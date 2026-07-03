import re
from datetime import date, datetime
from typing import Any

_ONGOING_WORDS = {
    "",
    "présent",
    "present",
    "ongoing",
    "current",
    "aujourd'hui",
    "now",
    "null",
    "none",
    "n/a",
    "unknown",
}
_PARTIAL_DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y", "%d/%m/%Y", "%d-%m-%Y")

_FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}
_FRENCH_DATE_RE = re.compile(r"^(\d{1,2})\s+([a-zéû]+)\s+(\d{4})$", re.IGNORECASE)


def _parse_french_date(text: str) -> date | None:
    match = _FRENCH_DATE_RE.match(text.lower())
    if not match:
        return None
    day, month_name, year = match.groups()
    month = _FRENCH_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def coerce_partial_date(value: Any) -> Any:
    """Tolerates the date shapes LLMs actually produce for CV/TDR fields:
    month- or year-only precision ("2016-01", "2016"), day/month/year with
    slashes or dashes, French-written dates ("28 août 2024"), words for an
    ongoing role/certification ("présent", "current"), and the literal
    string "null" (observed live — some models stringify a missing value
    instead of emitting real JSON null) — all resolve to a real date or
    None.

    Falls back to None (not the original string) when nothing matches —
    TDRs sometimes describe a deadline as a relative duration ("07 jours
    ouvrables à partir de la date de démarrage du projet") rather than a
    calendar date at all. Leaving that string for Pydantic to reject would
    crash the whole extraction over a single optional field; treating an
    unparseable value as "we don't actually know" doesn't.
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

    return _parse_french_date(text)
