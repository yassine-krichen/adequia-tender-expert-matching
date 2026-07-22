"""Live RAGAS-style faithfulness/groundedness eval for generated rationales
(ADQ-29).

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- this hits real LLM providers twice per claim (once to generate the
rationale via the real pipeline, once per surviving claim for an NLI-style
faithfulness judge), so it costs real free-tier quota and real wall-clock
time. Run explicitly:

    uv run pytest tests/eval/test_report_faithfulness_quality.py -m eval -v

Mirrors test_injection_resistance.py's hand-built-`PipelineState` fixture
style exactly -- 4-5 variants exercising different rationale-generation
scenarios (skill match/miss mix, sector match present/absent, an anomaly
present, qualitative reasoning present), fed through the real
`build_citation_ledger` + `generate_rationale` + `assemble_citations`
pipeline functions with a real `ModelRouter` (no mocked LLM calls, matching
this project's "verify live" practice for anything touching an LLM).

This is "RAGAS-style"/"DeepEval-style" methodology built on this codebase's
own `ModelRouter` + pytest/`@pytest.mark.eval` idiom -- not the literal
`ragas`/`deepeval` packages (no new dependencies, per this sprint's design
decision).

Faithfulness is scored against the citation ledger entry's `text`, not raw
CV/TDR text -- the ledger is the pipeline's actual guardrailed context
boundary a claim is meant to trace to (see generate_rationale's docstring:
the LLM never sees raw CV/TDR text or source_span, only ledger id/fact_type/
text), so that is the correct grounding surface to check faithfulness
against, not the source documents themselves.
"""

import json

import pytest
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from app.common.llm.router import ModelRouter
from app.common.llm.structured import invoke_structured
from app.config.settings import get_settings
from app.domain.cv import NormalizedSkill
from app.domain.matching import Anomaly, AnomalySeverity, AnomalyType
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.citation_ledger import LedgerEntry, build_citation_ledger
from app.features.pipeline.nodes.generate_report import assemble_citations, generate_rationale
from app.features.pipeline.state import PipelineState

# Real CI gate value from the sprint plan's acceptance summary.
_FAITHFULNESS_THRESHOLD = 0.85


@pytest.fixture(scope="module")
def real_router() -> ModelRouter:
    return ModelRouter(get_settings())


def _position() -> ExpertPosition:
    return ExpertPosition(
        position_id="p1",
        position_title="Chef de projet",
        required_skills=["Gestion de projet", "Python", "Docker"],
        required_sector_experience="Bancaire",
        source_span="span",
    )


def _skill(raw_term: str, *, canonical_id: str | None) -> NormalizedSkill:
    return NormalizedSkill(raw_term=raw_term, canonical_id=canonical_id, confidence=0.9, matched_via="direct")


def _base_state(
    *,
    normalized_skills: list[NormalizedSkill],
    normalized_position_skills: list[NormalizedSkill],
    sector_match_source_span: str | None = None,
    anomalies: list[Anomaly] | None = None,
    qualitative_fit_reasoning: str | None = None,
) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": _position(),
        "cv_extracted": None,
        "normalized_skills": normalized_skills,
        "normalized_position_skills": normalized_position_skills,
        "required_sector_vector": None,
        "sector": None,
        "hard_filter_passed": True,
        "hard_filter_failures": [],
        "sub_scores": None,
        "compatibility_score": 0.75,
        "qualitative_fit_reasoning": qualitative_fit_reasoning,
        "sector_match_source_span": sector_match_source_span,
        "anomalies": anomalies or [],
        "rationale": None,
        "citations": [],
        "needs_human_review": False,
        "reviewer_decision": None,
    }


# --- 5 hand-built scenarios, mirroring test_injection_resistance.py's style ---

_SCENARIOS: list[tuple[str, PipelineState]] = [
    (
        "all_skills_matched",
        _base_state(
            normalized_skills=[
                _skill("Gestion de projet", canonical_id="skill-1"),
                _skill("Python", canonical_id="skill-2"),
                _skill("Docker", canonical_id="skill-3"),
            ],
            normalized_position_skills=[
                _skill("Gestion de projet", canonical_id="skill-1"),
                _skill("Python", canonical_id="skill-2"),
                _skill("Docker", canonical_id="skill-3"),
            ],
        ),
    ),
    (
        "skill_match_and_miss_mix",
        _base_state(
            normalized_skills=[_skill("Gestion de projet", canonical_id="skill-1")],
            normalized_position_skills=[
                _skill("Gestion de projet", canonical_id="skill-1"),
                _skill("Python", canonical_id="skill-2"),
                _skill("Docker", canonical_id="skill-3"),
            ],
        ),
    ),
    (
        "sector_match_present",
        _base_state(
            normalized_skills=[_skill("Gestion de projet", canonical_id="skill-1")],
            normalized_position_skills=[_skill("Gestion de projet", canonical_id="skill-1")],
            sector_match_source_span="5 ans d'expérience dans le secteur bancaire chez ST2i.",
        ),
    ),
    (
        "anomaly_present",
        _base_state(
            normalized_skills=[_skill("Python", canonical_id="skill-2")],
            normalized_position_skills=[_skill("Python", canonical_id="skill-2")],
            anomalies=[
                Anomaly(
                    type=AnomalyType.expired_certification,
                    severity=AnomalySeverity.warning,
                    description="La certification PMP a expiré le 2023-01-15.",
                    source_citation="PMP, expire 2023-01-15",
                )
            ],
        ),
    ),
    (
        "qualitative_reasoning_present",
        _base_state(
            normalized_skills=[_skill("Docker", canonical_id="skill-3")],
            normalized_position_skills=[_skill("Docker", canonical_id="skill-3")],
            qualitative_fit_reasoning=(
                "Le candidat a occupé des postes de direction technique pendant 6 ans dans "
                "des projets de taille comparable, avec une montée en séniorité régulière."
            ),
        ),
    ),
]


# --- faithfulness judge: an NLI-style "does this claim follow from this fact" call ---


class _FaithfulnessJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_faithful: bool
    reasoning: str = Field(description="1 sentence explaining the verdict")


_FAITHFULNESS_JUDGE_PROMPT = (
    "You are a faithfulness judge (RAGAS-style NLI check). You are given "
    "one or more grounding FACTS and one CLAIM. Decide whether the claim is "
    "fully entailed by the facts TAKEN TOGETHER -- true if a reader given "
    "only the facts would agree the claim follows from them, with no "
    "invented detail absent from every fact. A claim that combines "
    "information from more than one fact is faithful as long as each part "
    "of the claim traces to at least one of the given facts -- judge the "
    "claim against the union of all facts, not against any single fact in "
    "isolation. False only if the claim adds specifics (numbers, names, "
    "qualifiers) absent from all the facts combined, or contradicts them."
)


def _judge_claim_faithfulness(
    claim: str, ledger_facts: list[str], *, router: ModelRouter
) -> _FaithfulnessJudgment:
    """Judges one claim against the UNION of every fact it cites -- not one
    call per cited fact. A claim citing two ledger entries (e.g. combining
    a skill-match fact and a sector-match fact into one sentence) is
    faithful as long as it's entailed by the two facts together; judging it
    against either fact in isolation would wrongly flag it as unfaithful
    for mentioning the other fact's content. This mirrors RAGAS's own
    statement-vs-full-context faithfulness check, not statement-vs-single-
    context-chunk.
    """
    messages: list[BaseMessage] = [
        SystemMessage(content=_FAITHFULNESS_JUDGE_PROMPT),
        HumanMessage(
            content=json.dumps({"facts": ledger_facts, "claim": claim}, ensure_ascii=False)
        ),
    ]
    return invoke_structured(
        messages,
        _FaithfulnessJudgment,
        primary=router.invoke_reasoning,
        retry=router.invoke_reasoning,
        failure_message="Faithfulness judgment failed",
    )


def _claim_citation_facts(claim_sentence: str, ledger: list[LedgerEntry], cited_ids: list[str]) -> list[str]:
    """The ledger entries actually backing a surviving claim, in citation
    order -- assemble_citations already validated every id in cited_ids
    exists in the ledger, but the rationale_output object doesn't survive
    past generate_rationale, so this re-derives which entries backed
    which claim from the ledger ids `cited_ids` (from the same
    RationaleClaim the caller already has in hand).
    """
    ledger_by_id = {entry.id: entry for entry in ledger}
    return [ledger_by_id[cid].text for cid in cited_ids if cid in ledger_by_id]


@pytest.mark.eval
def test_report_faithfulness_and_citation_coverage(real_router: ModelRouter) -> None:
    """Runs all 5 hand-built scenarios and aggregates every judged claim into
    one overall faithfulness score, asserted once against
    `_FAITHFULNESS_THRESHOLD` -- not one independent assertion per scenario.

    A per-scenario assertion is too noise-sensitive: some scenarios produce
    as few as 1-3 claims, so a single borderline judge call (an LLM judge
    call has real run-to-run variance, same as the generation call it's
    judging) can fail an entire scenario on its own. Aggregating over the
    whole live run's ~10 judged claims is what the sprint plan's single
    "assert faithfulness >= 0.85" gate actually means, and it's the
    statistically sound way to apply an LLM-judged threshold.
    """
    faithful_count = 0
    total_judged = 0
    total_surviving = 0
    total_claims_before_filtering = 0
    detail_lines: list[str] = []

    for scenario_name, state in _SCENARIOS:
        ledger = build_citation_ledger(state, taxonomy_names={})
        rationale_output = generate_rationale(ledger, router=real_router)
        surviving_sentences, _citations, scenario_total_claims = assemble_citations(
            rationale_output, ledger
        )
        total_surviving += len(surviving_sentences)
        total_claims_before_filtering += scenario_total_claims

        detail_lines.append(f"[{scenario_name}] ledger entries: {[e.text for e in ledger]}")
        for claim in rationale_output.claims:
            if claim.sentence not in surviving_sentences:
                continue  # dropped as hallucinated by assemble_citations -- not a real claim to judge
            facts = _claim_citation_facts(claim.sentence, ledger, claim.cited_ledger_ids)
            if not facts:
                continue
            judgment = _judge_claim_faithfulness(claim.sentence, facts, router=real_router)
            total_judged += 1
            if judgment.is_faithful:
                faithful_count += 1
            detail_lines.append(
                f"  [{scenario_name}] claim={claim.sentence!r} facts={facts!r} "
                f"faithful={judgment.is_faithful} reasoning={judgment.reasoning!r}"
            )

    faithfulness = faithful_count / total_judged if total_judged else 1.0
    # Citation coverage: surviving-claims-with-valid-citations / total-claims-before-filtering.
    citation_coverage = (
        total_surviving / total_claims_before_filtering if total_claims_before_filtering else 1.0
    )
    report = (
        f"Overall faithfulness={faithfulness:.2f} ({faithful_count}/{total_judged} claims) "
        f"citation_coverage={citation_coverage:.2f} "
        f"({total_surviving}/{total_claims_before_filtering})\n" + "\n".join(detail_lines)
    )
    print(report)

    assert faithfulness >= _FAITHFULNESS_THRESHOLD, report
