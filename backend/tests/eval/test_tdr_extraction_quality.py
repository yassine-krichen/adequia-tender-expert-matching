"""Live TDR extraction quality regression suite.

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- these hit real LLM providers against real documents in docs/tdrs/, which
costs real free-tier quota and real wall-clock time. Run explicitly:

    uv run pytest -m eval

Each fixture in fixtures/*.json is a hand-verified answer key, built by
actually reading the real source document once. Adding a new document:
read its real staffing/expert section once, write a fixture describing
what a correct extraction looks like, then this suite checks every
future retrieval/prompt change against every fixture that came before it
-- no re-reading documents by eye each time.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.extract import extract_tdr
from app.features.pipeline.nodes.ingest import extract_raw_text
from tests.eval._scoring import _TypeCounts

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Regression gate threshold from the sprint plan's acceptance criteria
# ("extraction F1 drops >3pts"). Update deliberately when the gold set
# intentionally grows/shrinks -- not silently, and not to paper over a real
# regression.
#
# TODO(ADQ-33, not yet done): this is still a PLACEHOLDER, not a real
# measured baseline. Two live attempts to compute the real number failed to
# complete within a 15-minute hard timeout each -- 13 real TDR PDFs, each
# needing a full live LLM extraction call, is simply too slow end-to-end
# under current free-tier Groq/Gemini + local-Ollama-fallback conditions
# (see the efficiency section of docs/04-evaluation-metrics.md, which
# independently measured extract_tdr p50=838s per document under quota-
# exhausted conditions). This is a deliberate, user-approved scope cut for
# Sprint 4, not an oversight -- see the `skip` marker on
# `test_tdr_extraction_field_level_f1_regression` below for how this is kept
# from silently hanging CI or a future dev's local run.
#
# Next session, to get the real number, don't just re-run this test as-is
# (it will hang again for the same reason) -- either:
#   (a) run it fixture-by-fixture (e.g. parametrize like the per-fixture
#       test above, so partial progress survives an interruption and each
#       fixture gets its own timeout), or
#   (b) run it against paid API access instead of free-tier, which removes
#       the key-rotation/rate-limit latency entirely.
# Whichever way, redirect output to a real file (not piped through `tail`),
# read the real aggregate F1 from the printed report, remove the `skip`
# marker below, and set this constant to the real measured value.
_BASELINE_TDR_F1 = 0.85  # PLACEHOLDER -- see TODO above, not a real measurement yet
_REGRESSION_TOLERANCE = 0.03


def _load_fixtures() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(_FIXTURES_DIR.glob("*.json"))]


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-·]+", "", text.lower())


def _title_matches(actual_title: str, title_contains_any: list[str]) -> bool:
    normalized_actual = _normalize(actual_title)
    return any(_normalize(candidate) in normalized_actual for candidate in title_contains_any)


def _diploma_matches(actual_diploma: str | None, diploma_contains: str | None) -> bool:
    if diploma_contains is None:
        return True
    if actual_diploma is None:
        return False
    return _normalize(diploma_contains) in _normalize(actual_diploma)


def _find_match(expected: dict[str, Any], actual_positions: list[ExpertPosition]) -> ExpertPosition | None:
    for position in actual_positions:
        if _title_matches(position.position_title, expected["title_contains_any"]) and _diploma_matches(
            position.mandatory_diploma, expected["diploma_contains"]
        ):
            return position
    return None


def _format_report(
    fixture_name: str, expected_positions: list[dict[str, Any]], actual_positions: list[ExpertPosition]
) -> str:
    lines = [f"Extraction mismatch for {fixture_name}", "", "Expected positions:"]
    for expected in expected_positions:
        match = _find_match(expected, actual_positions)
        status = "OK" if match else "MISSING"
        lines.append(
            f"  [{status}] title~{expected['title_contains_any']} "
            f"diploma~{expected['diploma_contains']} years={expected['minimum_years_experience']}"
        )
    lines.append("")
    lines.append("Actual extracted positions:")
    for position in actual_positions:
        lines.append(
            f"  - {position.position_title!r} diploma={position.mandatory_diploma!r} "
            f"years={position.minimum_years_experience!r}"
        )
    return "\n".join(lines)


@pytest.mark.eval
@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: Path(f["source_file"]).stem)
def test_tdr_extraction_matches_hand_verified_positions(fixture: dict[str, Any]) -> None:
    source_path = _REPO_ROOT / fixture["source_file"]
    raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)

    router = ModelRouter(get_settings())
    tdr = extract_tdr(
        raw_text,
        tdr_id="eval-run",
        source_file_path=source_path.name,
        router=router,
        embeddings=router.get_embedding_model(),
    )

    report = _format_report(source_path.name, fixture["expected_positions"], tdr.positions)
    for expected in fixture["expected_positions"]:
        match = _find_match(expected, tdr.positions)
        assert match is not None, report
        if expected["minimum_years_experience"] is not None:
            assert match.minimum_years_experience == expected["minimum_years_experience"], report


@pytest.mark.eval
@pytest.mark.skip(
    reason=(
        "ADQ-33: doesn't complete live -- 13 real TDR PDFs, each needing a "
        "full live LLM extraction call, hit a 15-minute hard timeout twice "
        "this session under free-tier Groq/Gemini + Ollama-fallback "
        "conditions, without producing a real aggregate F1. Deliberate, "
        "user-approved scope cut for Sprint 4, not a silent gap -- see the "
        "TODO above _BASELINE_TDR_F1 for exact next-session steps (run "
        "fixture-by-fixture, or with paid API access). Do NOT remove this "
        "skip and re-run as-is; it will hang again for the same reason."
    )
)
def test_tdr_extraction_field_level_f1_regression() -> None:
    """ADQ-30's DeepEval-style regression gate. Reuses `_find_match` (the
    same per-field matcher the per-fixture tests above use) to accumulate
    TP/FP/FN across ALL 13 fixtures into two field types -- "position"
    (title+diploma identity) and "minimum_years_experience" (only checked
    once a position is actually matched) -- then asserts the aggregate F1
    hasn't regressed past `_REGRESSION_TOLERANCE` below `_BASELINE_TDR_F1`.

    Kept entirely separate from the per-fixture parametrized tests above --
    those stay untouched for their failure-localization value (which
    fixture broke); this one gate is what CI actually asserts on.
    """
    router = ModelRouter(get_settings())
    per_field_counts: dict[str, _TypeCounts] = {
        "position": _TypeCounts(),
        "minimum_years_experience": _TypeCounts(),
    }
    detail_lines: list[str] = []

    for fixture in _load_fixtures():
        source_path = _REPO_ROOT / fixture["source_file"]
        raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)
        tdr = extract_tdr(
            raw_text,
            tdr_id="eval-run",
            source_file_path=source_path.name,
            router=router,
            embeddings=router.get_embedding_model(),
        )

        matched_actual_ids = set()
        for expected in fixture["expected_positions"]:
            match = _find_match(expected, tdr.positions)
            if match is None:
                per_field_counts["position"].false_negatives += 1
                detail_lines.append(
                    f"{source_path.name}: MISSING position title~{expected['title_contains_any']}"
                )
                continue

            per_field_counts["position"].true_positives += 1
            matched_actual_ids.add(id(match))

            if expected["minimum_years_experience"] is not None:
                if match.minimum_years_experience == expected["minimum_years_experience"]:
                    per_field_counts["minimum_years_experience"].true_positives += 1
                else:
                    per_field_counts["minimum_years_experience"].false_negatives += 1
                    detail_lines.append(
                        f"{source_path.name}: minimum_years_experience mismatch "
                        f"expected={expected['minimum_years_experience']} "
                        f"actual={match.minimum_years_experience}"
                    )

        # Extracted positions never matched to any expected entry -- over-
        # extraction, counted as a false positive on the "position" field.
        extra = [p for p in tdr.positions if id(p) not in matched_actual_ids]
        per_field_counts["position"].false_positives += len(extra)
        for position in extra:
            detail_lines.append(f"{source_path.name}: extra unmatched position {position.position_title!r}")

    aggregate = _TypeCounts(
        true_positives=sum(c.true_positives for c in per_field_counts.values()),
        false_positives=sum(c.false_positives for c in per_field_counts.values()),
        false_negatives=sum(c.false_negatives for c in per_field_counts.values()),
    )

    summary_lines = [
        f"{field}: precision={counts.precision:.2f} recall={counts.recall:.2f} f1={counts.f1:.2f} "
        f"(tp={counts.true_positives} fp={counts.false_positives} fn={counts.false_negatives})"
        for field, counts in per_field_counts.items()
    ]
    report = (
        f"TDR field-level F1 regression check -- aggregate F1={aggregate.f1:.3f} "
        f"(baseline={_BASELINE_TDR_F1}, tolerance={_REGRESSION_TOLERANCE})\n"
        + "\n".join(summary_lines)
        + "\n"
        + "\n".join(detail_lines)
    )
    print(report)

    assert aggregate.f1 >= _BASELINE_TDR_F1 - _REGRESSION_TOLERANCE, report
