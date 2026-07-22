"""Measures Cohen's kappa between the AI's recommendation and the human
reviewer's final decision (ADQ-33), from real `match_results` rows --
genuine Sprint 3 human-in-the-loop outcomes, not a synthetic gold set.

The AI's recommendation is derived directly from `match_results.
hard_filter_passed` (the same ground-truth column reporting/service.py's
get_match already surfaces), NOT inferred from the `reviewer_decision`
string's naming convention. That convention ("approved"/"rejected" imply
the reviewer accepted the AI's implicit recommendation, "overridden_to_X"
implies they flipped it) is never actually enforced anywhere:
submit_review/_write_back_review_decision (reporting/service.py) persist
whatever `decision` the caller sends without checking it against
hard_filter_passed, and the frontend (match-report-view.tsx) renders
Approve/Reject/Override unconditionally regardless of hard_filter_passed.
A reviewer can click plain "Approve" on a hard-filter-failed match, which
the naming convention would misread as agreement when it's actually a
disagreement. So this script treats hard_filter_passed and
reviewer_decision as two independently-sourced signals and compares them,
rather than parsing one string with an assumed meaning:

    AI recommendation = "approve" if hard_filter_passed else "reject"
    human decision     = "approve" if reviewer_decision indicates approval
                          (approved | overridden_to_approve) else "reject"

Cohen's kappa computed by hand (simple 2x2 categorical formula) rather than
pulling in scikit-learn/scipy -- neither is currently a dependency of this
backend (checked pyproject.toml), and one formula for one categorical
variable doesn't earn a new dependency per this project's
dependency-minimalism preference.

Spearman correlation is explicitly descoped: it needs a *ranked* gold set
(a full preference ordering over candidates per position), which doesn't
exist -- only per-candidate binary approve/reject outcomes do. Computing
Spearman on binarized labels would be statistically meaningless, so this
script does not attempt it.

Run from backend/: uv run python scripts/measure_scoring_agreement.py
"""

import asyncio

from sqlalchemy import select

from app.database.models import MatchResult
from app.database.session import async_session_factory
from app.domain.matching import ReviewDecision

_HUMAN_APPROVED = {ReviewDecision.approved.value, ReviewDecision.overridden_to_approve.value}


def _cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """Standard 2-category Cohen's kappa: kappa = (po - pe) / (1 - pe),
    po = observed agreement rate, pe = expected agreement rate by chance
    given each rater's own marginal distribution.
    """
    n = len(pairs)
    categories = {"approve", "reject"}

    agreements = sum(1 for ai, human in pairs if ai == human)
    po = agreements / n

    ai_marginal = {c: sum(1 for ai, _ in pairs if ai == c) / n for c in categories}
    human_marginal = {c: sum(1 for _, human in pairs if human == c) / n for c in categories}
    pe = sum(ai_marginal[c] * human_marginal[c] for c in categories)

    if pe == 1.0:
        # Both raters always picked the same single category -- no
        # disagreement was even possible, so kappa is undefined by the
        # standard formula's 0/0. Perfect observed agreement in this
        # degenerate case is reported as 1.0, matching the convention most
        # kappa implementations use.
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


async def main() -> None:
    async with async_session_factory() as session:
        raw_rows = (
            await session.execute(
                select(MatchResult.hard_filter_passed, MatchResult.reviewer_decision).where(
                    MatchResult.reviewer_decision.is_not(None)
                )
            )
        ).all()

    # The is_not(None) filter above already guarantees no None reviewer_decision
    # survives -- this narrows the type for mypy, not a behavior change.
    rows: list[tuple[bool, str]] = [
        (hard_filter_passed, decision)
        for hard_filter_passed, decision in raw_rows
        if decision is not None
    ]
    pairs = [
        (
            "approve" if hard_filter_passed else "reject",
            "approve" if decision in _HUMAN_APPROVED else "reject",
        )
        for hard_filter_passed, decision in rows
    ]
    n = len(pairs)

    decisions = [decision for _, decision in rows]
    print(f"n = {n} real reviewed match_results")
    print(
        f"raw reviewer_decision counts: {[decisions.count(v) for v in set(decisions)]} "
        f"-> {sorted(set(decisions))}"
    )

    if n == 0:
        print("kappa: undefined -- no reviewed match_results yet")
        return

    kappa = _cohens_kappa(pairs)
    print(f"Cohen's kappa (AI recommendation vs. human reviewer decision) = {kappa:.3f}")
    print(
        "Spearman correlation: descoped -- no ranked gold set exists, only "
        "binary approve/reject outcomes; computing Spearman on binarized "
        "labels would be statistically meaningless (see module docstring)."
    )


if __name__ == "__main__":
    asyncio.run(main())
