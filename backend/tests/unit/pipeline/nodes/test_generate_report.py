from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from app.database.models import SkillTaxonomy
from app.domain.cv import NormalizedSkill
from app.domain.matching import Citation
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.citation_ledger import LedgerEntry
from app.features.pipeline.nodes.generate_report import (
    _HARD_FILTER_FAILURE_RATIONALE,
    RationaleClaim,
    RationaleOutput,
    _assemble_citations,
    generate_rationale,
    make_generate_report_node,
)
from app.features.pipeline.state import PipelineState


def _position() -> ExpertPosition:
    return ExpertPosition(position_id="p1", position_title="Chef de projet", source_span="span")


def _state(
    *,
    hard_filter_passed: bool = True,
    hard_filter_failures: list[str] | None = None,
    normalized_skills: list[NormalizedSkill] | None = None,
    normalized_position_skills: list[NormalizedSkill] | None = None,
    compatibility_score: float | None = None,
) -> PipelineState:
    return {
        "cv_raw_text": "raw cv",
        "tdr_raw_text": "raw tdr",
        "position": _position(),
        "cv_extracted": None,
        "normalized_skills": normalized_skills if normalized_skills is not None else [],
        "normalized_position_skills": (
            normalized_position_skills if normalized_position_skills is not None else []
        ),
        "required_sector_vector": None,
        "sector": None,
        "hard_filter_passed": hard_filter_passed,
        "hard_filter_failures": hard_filter_failures or [],
        "sub_scores": None,
        "compatibility_score": compatibility_score,
        "qualitative_fit_reasoning": None,
        "sector_match_source_span": None,
        "anomalies": [],
        "rationale": None,
        "citations": [],
        "needs_human_review": False,
        "reviewer_decision": None,
    }


def _ledger_entry(
    entry_id: str,
    *,
    fact_type: str = "skill_matched",
    text: str = "fact",
    source_doc: str = "cv",
    source_span: str = "span",
) -> LedgerEntry:
    return LedgerEntry(
        id=entry_id, fact_type=fact_type, text=text, source_doc=source_doc, source_span=source_span
    )


# --- _assemble_citations (code-driven, never model-trusted) ---------------


def test_assemble_citations_keeps_sentence_and_citation_for_a_valid_ledger_id() -> None:
    ledger = [_ledger_entry("skill-matched-0", source_doc="cv", source_span="Python confirmé")]
    output = RationaleOutput(
        claims=[RationaleClaim(sentence="Le candidat maîtrise Python.", cited_ledger_ids=["skill-matched-0"])]
    )

    sentences, citations = _assemble_citations(output, ledger)

    assert sentences == ["Le candidat maîtrise Python."]
    assert citations == [
        Citation(claim="Le candidat maîtrise Python.", source_doc="cv", source_span="Python confirmé")
    ]


def test_assemble_citations_drops_sentence_citing_only_a_hallucinated_ledger_id() -> None:
    ledger = [_ledger_entry("skill-matched-0")]
    output = RationaleOutput(
        claims=[RationaleClaim(sentence="Faux fait.", cited_ledger_ids=["does-not-exist"])]
    )

    sentences, citations = _assemble_citations(output, ledger)

    assert sentences == []
    assert citations == []


def test_assemble_citations_mixed_sentence_keeps_only_the_valid_citation() -> None:
    ledger = [_ledger_entry("skill-matched-0", source_doc="cv", source_span="Python confirmé")]
    output = RationaleOutput(
        claims=[
            RationaleClaim(
                sentence="Le candidat maîtrise Python et autre chose.",
                cited_ledger_ids=["skill-matched-0", "hallucinated-id"],
            )
        ]
    )

    sentences, citations = _assemble_citations(output, ledger)

    assert sentences == ["Le candidat maîtrise Python et autre chose."]
    assert len(citations) == 1
    assert citations[0].source_span == "Python confirmé"


def test_assemble_citations_does_not_crash_when_every_cited_id_across_multiple_claims_is_hallucinated() -> None:
    ledger = [_ledger_entry("skill-matched-0")]
    output = RationaleOutput(
        claims=[
            RationaleClaim(sentence="Premier faux fait.", cited_ledger_ids=["ghost-1"]),
            RationaleClaim(sentence="Deuxième faux fait.", cited_ledger_ids=["ghost-2", "ghost-3"]),
        ]
    )

    sentences, citations = _assemble_citations(output, ledger)

    assert sentences == []
    assert citations == []


# --- generate_rationale -----------------------------------------------------


class _FakeReasoningRouter:
    def __init__(self, response: RationaleOutput) -> None:
        self._response = response
        self.messages_sent: Sequence[Any] | None = None

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> RationaleOutput:
        self.messages_sent = messages
        return self._response

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> RationaleOutput:
        raise AssertionError("generate_rationale must not call invoke_extraction")


def test_generate_rationale_returns_the_routers_structured_output() -> None:
    ledger = [
        LedgerEntry(
            id="skill-matched-0",
            fact_type="skill_matched",
            text="Le candidat maîtrise Python",
            source_doc="cv",
            source_span="Python confirmé dans le CV",
        )
    ]
    canned = RationaleOutput(
        claims=[RationaleClaim(sentence="s.", cited_ledger_ids=["skill-matched-0"])]
    )
    router = _FakeReasoningRouter(canned)

    result = generate_rationale(ledger, router=router)

    assert result == canned


def test_generate_rationale_sends_only_ledger_id_fact_type_and_text_never_source_span() -> None:
    ledger = [
        LedgerEntry(
            id="skill-matched-0",
            fact_type="skill_matched",
            text="Le candidat maîtrise Python",
            source_doc="cv",
            source_span="Python confirmé dans le CV -- ceci ne doit jamais être envoyé au LLM",
        )
    ]
    router = _FakeReasoningRouter(RationaleOutput(claims=[]))

    generate_rationale(ledger, router=router)

    assert router.messages_sent is not None
    human_messages = [m for m in router.messages_sent if isinstance(m, HumanMessage)]
    assert len(human_messages) == 1
    payload = str(human_messages[0].content)
    assert "Le candidat maîtrise Python" in payload
    assert "ne doit jamais être envoyé au LLM" not in payload


def test_generate_rationale_guardrail_prompt_forbids_mentioning_ledger_ids_in_prose() -> None:
    router = _FakeReasoningRouter(RationaleOutput(claims=[]))

    generate_rationale([], router=router)

    assert router.messages_sent is not None
    system_messages = [m for m in router.messages_sent if isinstance(m, SystemMessage)]
    assert system_messages
    assert any(
        "Never mention a ledger entry's id" in str(m.content) for m in system_messages
    )


# --- make_generate_report_node ----------------------------------------------


class _FakeExecuteResult:
    def __init__(self, rows: list[SkillTaxonomy]) -> None:
        self._rows = rows

    def scalars(self) -> list[SkillTaxonomy]:
        return self._rows


class _FakeSession:
    def __init__(self, taxonomy_rows: list[SkillTaxonomy]) -> None:
        self._taxonomy_rows = taxonomy_rows

    async def execute(self, stmt: Any) -> _FakeExecuteResult:
        return _FakeExecuteResult(self._taxonomy_rows)


async def test_make_generate_report_node_hard_filter_fail_never_calls_the_router() -> None:
    router = _FakeReasoningRouter(RationaleOutput(claims=[]))
    session = _FakeSession(taxonomy_rows=[])
    node = make_generate_report_node(session, router)  # type: ignore[arg-type]
    state = _state(hard_filter_passed=False, hard_filter_failures=["Missing mandatory diploma: Bac+5"])

    result = await node(state)

    assert router.messages_sent is None
    assert set(result.keys()) == {"rationale", "citations"}
    assert result["rationale"] == _HARD_FILTER_FAILURE_RATIONALE
    assert result["citations"] == [
        Citation(
            claim="Missing mandatory diploma: Bac+5",
            source_doc="assessment",
            source_span="Missing mandatory diploma: Bac+5",
        )
    ]


async def test_make_generate_report_node_hard_filter_fail_is_deterministic_across_repeated_calls() -> None:
    router = _FakeReasoningRouter(RationaleOutput(claims=[]))
    session = _FakeSession(taxonomy_rows=[])
    node = make_generate_report_node(session, router)  # type: ignore[arg-type]
    state = _state(hard_filter_passed=False, hard_filter_failures=["Missing mandatory diploma: Bac+5"])

    first = await node(state)
    second = await node(state)

    assert first == second


async def test_make_generate_report_node_pass_branch_returns_rationale_and_citations() -> None:
    skill_id = uuid4()
    matched_skill = NormalizedSkill(
        raw_term="gp", canonical_id=str(skill_id), confidence=0.9, matched_via="direct"
    )
    taxonomy_row = SkillTaxonomy(skill_id=skill_id, canonical_name="Gestion de projet", aliases=[])
    session = _FakeSession(taxonomy_rows=[taxonomy_row])
    canned = RationaleOutput(
        claims=[
            RationaleClaim(
                sentence="Ce candidat maîtrise la gestion de projet.",
                cited_ledger_ids=["skill-matched-0"],
            )
        ]
    )
    router = _FakeReasoningRouter(canned)
    node = make_generate_report_node(session, router)  # type: ignore[arg-type]
    state = _state(
        hard_filter_passed=True,
        normalized_skills=[matched_skill],
        normalized_position_skills=[matched_skill],
        compatibility_score=0.85,
    )

    result = await node(state)

    assert set(result.keys()) == {"rationale", "citations"}
    assert result["rationale"].startswith(
        "Ce profil correspond à 85% des critères demandés, notamment :"
    )
    assert "Ce candidat maîtrise la gestion de projet." in result["rationale"]
    assert len(result["citations"]) == 1
    assert result["citations"][0].claim == "Ce candidat maîtrise la gestion de projet."


async def test_make_generate_report_node_pass_branch_drops_a_fully_hallucinated_sentence() -> None:
    session = _FakeSession(taxonomy_rows=[])
    canned = RationaleOutput(
        claims=[RationaleClaim(sentence="Fait inventé.", cited_ledger_ids=["does-not-exist"])]
    )
    router = _FakeReasoningRouter(canned)
    node = make_generate_report_node(session, router)  # type: ignore[arg-type]
    state = _state(hard_filter_passed=True, compatibility_score=0.5)

    result = await node(state)

    assert "Fait inventé." not in result["rationale"]
    assert result["citations"] == []
    # Every claim was dropped as hallucinated -- the rationale must not be
    # left with a dangling "notamment :" and nothing after it.
    assert result["rationale"] == "Ce profil correspond à 50% des critères demandés."
    assert not result["rationale"].rstrip().endswith(":")
