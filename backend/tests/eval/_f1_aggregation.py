"""Reads/aggregates the per-fixture F1 result files persisted by the TDR
extraction quality suite's per-fixture test (see test_tdr_extraction_quality.py).

Split out as a pure function (no pytest.skip, no live LLM call, no file
writing) so it's independently unit-testable against a temp directory of
fake JSON result files -- see tests/unit/eval/test_f1_aggregation.py.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from tests.eval._scoring import _TypeCounts


@dataclass
class F1AggregationResult:
    counts: _TypeCounts
    fixtures_found: int
    fixtures_expected: int

    @property
    def is_complete(self) -> bool:
        return self.fixtures_found >= self.fixtures_expected


def aggregate_persisted_f1_results(
    results_dir: Path, fixtures_expected: int
) -> F1AggregationResult:
    """Sums every `*.json` file in results_dir (each one fixture's
    {"true_positives": .., "false_positives": .., "false_negatives": ..})
    into one aggregate _TypeCounts. Doesn't validate fixtures_found against
    fixtures_expected itself -- callers (the aggregate pytest test) decide
    what an incomplete count means (skip vs. gate).
    """
    files = sorted(results_dir.glob("*.json")) if results_dir.exists() else []
    aggregate = _TypeCounts()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        aggregate.true_positives += data["true_positives"]
        aggregate.false_positives += data["false_positives"]
        aggregate.false_negatives += data["false_negatives"]

    return F1AggregationResult(
        counts=aggregate, fixtures_found=len(files), fixtures_expected=fixtures_expected
    )
