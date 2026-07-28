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
from tests.eval._f1_aggregation import aggregate_persisted_f1_results
from tests.eval._scoring import _TypeCounts

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).parent / "fixtures"

# ADQ-33: the original monolithic F1 test looped over all 12 fixtures
# (chunked, multi-LLM-call each) in one test and twice blew a 15-minute CI
# timeout without producing a real aggregate F1 (see the efficiency section
# of docs/04-evaluation-metrics.md -- extract_tdr p50=838s/doc under
# quota-exhausted free-tier conditions). Split into two tests instead:
#
# 1. `test_tdr_extraction_field_level_f1_per_fixture` (parametrized, one
#    LLM extraction run per fixture, its own `timeout` marker) persists
#    that one fixture's TP/FP/FN to `.f1_results/<fixture-stem>.json` --
#    partial progress survives an interrupted/quota-exhausted run.
# 2. `test_tdr_extraction_field_level_f1_regression` (not skipped) reads
#    every persisted result file, sums them, and gates on the aggregate F1
#    -- or skips with a clear "N/12 computed" message if the per-fixture
#    test hasn't finished populating every result file yet.
#
# Regression gate threshold from the sprint plan's acceptance criteria
# ("extraction F1 drops >3pts"). Update deliberately when the gold set
# intentionally grows/shrinks -- not silently, and not to paper over a real
# regression.
#
# STILL a PLACEHOLDER, not a real measured baseline -- computing the real
# number requires actually running the per-fixture test above against all
# 12 fixtures (one real LLM extraction call each) and reading back the
# aggregate F1 the regression test below reports, then replacing this
# constant with that measured value (mirroring how test_cv_extraction_
# quality.py's _BASELINE_CV_F1 was set from a real run).
_BASELINE_TDR_F1 = 0.85  # PLACEHOLDER -- not a real measurement yet, see note above
_REGRESSION_TOLERANCE = 0.03
_F1_RESULTS_DIR = Path(__file__).parent / ".f1_results"


def _load_fixtures() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


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


def _find_match(
    expected: dict[str, Any], actual_positions: list[ExpertPosition]
) -> ExpertPosition | None:
    for position in actual_positions:
        if _title_matches(
            position.position_title, expected["title_contains_any"]
        ) and _diploma_matches(position.mandatory_diploma, expected["diploma_contains"]):
            return position
    return None


def _format_report(
    fixture_name: str,
    expected_positions: list[dict[str, Any]],
    actual_positions: list[ExpertPosition],
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


def _compute_fixture_f1(fixture: dict[str, Any], tdr: Any) -> tuple[_TypeCounts, list[str]]:
    """One fixture's contribution to the aggregate F1 -- same per-field
    matching (`_find_match`) the per-fixture positions test above uses,
    folded into a single _TypeCounts across "position" (title+diploma
    identity) and "minimum_years_experience" (only checked once a position
    is actually matched).
    """
    counts = _TypeCounts()
    detail_lines: list[str] = []
    matched_actual_ids: set[int] = set()

    for expected in fixture["expected_positions"]:
        match = _find_match(expected, tdr.positions)
        if match is None:
            counts.false_negatives += 1
            detail_lines.append(f"MISSING position title~{expected['title_contains_any']}")
            continue

        counts.true_positives += 1
        matched_actual_ids.add(id(match))

        if expected["minimum_years_experience"] is not None:
            if match.minimum_years_experience == expected["minimum_years_experience"]:
                counts.true_positives += 1
            else:
                counts.false_negatives += 1
                detail_lines.append(
                    "minimum_years_experience mismatch "
                    f"expected={expected['minimum_years_experience']} "
                    f"actual={match.minimum_years_experience}"
                )

    # Extracted positions never matched to any expected entry -- over-
    # extraction, counted as a false positive.
    extra = [p for p in tdr.positions if id(p) not in matched_actual_ids]
    counts.false_positives += len(extra)
    for position in extra:
        detail_lines.append(f"extra unmatched position {position.position_title!r}")

    return counts, detail_lines


@pytest.mark.eval
@pytest.mark.timeout(180)
@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: Path(f["source_file"]).stem)
def test_tdr_extraction_field_level_f1_per_fixture(fixture: dict[str, Any]) -> None:
    """ADQ-33: computes one fixture's TP/FP/FN and persists it to
    `.f1_results/<fixture-stem>.json`, instead of accumulating all 12
    fixtures in one test (see the module docstring note above
    _BASELINE_TDR_F1 for why the original monolithic test never
    completed). A 3-minute per-fixture timeout means one slow/quota-
    exhausted fixture can't sink the whole run -- partial progress
    (whichever fixtures already ran) survives.
    """
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

    counts, detail_lines = _compute_fixture_f1(fixture, tdr)

    _F1_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = _F1_RESULTS_DIR / f"{source_path.stem}.json"
    result_path.write_text(
        json.dumps(
            {
                "true_positives": counts.true_positives,
                "false_positives": counts.false_positives,
                "false_negatives": counts.false_negatives,
                "details": detail_lines,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_tdr_extraction_field_level_f1_regression() -> None:
    """ADQ-30's DeepEval-style regression gate. NOT skipped -- reads every
    result file the per-fixture test above persists, sums them into one
    aggregate F1, and asserts it hasn't regressed past
    `_REGRESSION_TOLERANCE` below `_BASELINE_TDR_F1`. Skips (rather than
    silently passing) if the per-fixture test hasn't populated every
    fixture's result file yet -- e.g. on a machine that's never run
    `pytest -m eval` for TDR extraction.

    Kept entirely separate from the per-fixture test above -- that one
    stays parametrized for its failure-localization value (which fixture
    broke); this one gate is what CI actually asserts on, and doesn't
    itself call any LLM.
    """
    fixtures = _load_fixtures()
    result = aggregate_persisted_f1_results(_F1_RESULTS_DIR, fixtures_expected=len(fixtures))

    if not result.is_complete:
        pytest.skip(
            f"{result.fixtures_found}/{result.fixtures_expected} fixture results computed "
            "-- run test_tdr_extraction_field_level_f1_per_fixture first "
            "(pytest -m eval tests/eval/test_tdr_extraction_quality.py)"
        )

    counts = result.counts
    report = (
        f"TDR field-level F1 regression check -- aggregate F1={counts.f1:.3f} "
        f"(baseline={_BASELINE_TDR_F1}, tolerance={_REGRESSION_TOLERANCE}) "
        f"precision={counts.precision:.2f} recall={counts.recall:.2f} "
        f"(tp={counts.true_positives} fp={counts.false_positives} fn={counts.false_negatives})"
    )
    print(report)

    assert counts.f1 >= _BASELINE_TDR_F1 - _REGRESSION_TOLERANCE, report
