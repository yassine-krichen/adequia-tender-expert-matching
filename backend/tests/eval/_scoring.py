"""Shared precision/recall/F1 tallying for tests/eval/'s regression suites.

Extracted from test_anomaly_detection_quality.py's originally-local
`_TypeCounts` dataclass (ADQ-30) so the field-level extraction F1 regression
tests (test_tdr_extraction_quality.py / test_cv_extraction_quality.py) can
reuse the exact same math instead of re-deriving it. Generic over TP/FP/FN
counts of any kind -- rule-based anomaly flags, extracted field matches,
whatever a caller is tallying -- this file has no opinion on what a "true
positive" means to its caller.
"""

from dataclasses import dataclass


@dataclass
class _TypeCounts:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0
