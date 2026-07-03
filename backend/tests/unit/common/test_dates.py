from datetime import date

import pytest

from app.common.dates import coerce_partial_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2016-01-15", date(2016, 1, 15)),
        ("2016-01", date(2016, 1, 1)),
        ("2016", date(2016, 1, 1)),
        ("28/08/2024", date(2024, 8, 28)),
        ("28-08-2024", date(2024, 8, 28)),
        ("28 août 2024", date(2024, 8, 28)),
        ("28 aout 2024", date(2024, 8, 28)),
        ("présent", None),
        ("present", None),
        ("Present", None),
        ("ongoing", None),
        ("current", None),
        ("null", None),
        ("Null", None),
        ("none", None),
        ("n/a", None),
        ("unknown", None),
        ("", None),
        (None, None),
    ],
)
def test_coerce_partial_date_recognized_shapes(raw: str | None, expected: date | None) -> None:
    assert coerce_partial_date(raw) == expected


def test_coerce_partial_date_passes_through_already_a_date() -> None:
    value = date(2020, 5, 1)
    assert coerce_partial_date(value) is value


def test_coerce_partial_date_falls_back_to_none_for_a_non_date_description() -> None:
    """Regression: a real TDR gave "07 jours ouvrables à partir de la date
    de démarrage du projet" (a relative duration, not a calendar date) for
    an optional deadline field — leaving that string for Pydantic to reject
    crashed the entire extraction over one non-critical field.
    """
    assert coerce_partial_date("07 jours ouvrables à partir du démarrage") is None
