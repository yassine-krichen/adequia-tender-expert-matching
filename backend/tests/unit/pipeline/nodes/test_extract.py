from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.common.exceptions import ExtractionFailedError
from app.domain.cv import Education, Experience, LanguageProficiency
from app.features.pipeline.nodes.extract import _CVExtraction, extract_cv


def _sample_extraction() -> _CVExtraction:
    return _CVExtraction(
        full_name="Jane Doe",
        education=[
            Education(
                degree="Master",
                field="Computer Science",
                institution="MIT",
                source_span="Master in Computer Science from MIT",
            )
        ],
        certifications=[],
        experience=[
            Experience(
                title="Engineer",
                employer="Acme",
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
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


class _FakeRouter:
    def __init__(self, responses: Sequence[_CVExtraction | Exception]) -> None:
        self._responses = iter(responses)
        self.call_count = 0

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _CVExtraction:
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


def test_extract_cv_retries_once_on_validation_failure() -> None:
    router = _FakeRouter([_validation_error(), _sample_extraction()])

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
