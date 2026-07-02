from datetime import date

from app.domain.cv import Certification, Education, Experience


def test_experience_accepts_month_precision_dates_from_the_llm() -> None:
    exp = Experience(
        title="Engineer",
        employer="Acme",
        start_date="2016-01",  # type: ignore[arg-type]
        end_date="présent",  # type: ignore[arg-type]
        source_span="span",
    )

    assert exp.start_date == date(2016, 1, 1)
    assert exp.end_date is None


def test_certification_accepts_month_precision_dates_from_the_llm() -> None:
    cert = Certification(
        name="PMP",
        issue_date="2015-03",  # type: ignore[arg-type]
        source_span="span",
    )

    assert cert.issue_date == date(2015, 3, 1)


def test_education_accepts_a_quoted_graduation_year() -> None:
    edu = Education(
        degree="Diplôme d'ingénieur",
        institution="INSAT",
        graduation_year="2008",  # type: ignore[arg-type]
        source_span="span",
    )

    assert edu.graduation_year == 2008


def test_education_field_is_optional() -> None:
    edu = Education(degree="Diplôme d'ingénieur", institution="INSAT", source_span="span")

    assert edu.field is None
