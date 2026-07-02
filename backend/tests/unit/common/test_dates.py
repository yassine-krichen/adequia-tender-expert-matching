from datetime import date

import pytest

from app.common.dates import coerce_partial_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2016-01-15", date(2016, 1, 15)),
        ("2016-01", date(2016, 1, 1)),
        ("2016", date(2016, 1, 1)),
        ("présent", None),
        ("present", None),
        ("Present", None),
        ("ongoing", None),
        ("current", None),
        ("", None),
        (None, None),
    ],
)
def test_coerce_partial_date_recognized_shapes(raw: str | None, expected: date | None) -> None:
    assert coerce_partial_date(raw) == expected


def test_coerce_partial_date_passes_through_already_a_date() -> None:
    value = date(2020, 5, 1)
    assert coerce_partial_date(value) is value


def test_coerce_partial_date_leaves_unparseable_strings_for_pydantic_to_reject() -> None:
    assert coerce_partial_date("not a date at all") == "not a date at all"
