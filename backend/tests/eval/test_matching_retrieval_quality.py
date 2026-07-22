"""Live coarse-retrieval quality check against our own ground-truth matching set.

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- shortlist_candidates needs real embeddings (the default suite mocks
those) and a real CV pool, so this is run explicitly:

    uv run pytest -m eval

fixtures/gold_matching_set.json labels the true match for one hand-crafted
or genuinely-real-TDR-extracted position per candidate in the pool
(docs/cvs/synthetic/). This *is* the working ground truth for retrieval
quality -- no external staffing-decision export is coming, so this is
grown deliberately alongside the candidate/TDR pool instead of waiting on
one (see docs/08-company-data-checklist.md for the one thing genuine
historical company data would still add: real acceptance/rejection
outcomes, not just "who's a plausible fit"). One entry
(gold-software-developer-ilo-real) is pulled verbatim from a real TDR
extraction rather than hand-written, to keep the set honest about what
production extractions actually look like. Skips if the synthetic CVs
haven't been uploaded to the CV pool this suite runs against yet (see the
skip message for how to seed them) -- but that skip only fires against a
real, reachable Postgres. This test needs a live seeded Postgres+pgvector
stack to run at all, so it's excluded from .github/workflows/eval.yml
(no such stack there) and must be run manually against a seeded dev
stack instead.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.database.models import Candidate as CandidateModel
from app.database.session import async_session_factory
from app.domain.tdr import ExpertPosition
from app.features.matching.coarse_retrieval import shortlist_candidates

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "matching"
_SHORTLIST_K = 3


def _load_gold_set() -> list[dict[str, Any]]:
    return json.loads((_FIXTURES_DIR / "gold_matching_set.json").read_text(encoding="utf-8"))


async def _candidate_pool_covers(required_names: set[str]) -> bool:
    async with async_session_factory() as session:
        rows = (await session.execute(select(CandidateModel.full_name))).scalars().all()
    return required_names.issubset(set(rows))


@pytest.mark.eval
async def test_coarse_retrieval_precision_and_recall_at_k() -> None:
    gold_set = _load_gold_set()
    required_names = {name for entry in gold_set for name in entry["relevant_candidate_names"]}

    if not await _candidate_pool_covers(required_names):
        pytest.skip(
            "CV pool doesn't contain the synthetic candidates the gold set expects -- "
            "upload docs/cvs/synthetic/*.{pdf,docx} via POST /candidates/cv first."
        )

    embeddings = ModelRouter(get_settings()).get_embedding_model()
    precisions: list[float] = []
    recalls: list[float] = []
    report_lines = []

    async with async_session_factory() as session:
        for entry in gold_set:
            position = ExpertPosition.model_validate(entry["position"])
            relevant = set(entry["relevant_candidate_names"])

            shortlist = await shortlist_candidates(
                position, session=session, embeddings=embeddings, k=_SHORTLIST_K
            )
            shortlisted_names = []
            for cv_row in shortlist:
                candidate = await session.get(CandidateModel, cv_row.candidate_id)
                assert candidate is not None
                shortlisted_names.append(candidate.full_name)

            hits = relevant & set(shortlisted_names)
            precision = len(hits) / _SHORTLIST_K
            recall = len(hits) / len(relevant)
            precisions.append(precision)
            recalls.append(recall)
            report_lines.append(
                f"{position.position_title}: shortlisted={shortlisted_names} "
                f"relevant={sorted(relevant)} precision@{_SHORTLIST_K}={precision:.2f} recall@{_SHORTLIST_K}={recall:.2f}"
            )

    mean_precision = sum(precisions) / len(precisions)
    mean_recall = sum(recalls) / len(recalls)
    report = (
        f"Precision@{_SHORTLIST_K}={mean_precision:.2f} Recall@{_SHORTLIST_K}={mean_recall:.2f}\n"
        + "\n".join(report_lines)
    )

    # Real baseline as of this 11-entry set (mix of hand-crafted positions
    # covering all 11 candidates + one genuinely real TDR-extracted
    # position): Recall@3 = 1.0, Precision@3 = 0.33 (expected -- only one
    # truly relevant candidate per position, out of a k=3 shortlist).
    # 0.9 leaves room for one legitimate miss as the pool keeps growing
    # without masking an actual regression the way the old 0.5 floor
    # (set before any real run existed) would have.
    assert mean_recall >= 0.9, report
