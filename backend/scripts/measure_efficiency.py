"""Measures real per-node pipeline latency (ADQ-33), mirroring
backfill_cv_content_hash.py's standalone-script structure/conventions.

Times every real pipeline node against a small real sample -- 2 real TDR
positions (from docs/tdrs/) x 2 real synthetic CVs (from
docs/cvs/synthetic/), the same fixture pool test_tdr_extraction_quality.py /
test_cv_extraction_quality.py already depend on -- via `time.perf_counter()`
around each node call, exactly as the real matching pipeline invokes them
(app/features/pipeline/graph.py), not a synthetic timing harness.

Node coverage: extract_tdr, extract_cv, normalize_position_skills +
normalize_cv_skills, score (check_hard_filters + score_soft_criteria +
judge_qualitative_fit), detect_anomalies (rule checks + judge_plausibility),
generate_rationale. calibrate_against_history (an MCP call to
historical_decisions, a small memory-lookup step orthogonal to the
extraction/scoring/report cost this script is measuring) is deliberately
out of scope here -- timing it would require standing up a live MCP client
connection, adding infra dependency this script doesn't otherwise need.

Token-volume verification (live, confirmed this pass): `UsageMetadataCallbackHandler`
DOES emit real usage_metadata when calling the underlying LangChain chat
models (ChatGroq, ChatOllama) directly with `config={"callbacks": [...]}}` --
verified live against both providers. However, `ModelRouter.invoke_extraction`/
`invoke_reasoning` (the only entry points every pipeline node actually calls)
take no `config`/`callbacks` parameter and never forward one to the
underlying `model.invoke()` call -- so token volume is NOT capturable
through the current router wrapper without a signature change to
ModelRouter itself, which is out of scope for a measurement script. Honest
fallback per this sprint's design decision: $0 real cost (free-tier-only
architecture -- Groq/Gemini free tier + local Ollama, no paid API access
anywhere), token volume not reliably captured through the current router
wrapper this pass.

Run from backend/: uv run python scripts/measure_efficiency.py
"""

import asyncio
import time
from pathlib import Path
from statistics import median

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.session import async_session_factory
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.citation_ledger import build_citation_ledger
from app.features.pipeline.nodes.detect_anomalies import (
    check_age_at_graduation,
    check_date_overlaps,
    check_employment_gaps,
    check_expired_certifications,
    judge_plausibility,
)
from app.features.pipeline.nodes.extract import extract_cv, extract_tdr
from app.features.pipeline.nodes.generate_report import generate_rationale
from app.features.pipeline.nodes.ingest import extract_raw_text
from app.features.pipeline.nodes.normalize_skills import (
    normalize_cv_skills,
    normalize_position_skills,
)
from app.features.pipeline.nodes.score import (
    check_hard_filters,
    judge_qualitative_fit,
    score_soft_criteria,
)
from app.features.pipeline.state import PipelineState

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Small real sample -- 2 TDR PDFs, 2 synthetic CVs -- kept deliberately small
# (this measures real wall-clock latency against live free-tier providers,
# not a synthetic benchmark) per this sprint's "small real sample" scoping.
_TDR_FILES = [
    "docs/tdrs/ai-chatbot-gafi.pdf",
    "docs/tdrs/software-developer-unfpa.pdf",
]
_CV_FILES = [
    "docs/cvs/synthetic/amine-ferjani.docx",
    "docs/cvs/synthetic/nadia-ben-salah.pdf",
]

_latencies: dict[str, list[float]] = {}


def _record(node: str, seconds: float) -> None:
    _latencies.setdefault(node, []).append(seconds)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(int(round(pct * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[index]


async def main() -> None:
    settings = get_settings()
    router = ModelRouter(settings)
    embeddings = router.get_embedding_model()

    positions: list[ExpertPosition] = []
    for tdr_file in _TDR_FILES:
        source_path = _REPO_ROOT / tdr_file
        raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)
        start = time.perf_counter()
        tdr = extract_tdr(
            raw_text,
            tdr_id="efficiency-run",
            source_file_path=source_path.name,
            router=router,
            embeddings=embeddings,
        )
        _record("extract_tdr", time.perf_counter() - start)
        positions.extend(tdr.positions)

    cvs = []
    for cv_file in _CV_FILES:
        source_path = _REPO_ROOT / cv_file
        raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)
        start = time.perf_counter()
        cv = extract_cv(
            raw_text,
            candidate_id="efficiency-run",
            source_file_path=source_path.name,
            router=router,
        )
        _record("extract_cv", time.perf_counter() - start)
        cvs.append(cv)

    async with async_session_factory() as session:
        for position in positions:
            start = time.perf_counter()
            normalized_position_skills = await normalize_position_skills(
                position, session=session, embeddings=embeddings
            )
            _record("normalize_position_skills", time.perf_counter() - start)
            required_sector_vector = (
                embeddings.embed_query(position.required_sector_experience)
                if position.required_sector_experience
                else None
            )

            for cv in cvs:
                match_start = time.perf_counter()

                start = time.perf_counter()
                normalized_cv_skills = await normalize_cv_skills(
                    cv, session=session, embeddings=embeddings
                )
                _record("normalize_cv_skills", time.perf_counter() - start)

                start = time.perf_counter()
                hard_filter_passed, hard_filter_failures = check_hard_filters(cv, position)
                sub_scores, sector_match_source_span = score_soft_criteria(
                    cv,
                    normalized_cv_skills,
                    normalized_position_skills,
                    required_sector_vector,
                    embeddings=embeddings,
                )
                qualitative_fit_reasoning = None
                if hard_filter_passed:
                    judgment = judge_qualitative_fit(cv, position, router=router)
                    sub_scores = sub_scores.model_copy(
                        update={"qualitative_fit_score": judgment.qualitative_fit_score}
                    )
                    qualitative_fit_reasoning = judgment.reasoning
                _record("score", time.perf_counter() - start)

                start = time.perf_counter()
                anomalies = [
                    *check_employment_gaps(cv.experience),
                    *check_date_overlaps(cv.experience),
                    *check_expired_certifications(cv.certifications),
                    *(
                        check_age_at_graduation(cv.birth_date, cv.education)
                        if cv.birth_date is not None
                        else []
                    ),
                ]
                if hard_filter_passed:
                    anomalies.extend(judge_plausibility(cv, position, router=router))
                _record("detect_anomalies", time.perf_counter() - start)

                state: PipelineState = {
                    "cv_raw_text": cv.raw_text,
                    "tdr_raw_text": "",
                    "position": position,
                    "cv_extracted": cv,
                    "normalized_skills": normalized_cv_skills,
                    "normalized_position_skills": normalized_position_skills,
                    "required_sector_vector": required_sector_vector,
                    "sector": None,
                    "hard_filter_passed": hard_filter_passed,
                    "hard_filter_failures": hard_filter_failures,
                    "sub_scores": sub_scores,
                    "compatibility_score": 0.5,
                    "qualitative_fit_reasoning": qualitative_fit_reasoning,
                    "sector_match_source_span": sector_match_source_span,
                    "anomalies": anomalies,
                    "rationale": None,
                    "citations": [],
                    "needs_human_review": False,
                    "reviewer_decision": None,
                }
                ledger = build_citation_ledger(state, taxonomy_names={})
                start = time.perf_counter()
                generate_rationale(ledger, router=router)
                _record("generate_rationale", time.perf_counter() - start)

                _record("overall_per_match", time.perf_counter() - match_start)

    print("\n=== Real pipeline node latency (p50/p95, seconds) ===")
    for node, values in _latencies.items():
        p50 = median(values)
        p95 = _percentile(values, 0.95)
        print(
            f"{node}: n={len(values)} p50={p50:.2f}s p95={p95:.2f}s samples={[round(v, 2) for v in values]}"
        )

    print(
        "\nCost: $0 (free-tier-only architecture -- Groq/Gemini free tier + "
        "local Ollama, no paid API access anywhere). Token volume: not "
        "reliably captured through the current ModelRouter wrapper this "
        "pass (see module docstring for the live-verified reason)."
    )


if __name__ == "__main__":
    asyncio.run(main())
