import inspect
import logging
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import pytest

from app.domain.cv import CandidateCV, Certification, Education, Experience
from app.domain.matching import AnomalySeverity, AnomalyType
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.detect_anomalies import (
    _PlausibilityAssessment,
    _PlausibilityFinding,
    check_age_at_graduation,
    check_date_overlaps,
    check_employment_gaps,
    check_expired_certifications,
    judge_plausibility,
    make_detect_anomalies_node,
)
from app.features.pipeline.state import PipelineState


def _experience(
    *,
    title: str = "Chef de projet",
    employer: str = "ST2i",
    sector: str | None = "Bancaire",
    start_date: date = date(2018, 1, 1),
    end_date: date | None = date(2019, 1, 1),
    source_span: str = "span",
) -> Experience:
    return Experience(
        title=title,
        employer=employer,
        sector=sector,
        start_date=start_date,
        end_date=end_date,
        source_span=source_span,
    )


def _education(
    *,
    degree: str = "Master en Génie Logiciel",
    graduation_year: int | None = None,
    source_span: str = "edu-span",
) -> Education:
    return Education(
        degree=degree, institution="INSAT", graduation_year=graduation_year, source_span=source_span
    )


def _certification(
    *, name: str = "PMP", expiry_date: date | None = None, source_span: str = "cert-span"
) -> Certification:
    return Certification(name=name, expiry_date=expiry_date, source_span=source_span)


def _cv(
    *,
    birth_date: date | None = None,
    experience: list[Experience] | None = None,
    certifications: list[Certification] | None = None,
    education: list[Education] | None = None,
) -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test Candidate",
        education=education if education is not None else [],
        certifications=certifications or [],
        experience=experience if experience is not None else [],
        languages=[],
        birth_date=birth_date,
        raw_skills=[],
        total_years_experience=1.0,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


def _position() -> ExpertPosition:
    return ExpertPosition(position_id="p1", position_title="Chef de projet", source_span="span")


def _state(*, cv: CandidateCV | None = None, position: ExpertPosition | None = None) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": position if position is not None else _position(),
        "cv_extracted": cv if cv is not None else _cv(),
        "normalized_skills": [],
        "normalized_position_skills": [],
        "required_sector_vector": None,
        "sector": None,
        "hard_filter_passed": True,
        "hard_filter_failures": [],
        "sub_scores": None,
        "compatibility_score": None,
        "qualitative_fit_reasoning": None,
        "sector_match_source_span": None,
        "anomalies": [],
        "rationale": None,
        "citations": [],
        "needs_human_review": False,
        "reviewer_decision": None,
    }


# --- check_employment_gaps ---------------------------------------------


def test_check_employment_gaps_returns_empty_for_adjacent_roles_within_threshold() -> None:
    earlier = _experience(start_date=date(2018, 1, 1), end_date=date(2019, 1, 1))
    later = _experience(start_date=date(2019, 1, 15), end_date=date(2020, 1, 1))

    assert check_employment_gaps([earlier, later]) == []


def test_check_employment_gaps_returns_empty_for_gap_just_under_threshold() -> None:
    earlier = _experience(start_date=date(2018, 1, 1), end_date=date(2019, 1, 1))
    later = _experience(start_date=date(2019, 1, 1) + timedelta(days=89), end_date=date(2020, 1, 1))

    assert check_employment_gaps([earlier, later]) == []


def test_check_employment_gaps_flags_gap_at_or_over_threshold() -> None:
    earlier = _experience(start_date=date(2018, 1, 1), end_date=date(2019, 1, 1))
    later = _experience(start_date=date(2019, 1, 1) + timedelta(days=90), end_date=date(2020, 1, 1))

    anomalies = check_employment_gaps([earlier, later])

    assert len(anomalies) == 1
    assert anomalies[0].type == AnomalyType.employment_gap
    assert anomalies[0].severity == AnomalySeverity.warning


def test_check_employment_gaps_never_flags_a_current_role_as_a_gap_source() -> None:
    # earlier's end_date=None (a current/ongoing role) must never be treated
    # as the start of a gap, however far the next role's start_date is.
    current_role = _experience(start_date=date(2015, 1, 1), end_date=None)
    later = _experience(start_date=date(2020, 1, 1), end_date=date(2021, 1, 1))

    assert check_employment_gaps([current_role, later]) == []


# --- check_date_overlaps -------------------------------------------------


def test_check_date_overlaps_returns_empty_for_non_overlapping_roles() -> None:
    first = _experience(start_date=date(2018, 1, 1), end_date=date(2019, 1, 1))
    second = _experience(start_date=date(2019, 2, 1), end_date=date(2020, 1, 1))

    assert check_date_overlaps([first, second]) == []


def test_check_date_overlaps_returns_empty_for_overlap_within_tolerance() -> None:
    # overlap_start=2020-01-31, overlap_end=2020-03-01 -> 30-day overlap,
    # exactly at (not beyond) the default 30-day tolerance.
    first = _experience(start_date=date(2020, 1, 1), end_date=date(2020, 3, 1))
    second = _experience(start_date=date(2020, 1, 31), end_date=date(2020, 4, 1))

    assert check_date_overlaps([first, second]) == []


def test_check_date_overlaps_flags_overlap_beyond_tolerance() -> None:
    # overlap_start=2020-01-30, overlap_end=2020-03-01 -> 31-day overlap,
    # one day past the default 30-day tolerance.
    first = _experience(start_date=date(2020, 1, 1), end_date=date(2020, 3, 1))
    second = _experience(start_date=date(2020, 1, 30), end_date=date(2020, 4, 1))

    anomalies = check_date_overlaps([first, second])

    assert len(anomalies) == 1
    assert anomalies[0].type == AnomalyType.date_overlap


def test_check_date_overlaps_flags_two_concurrent_current_roles_against_todays_date() -> None:
    today = date.today()
    first = _experience(start_date=today - timedelta(days=400), end_date=None)
    second = _experience(start_date=today - timedelta(days=200), end_date=None)

    anomalies = check_date_overlaps([first, second])

    assert len(anomalies) == 1
    assert anomalies[0].type == AnomalyType.date_overlap


# --- check_expired_certifications ----------------------------------------


def test_check_expired_certifications_returns_empty_when_no_expiry_date() -> None:
    cert = _certification(expiry_date=None)

    assert check_expired_certifications([cert]) == []


def test_check_expired_certifications_returns_empty_for_future_expiry() -> None:
    cert = _certification(expiry_date=date.today() + timedelta(days=30))

    assert check_expired_certifications([cert]) == []


def test_check_expired_certifications_flags_a_past_expiry_date() -> None:
    cert = _certification(expiry_date=date.today() - timedelta(days=1))

    anomalies = check_expired_certifications([cert])

    assert len(anomalies) == 1
    assert anomalies[0].type == AnomalyType.expired_certification


def test_check_expired_certifications_takes_no_position_argument() -> None:
    # Deliberately unlike score.py's _missing_certifications -- this check
    # flags every expired cert regardless of what the position requires.
    parameters = inspect.signature(check_expired_certifications).parameters
    assert "position" not in parameters


# --- check_age_at_graduation ----------------------------------------------


def test_check_age_at_graduation_returns_empty_when_birth_date_is_none() -> None:
    education = [_education(graduation_year=2010)]

    assert check_age_at_graduation(None, education) == []


def test_check_age_at_graduation_returns_empty_when_no_education_has_a_graduation_year() -> None:
    education = [_education(graduation_year=None)]

    assert check_age_at_graduation(date(2000, 1, 1), education) == []


def test_check_age_at_graduation_flags_implausibly_young_graduation_age() -> None:
    education = [_education(graduation_year=2010)]

    anomalies = check_age_at_graduation(date(2000, 1, 1), education)

    assert len(anomalies) == 1
    assert anomalies[0].type == AnomalyType.age_graduation_implausibility


def test_check_age_at_graduation_returns_empty_for_a_plausible_graduation_age() -> None:
    education = [_education(graduation_year=2024)]

    assert check_age_at_graduation(date(2000, 1, 1), education) == []


# --- judge_plausibility ----------------------------------------------------


class _FakeReasoningRouter:
    def __init__(self, response: _PlausibilityAssessment) -> None:
        self._response = response
        self.reasoning_call_count = 0

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _PlausibilityAssessment:
        self.reasoning_call_count += 1
        return self._response

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _PlausibilityAssessment:
        raise AssertionError("judge_plausibility must not call invoke_extraction")


def test_judge_plausibility_maps_each_finding_to_one_anomaly_in_order() -> None:
    experience = [
        _experience(source_span="Directeur de projet chez ST2i, 2018-2019"),
        _experience(source_span="Reconnu comme le meilleur expert du secteur"),
    ]
    assessment = _PlausibilityAssessment(
        findings=[
            _PlausibilityFinding(
                type="title_seniority_mismatch",
                severity="warning",
                description="Le titre ne correspond pas à l'expérience.",
                # Genuine verbatim substrings of the experience source_spans
                # above -- judge_plausibility now drops anything that isn't.
                source_citation="Directeur de projet chez ST2i",
            ),
            _PlausibilityFinding(
                type="unverifiable_claim",
                severity="info",
                description="Affirmation invérifiable.",
                source_citation="le meilleur expert du secteur",
            ),
        ]
    )
    router = _FakeReasoningRouter(assessment)

    anomalies = judge_plausibility(_cv(experience=experience), _position(), router=router)

    assert len(anomalies) == 2
    assert anomalies[0].type == AnomalyType.title_seniority_mismatch
    assert anomalies[0].source_citation == "Directeur de projet chez ST2i"
    assert anomalies[1].type == AnomalyType.unverifiable_claim
    assert anomalies[1].source_citation == "le meilleur expert du secteur"


def test_judge_plausibility_drops_a_finding_whose_citation_is_not_a_genuine_substring() -> None:
    experience = [_experience(source_span="Chef de projet chez ST2i, 2018-2019")]
    assessment = _PlausibilityAssessment(
        findings=[
            _PlausibilityFinding(
                type="unverifiable_claim",
                severity="info",
                description="Affirmation invérifiable.",
                source_citation="Ce texte n'apparaît nulle part dans le CV",
            )
        ]
    )
    router = _FakeReasoningRouter(assessment)

    anomalies = judge_plausibility(_cv(experience=experience), _position(), router=router)

    assert anomalies == []


def test_judge_plausibility_logs_a_warning_when_dropping_a_hallucinated_citation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    experience = [_experience(source_span="Chef de projet chez ST2i, 2018-2019")]
    assessment = _PlausibilityAssessment(
        findings=[
            _PlausibilityFinding(
                type="unverifiable_claim",
                severity="info",
                description="Affirmation invérifiable.",
                source_citation="Ce texte n'apparaît nulle part dans le CV",
            )
        ]
    )
    router = _FakeReasoningRouter(assessment)

    with caplog.at_level(logging.WARNING, logger="app.features.pipeline.nodes.detect_anomalies"):
        judge_plausibility(_cv(experience=experience), _position(), router=router)

    assert "hallucinated_citation" in caplog.text


def test_judge_plausibility_keeps_a_finding_whose_citation_is_a_genuine_verbatim_substring() -> None:
    experience = [_experience(source_span="Chef de projet chez ST2i, 2018-2019")]
    assessment = _PlausibilityAssessment(
        findings=[
            _PlausibilityFinding(
                type="title_seniority_mismatch",
                severity="warning",
                description="Le titre ne correspond pas à l'expérience.",
                source_citation="Chef de projet chez ST2i",
            )
        ]
    )
    router = _FakeReasoningRouter(assessment)

    anomalies = judge_plausibility(_cv(experience=experience), _position(), router=router)

    assert len(anomalies) == 1
    assert anomalies[0].source_citation == "Chef de projet chez ST2i"


def test_judge_plausibility_calls_invoke_reasoning_not_invoke_extraction() -> None:
    router = _FakeReasoningRouter(_PlausibilityAssessment(findings=[]))

    judge_plausibility(_cv(experience=[_experience()]), _position(), router=router)

    assert router.reasoning_call_count == 1


# --- make_detect_anomalies_node --------------------------------------------


async def test_make_detect_anomalies_node_returns_exactly_the_anomalies_key() -> None:
    router = _FakeReasoningRouter(_PlausibilityAssessment(findings=[]))
    node = make_detect_anomalies_node(router=router)
    state = _state(cv=_cv(experience=[_experience()]))

    result = await node(state)

    assert set(result.keys()) == {"anomalies"}


async def test_make_detect_anomalies_node_concatenates_rule_based_findings_before_llm_findings() -> None:
    llm_finding = _PlausibilityFinding(
        type="unverifiable_claim",
        severity="info",
        description="Affirmation invérifiable.",
        source_citation="span",
    )
    router = _FakeReasoningRouter(_PlausibilityAssessment(findings=[llm_finding]))
    gap_experience = [
        _experience(start_date=date(2015, 1, 1), end_date=date(2016, 1, 1)),
        # >90-day gap after the first role's end_date.
        _experience(start_date=date(2017, 1, 1), end_date=date(2018, 1, 1)),
    ]
    node = make_detect_anomalies_node(router=router)
    state = _state(cv=_cv(experience=gap_experience))

    result = await node(state)

    types = [anomaly.type for anomaly in result["anomalies"]]
    assert types == [AnomalyType.employment_gap, AnomalyType.unverifiable_claim]
