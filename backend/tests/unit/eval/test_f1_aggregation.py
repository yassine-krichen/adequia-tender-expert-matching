import json
from pathlib import Path

from tests.eval._f1_aggregation import aggregate_persisted_f1_results


def _write_result(directory: Path, name: str, tp: int, fp: int, fn: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(
        json.dumps({"true_positives": tp, "false_positives": fp, "false_negatives": fn}),
        encoding="utf-8",
    )


def test_aggregate_sums_true_false_positives_and_negatives_across_fixture_files(
    tmp_path: Path,
) -> None:
    _write_result(tmp_path, "fixture-a", tp=2, fp=1, fn=0)
    _write_result(tmp_path, "fixture-b", tp=3, fp=0, fn=1)

    result = aggregate_persisted_f1_results(tmp_path, fixtures_expected=2)

    assert result.counts.true_positives == 5
    assert result.counts.false_positives == 1
    assert result.counts.false_negatives == 1
    assert result.fixtures_found == 2
    assert result.is_complete is True


def test_aggregate_computes_correct_f1_from_summed_counts(tmp_path: Path) -> None:
    _write_result(tmp_path, "fixture-a", tp=1, fp=0, fn=0)
    _write_result(tmp_path, "fixture-b", tp=1, fp=0, fn=0)

    result = aggregate_persisted_f1_results(tmp_path, fixtures_expected=2)

    assert result.counts.f1 == 1.0


def test_aggregate_reports_incomplete_when_fewer_result_files_than_expected(
    tmp_path: Path,
) -> None:
    _write_result(tmp_path, "fixture-a", tp=1, fp=0, fn=0)

    result = aggregate_persisted_f1_results(tmp_path, fixtures_expected=3)

    assert result.fixtures_found == 1
    assert result.is_complete is False


def test_aggregate_handles_a_results_directory_that_does_not_exist_yet(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does-not-exist"

    result = aggregate_persisted_f1_results(missing_dir, fixtures_expected=5)

    assert result.fixtures_found == 0
    assert result.counts.true_positives == 0
    assert result.is_complete is False
