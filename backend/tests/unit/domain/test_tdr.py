from datetime import date

from app.domain.tdr import TDR


def test_tdr_accepts_year_precision_deadline_from_the_llm() -> None:
    tdr = TDR(
        tdr_id="tdr-1",
        mission_title="Mission",
        positions=[],
        raw_text="raw",
        source_file_path="tdr.pdf",
        deadline="2026",  # type: ignore[arg-type]
    )

    assert tdr.deadline == date(2026, 1, 1)
