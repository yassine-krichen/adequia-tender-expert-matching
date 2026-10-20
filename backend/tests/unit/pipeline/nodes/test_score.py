import logging
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage

from app.domain.cv import CandidateCV, Certification, Education, Experience, NormalizedSkill
from app.domain.matching import SubScores
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.score import (
    _QualitativeFitJudgment,
    _combine_compatibility_score,
    _cosine_similarity,
    _sector_score_with_span,
    _skill_score,
    calibrate_against_history,
    check_hard_filters,
    judge_qualitative_fit,
    make_score_node,
    score_soft_criteria,
)
from app.features.pipeline.state import PipelineState


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
        education=[Education(degree=degree, field=field, institution="INSAT", source_span="span")],
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


def _state(
    *,
    cv: CandidateCV | None = None,
    position: ExpertPosition | None = None,
    normalized_skills: list[NormalizedSkill] | None = None,
    normalized_position_skills: list[NormalizedSkill] | None = None,
    required_sector_vector: list[float] | None = None,
    sector: str | None = None,
) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": position if position is not None else _position(),
        "cv_extracted": cv if cv is not None else _cv(),
        "normalized_skills": normalized_skills if normalized_skills is not None else [],
        "normalized_position_skills": (
            normalized_position_skills if normalized_position_skills is not None else []
        ),
        "required_sector_vector": required_sector_vector,
        "sector": sector,
        "hard_filter_passed": None,
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


def _normalized(canonical_id: str | None) -> NormalizedSkill:
    return NormalizedSkill(
        raw_term="term", canonical_id=canonical_id, confidence=1.0, matched_via="direct"
    )


def test_skill_score_is_one_when_position_has_no_required_skills() -> None:
    assert _skill_score([], [_normalized("s1")]) == 1.0


def test_skill_score_is_coverage_ratio_of_matched_canonical_ids() -> None:
    normalized_position_skills = [_normalized("s1"), _normalized("s2")]
    normalized_cv_skills = [_normalized("s1")]

    assert _skill_score(normalized_position_skills, normalized_cv_skills) == 0.5


def test_skill_score_ignores_unmatched_position_requirements() -> None:
    # A required skill with no taxonomy match (canonical_id=None) can never
    # be satisfied by any candidate -- shouldn't crash, just doesn't count.
    normalized_position_skills = [_normalized(None), _normalized("s1")]
    normalized_cv_skills = [_normalized("s1")]

    assert _skill_score(normalized_position_skills, normalized_cv_skills) == 0.5


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "banc" in t.lower() else [0.0, 1.0] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0] if "banc" in text.lower() else [0.0, 1.0]


def _cv_without_sector_data() -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test",
        education=[],
        certifications=[],
        experience=[],
        languages=[],
        raw_skills=[],
        total_years_experience=1.0,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


def test_sector_score_with_span_is_one_with_no_span_when_position_has_no_sector_requirement() -> (
    None
):
    score, span = _sector_score_with_span(
        _cv(), required_sector_vector=None, embeddings=_FakeEmbeddings()
    )

    assert score == 1.0
    assert span is None


def test_sector_score_with_span_is_zero_with_no_span_when_candidate_has_no_sector_data() -> None:
    score, span = _sector_score_with_span(
        _cv_without_sector_data(), required_sector_vector=[1.0, 0.0], embeddings=_FakeEmbeddings()
    )

    assert score == 0.0
    assert span is None


def test_sector_score_with_span_uses_max_similarity_and_returns_winning_experience_span() -> None:
    # _cv()'s only experience entry has sector="Bancaire" -- the fake
    # embeddings map anything containing "banc" to [1.0, 0.0], an exact
    # match against the required vector.
    score, span = _sector_score_with_span(
        _cv(), required_sector_vector=[1.0, 0.0], embeddings=_FakeEmbeddings()
    )

    assert score == 1.0
    assert span == "span"


def test_score_soft_criteria_returns_sub_scores_and_the_winning_sector_span() -> None:
    normalized_position_skills = [_normalized("s1")]
    normalized_cv_skills = [_normalized("s1")]

    sub_scores, sector_match_source_span = score_soft_criteria(
        _cv(),
        normalized_cv_skills,
        normalized_position_skills,
        [1.0, 0.0],
        embeddings=_FakeEmbeddings(),
    )

    assert isinstance(sub_scores, SubScores)
    assert sub_scores.skill_score == 1.0
    assert sub_scores.sector_score == 1.0
    assert sub_scores.qualitative_fit_score is None
    assert sector_match_source_span == "span"


def test_score_soft_criteria_sector_span_is_none_when_no_required_sector_vector() -> None:
    sub_scores, sector_match_source_span = score_soft_criteria(
        _cv(), [], [], None, embeddings=_FakeEmbeddings()
    )

    assert sub_scores.sector_score == 1.0
    assert sector_match_source_span is None


def test_combine_compatibility_score_applies_45_25_30_weighting() -> None:
    sub_scores = SubScores(skill_score=0.8, sector_score=0.6, qualitative_fit_score=0.5)

    result = _combine_compatibility_score(sub_scores)

    assert result == pytest.approx(0.45 * 0.8 + 0.25 * 0.6 + 0.30 * 0.5)


class _FakeReasoningRouter:
    """Fake ExtractionRouter -- only invoke_reasoning is exercised by
    judge_qualitative_fit/calibrate_against_history's callers in this file.
    """

    def __init__(self, response: _QualitativeFitJudgment) -> None:
        self._response = response
        self.messages_sent: Sequence[Any] | None = None
        self.reasoning_call_count = 0

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _QualitativeFitJudgment:
        self.messages_sent = messages
        self.reasoning_call_count += 1
        return self._response

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _QualitativeFitJudgment:
        raise AssertionError("judge_qualitative_fit must not call invoke_extraction")


def test_judge_qualitative_fit_passes_through_score_and_reasoning() -> None:
    canned = _QualitativeFitJudgment(
        qualitative_fit_score=0.75, reasoning="Forte expérience sectorielle."
    )
    router = _FakeReasoningRouter(canned)

    result = judge_qualitative_fit(_cv(), _position(), router=router)

    assert result.qualitative_fit_score == 0.75
    assert result.reasoning == "Forte expérience sectorielle."


def test_judge_qualitative_fit_sends_the_data_only_guardrail_prompt() -> None:
    router = _FakeReasoningRouter(_QualitativeFitJudgment(qualitative_fit_score=0.5, reasoning="x"))

    judge_qualitative_fit(_cv(), _position(), router=router)

    assert router.messages_sent is not None
    system_messages = [m for m in router.messages_sent if isinstance(m, SystemMessage)]
    assert system_messages
    assert any("DATA" in str(m.content) for m in system_messages)


class _FakeMcpSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.call_tool_args: tuple[str, dict[str, Any]] | None = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.call_tool_args = (name, arguments)
        return _FakeToolResult(self._rows)


class _FakeToolResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.structuredContent = {"result": rows}


class _FakeSessionContext:
    def __init__(self, session: _FakeMcpSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeMcpSession:
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeMcpClient:
    """Fake MultiServerMCPClient -- only .session(...) is exercised at
    runtime by calibrate_against_history/make_score_node. MultiServerMCPClient
    is a concrete class (not a Protocol), so mypy can't verify this fake
    structurally the way it can for a Protocol; call sites below use a
    scoped `# type: ignore[arg-type]` for that reason.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._session = _FakeMcpSession(rows)
        self.session_calls: list[str] = []

    def session(self, name: str) -> _FakeSessionContext:
        self.session_calls.append(name)
        return _FakeSessionContext(self._session)


class _FailingMcpSession:
    """Simulates a network failure/timeout during call_tool -- exercises
    calibrate_against_history's requirement to never let an MCP failure
    propagate out and fail an entire TDR matching run.
    """

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise ConnectionError("MCP server unreachable")


class _FailingMcpClient:
    def __init__(self) -> None:
        self.session_calls: list[str] = []

    def session(self, name: str) -> _FakeSessionContext:
        self.session_calls.append(name)
        return _FakeSessionContext(_FailingMcpSession())  # type: ignore[arg-type]


async def test_calibrate_against_history_skips_mcp_call_when_sector_is_none() -> None:
    mcp_client = _FakeMcpClient(rows=[])

    await calibrate_against_history(
        _cv(), _position(), 0.7, sector=None, mcp_client=mcp_client  # type: ignore[arg-type]
    )

    assert mcp_client.session_calls == []


async def test_calibrate_against_history_never_raises_on_empty_historical_rows() -> None:
    mcp_client = _FakeMcpClient(rows=[])

    await calibrate_against_history(
        _cv(), _position(), 0.7, sector="Bancaire", mcp_client=mcp_client  # type: ignore[arg-type]
    )

    assert mcp_client.session_calls == ["adequia"]


async def test_calibrate_against_history_logs_a_calibration_note(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mcp_client = _FakeMcpClient(rows=[{"was_selected": True}, {"was_selected": False}])

    with caplog.at_level(logging.INFO, logger="app.features.pipeline.nodes.score"):
        await calibrate_against_history(
            _cv(), _position(), 0.7, sector="Bancaire", mcp_client=mcp_client  # type: ignore[arg-type]
        )

    assert "calibration_note" in caplog.text


class _MalformedToolResult:
    """No structuredContent and an empty content list -- exercises
    _parse_historical_decisions's IndexError on result.content[0], which
    calibrate_against_history must also swallow.
    """

    structuredContent = None
    content: list[Any] = []


class _MalformedMcpSession:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return _MalformedToolResult()


class _MalformedMcpClient:
    def __init__(self) -> None:
        self.session_calls: list[str] = []

    def session(self, name: str) -> _FakeSessionContext:
        self.session_calls.append(name)
        return _FakeSessionContext(_MalformedMcpSession())  # type: ignore[arg-type]


async def test_calibrate_against_history_returns_none_on_malformed_mcp_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mcp_client = _MalformedMcpClient()

    # calibrate_against_history is annotated -> None; the real assertion
    # here is that a malformed response never propagates as an exception.
    with caplog.at_level(logging.WARNING, logger="app.features.pipeline.nodes.score"):
        await calibrate_against_history(
            _cv(), _position(), 0.7, sector="Bancaire", mcp_client=mcp_client  # type: ignore[arg-type]
        )

    assert "calibration_note_failed" in caplog.text


async def test_calibrate_against_history_returns_none_and_logs_a_warning_on_mcp_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mcp_client = _FailingMcpClient()

    # calibrate_against_history is annotated -> None; the real assertion
    # here is that call_tool's ConnectionError never propagates out.
    with caplog.at_level(logging.WARNING, logger="app.features.pipeline.nodes.score"):
        await calibrate_against_history(
            _cv(), _position(), 0.7, sector="Bancaire", mcp_client=mcp_client  # type: ignore[arg-type]
        )

    assert "calibration_note_failed" in caplog.text
    assert mcp_client.session_calls == ["adequia"]


async def test_make_score_node_hard_filter_fail_never_calls_router_or_mcp_client() -> None:
    router = _FakeReasoningRouter(_QualitativeFitJudgment(qualitative_fit_score=0.9, reasoning="x"))
    mcp_client = _FakeMcpClient(rows=[])
    node = make_score_node(
        router=router, mcp_client=mcp_client, embeddings=_FakeEmbeddings()  # type: ignore[arg-type]
    )
    state = _state(
        # cv's degree (Master, level 5) can't satisfy a Bac+8 requirement.
        position=_position(mandatory_diploma="Bac+8"),
        sector="Bancaire",
    )

    result = await node(state)

    assert result["hard_filter_passed"] is False
    assert result["compatibility_score"] is None
    assert result["qualitative_fit_reasoning"] is None
    assert result["sub_scores"].qualitative_fit_score is None
    assert router.messages_sent is None
    assert router.reasoning_call_count == 0
    assert mcp_client.session_calls == []


async def test_make_score_node_hard_filter_pass_calls_router_and_mcp_client_and_combines_score() -> (
    None
):
    matched_skill = NormalizedSkill(
        raw_term="Gestion de projet", canonical_id="s1", confidence=1.0, matched_via="direct"
    )
    router = _FakeReasoningRouter(
        _QualitativeFitJudgment(qualitative_fit_score=0.5, reasoning="Solide profil sectoriel.")
    )
    mcp_client = _FakeMcpClient(rows=[])
    node = make_score_node(
        router=router, mcp_client=mcp_client, embeddings=_FakeEmbeddings()  # type: ignore[arg-type]
    )
    state = _state(
        normalized_skills=[matched_skill],
        normalized_position_skills=[matched_skill],
        required_sector_vector=[1.0, 0.0],
        sector="Bancaire",
    )

    result = await node(state)

    assert result["hard_filter_passed"] is True
    assert result["sub_scores"].qualitative_fit_score == 0.5
    assert result["compatibility_score"] == pytest.approx(0.45 * 1.0 + 0.25 * 1.0 + 0.30 * 0.5)
    assert result["qualitative_fit_reasoning"] == "Solide profil sectoriel."
    assert result["sector_match_source_span"] == "span"
    assert router.reasoning_call_count == 1
    assert mcp_client.session_calls == ["adequia"]
