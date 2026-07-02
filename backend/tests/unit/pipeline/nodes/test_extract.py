from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from groq import BadRequestError as GroqBadRequestError
from pydantic import ValidationError

from app.common.exceptions import ExtractionFailedError
from app.domain.cv import LanguageProficiency
from app.features.pipeline.nodes.extract import (
    _CVExtraction,
    _ExtractedEducation,
    _ExtractedExperience,
    extract_cv,
)


def _sample_extraction() -> _CVExtraction:
    return _CVExtraction(
        full_name="Jane Doe",
        education=[
            _ExtractedEducation(
                degree="Master",
                field="Computer Science",
                institution="MIT",
                source_span="Master in Computer Science from MIT",
            )
        ],
        certifications=[],
        experience=[
            _ExtractedExperience(
                title="Engineer",
                employer="Acme",
                start_date="2020-01-01",
                end_date="2022-01-01",
                source_span="Engineer at Acme, 2020-2022",
            )
        ],
        languages=[LanguageProficiency(language="English", level="native")],
        raw_skills=["Python", "SQL"],
    )


def _validation_error() -> ValidationError:
    try:
        _CVExtraction.model_validate({})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")


def _groq_bad_request_error() -> GroqBadRequestError:
    """What Groq raises when its own strict function-calling rejects the
    generated tool-call arguments (e.g. an extra field) before it ever
    reaches our Pydantic validation — this must retry too, not 500.
    """
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return GroqBadRequestError("tool_use_failed", response=response, body=None)


class _FakeRouter:
    def __init__(self, responses: Sequence[_CVExtraction | Exception]) -> None:
        self._responses = iter(responses)
        self.call_count = 0
        self.extraction_call_count = 0
        self.reasoning_call_count = 0

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _CVExtraction:
        self.extraction_call_count += 1
        return self._next_response()

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _CVExtraction:
        self.reasoning_call_count += 1
        return self._next_response()

    def _next_response(self) -> _CVExtraction:
        self.call_count += 1
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_extract_cv_builds_candidate_cv_from_extraction() -> None:
    router = _FakeRouter([_sample_extraction()])

    result = extract_cv(
        "raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router
    )

    assert result.candidate_id == "cand-1"
    assert result.source_file_path == "cv.pdf"
    assert result.raw_text == "raw cv text"
    assert result.full_name == "Jane Doe"
    assert result.normalized_skills == []
    assert result.total_years_experience == pytest.approx(2.0, abs=0.1)
    assert router.call_count == 1


def test_extract_cv_accepts_month_precision_and_ongoing_dates_from_the_llm() -> None:
    """Regression: real Groq output used month-precision start_date and
    "présent" for an ongoing role — must resolve into real date objects on
    the final CandidateCV, not get rejected upstream by the provider's own
    strict date-format schema enforcement (see _ExtractedExperience).
    """
    extraction = _CVExtraction(
        full_name="Jane Doe",
        education=[],
        certifications=[],
        experience=[
            _ExtractedExperience(
                title="Engineer",
                employer="Acme",
                start_date="2020-01",
                end_date="présent",
                source_span="span",
            )
        ],
        languages=[],
        raw_skills=[],
    )
    router = _FakeRouter([extraction])

    result = extract_cv(
        "raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router
    )

    assert result.experience[0].start_date.isoformat() == "2020-01-01"
    assert result.experience[0].end_date is None


def test_extract_cv_accepts_unsplit_degree_and_quoted_graduation_year() -> None:
    """Regression: real Groq output sent field=null (degree/field of study
    weren't cleanly separable in the source CV) and graduation_year as a
    quoted string ("2008") — both must resolve without the provider
    rejecting the tool call upstream (see _ExtractedEducation).
    """
    extraction = _CVExtraction(
        full_name="Jane Doe",
        education=[
            _ExtractedEducation(
                degree="Diplôme d'ingénieur en Génie Logiciel",
                field=None,
                institution="INSAT",
                graduation_year="2008",
                source_span="span",
            )
        ],
        certifications=[],
        experience=[],
        languages=[],
        raw_skills=[],
    )
    router = _FakeRouter([extraction])

    result = extract_cv(
        "raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router
    )

    assert result.education[0].field is None
    assert result.education[0].graduation_year == 2008


def test_extract_cv_retries_once_on_validation_failure() -> None:
    router = _FakeRouter([_validation_error(), _sample_extraction()])

    result = extract_cv(
        "raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router
    )

    assert result.full_name == "Jane Doe"
    assert router.call_count == 2


def test_extract_cv_retry_escalates_to_the_reasoning_tier_not_the_same_model() -> None:
    """Regression: retrying with the same extraction-tier model rarely
    helps (verified empirically against real Groq output) — the retry must
    go through invoke_reasoning, not invoke_extraction again.
    """
    router = _FakeRouter([_validation_error(), _sample_extraction()])

    extract_cv("raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router)

    assert router.extraction_call_count == 1
    assert router.reasoning_call_count == 1


def test_extract_cv_retries_once_on_provider_rejected_structured_output() -> None:
    """Regression: a provider-level rejection (Groq's tool_use_failed) must
    go through the same retry-with-feedback path as a schema ValidationError,
    not propagate uncaught into a bare 500.
    """
    router = _FakeRouter([_groq_bad_request_error(), _sample_extraction()])

    result = extract_cv(
        "raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router
    )

    assert result.full_name == "Jane Doe"
    assert router.call_count == 2


def test_extract_cv_raises_extraction_failed_error_after_retry_also_fails() -> None:
    router = _FakeRouter([_validation_error(), _validation_error()])

    with pytest.raises(ExtractionFailedError):
        extract_cv("raw cv text", candidate_id="cand-1", source_file_path="cv.pdf", router=router)

    assert router.call_count == 2


def test_cv_extraction_schema_rejects_a_field_the_llm_invented() -> None:
    """Regression: the LLM previously sent total_years_experience even
    though _CVExtraction doesn't ask for it — extra="forbid" turns that
    into a catchable ValidationError instead of silently accepting it.
    """
    payload = _sample_extraction().model_dump()
    payload["total_years_experience"] = 5.0

    with pytest.raises(ValidationError):
        _CVExtraction.model_validate(payload)
