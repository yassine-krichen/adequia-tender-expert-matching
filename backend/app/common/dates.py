from datetime import date, datetime
from typing import Any

_ONGOING_WORDS = {"", "présent", "present", "ongoing", "current", "aujourd'hui", "now"}
_PARTIAL_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")


def coerce_partial_date(value: Any) -> Any:
    """Tolerates the date shapes LLMs actually produce for CV/TDR fields:
    month- or year-only precision ("2016-01", "2016"), and words for an
    ongoing role/certification ("présent", "current") where the schema
    expects None instead.

    Returns the coerced date/None on a recognized shape, or the original
    value unchanged so Pydantic's own validation still raises a clear
    error on genuinely malformed input.
    """
    if value is None or isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value

    text = value.strip()
    if text.lower() in _ONGOING_WORDS:
        return None

    for fmt in _PARTIAL_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return value
