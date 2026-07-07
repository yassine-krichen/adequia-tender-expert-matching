from datetime import date, timedelta

from app.domain.cv import CandidateCV, Certification, Education, Experience
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.score import _cosine_similarity, check_hard_filters


def _cv(
    *,
    degree: str = "Master en Génie Logiciel",
    field: str | None = None,
    total_years_experience: float = 6.0,
    certifications: list[Certification] | None = None,
) -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test Candidate",
        education=[
            Education(degree=degree, field=field, institution="INSAT", source_span="span")
        ],
        certifications=certifications or [],
        experience=[
            Experience(
                title="Chef de projet",
                employer="ST2i",
                sector="Bancaire",
                start_date=date(2018, 1, 1),
                source_span="span",
            )
        ],
        languages=[],
        raw_skills=["Gestion de projet"],
        total_years_experience=total_years_experience,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


def _position(
    *,
    mandatory_diploma: str | None = None,
    minimum_years_experience: float | None = None,
    required_certifications: list[str] | None = None,
) -> ExpertPosition:
    return ExpertPosition(
        position_id="p1",
        position_title="Chef de projet",
        mandatory_diploma=mandatory_diploma,
        minimum_years_experience=minimum_years_experience,
        required_certifications=required_certifications or [],
        source_span="span",
    )


def test_hard_filters_pass_when_no_requirements_set() -> None:
    passed, failures = check_hard_filters(_cv(), _position())

    assert passed is True
    assert failures == []


def test_hard_filter_fails_on_insufficient_years() -> None:
    passed, failures = check_hard_filters(
        _cv(total_years_experience=2.0), _position(minimum_years_experience=5.0)
    )

    assert passed is False
    assert any("Insufficient experience" in f for f in failures)


def test_hard_filter_passes_on_sufficient_years() -> None:
    passed, _ = check_hard_filters(
        _cv(total_years_experience=6.0), _position(minimum_years_experience=5.0)
    )

    assert passed is True


def test_hard_filter_diploma_matches_bac_plus_n_against_degree_level() -> None:
    # "Bac+5" (TDR-side phrasing) should be satisfied by a Master's/
    # Ingénieur degree even though the CV never literally says "Bac+5".
    passed, failures = check_hard_filters(
        _cv(degree="Master en Génie Logiciel"), _position(mandatory_diploma="Bac+5")
    )

    assert passed is True
    assert failures == []


def test_hard_filter_diploma_fails_when_level_too_low() -> None:
    passed, failures = check_hard_filters(
        _cv(degree="Licence en Informatique"), _position(mandatory_diploma="Bac+5")
    )

    assert passed is False
    assert any("Missing mandatory diploma" in f for f in failures)


def test_hard_filter_certification_fails_when_missing() -> None:
    passed, failures = check_hard_filters(_cv(), _position(required_certifications=["PMP"]))

    assert passed is False
    assert any("Missing or expired certification: PMP" in f for f in failures)


def test_hard_filter_certification_fails_when_expired() -> None:
    expired_cert = Certification(
        name="PMP", expiry_date=date.today() - timedelta(days=1), source_span="span"
    )
    passed, failures = check_hard_filters(
        _cv(certifications=[expired_cert]), _position(required_certifications=["PMP"])
    )

    assert passed is False
    assert any("Missing or expired certification: PMP" in f for f in failures)


def test_hard_filter_certification_passes_when_present_and_unexpired() -> None:
    valid_cert = Certification(
        name="PMP", expiry_date=date.today() + timedelta(days=365), source_span="span"
    )
    passed, failures = check_hard_filters(
        _cv(certifications=[valid_cert]), _position(required_certifications=["PMP"])
    )

    assert passed is True
    assert failures == []


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_zero_vector_is_zero_not_a_crash() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
