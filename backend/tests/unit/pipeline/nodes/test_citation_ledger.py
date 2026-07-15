from app.domain.cv import NormalizedSkill
from app.domain.matching import Anomaly, AnomalySeverity, AnomalyType
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.citation_ledger import build_citation_ledger
from app.features.pipeline.state import PipelineState


def _position() -> ExpertPosition:
    return ExpertPosition(position_id="p1", position_title="Chef de projet", source_span="span")


def _state(
    *,
    hard_filter_passed: bool = True,
    hard_filter_failures: list[str] | None = None,
    normalized_skills: list[NormalizedSkill] | None = None,
    normalized_position_skills: list[NormalizedSkill] | None = None,
    sector_match_source_span: str | None = None,
    anomalies: list[Anomaly] | None = None,
    qualitative_fit_reasoning: str | None = None,
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
        "compatibility_score": None,
        "qualitative_fit_reasoning": qualitative_fit_reasoning,
        "sector_match_source_span": sector_match_source_span,
        "anomalies": anomalies or [],
        "rationale": None,
        "citations": [],
        "needs_human_review": False,
    }


def _anomaly(
    *,
    type_: AnomalyType = AnomalyType.employment_gap,
    description: str = "Écart détecté.",
    source_citation: str = "span-a\n---\nspan-b",
) -> Anomaly:
    return Anomaly(
        type=type_, severity=AnomalySeverity.warning, description=description, source_citation=source_citation
    )


def test_build_citation_ledger_fail_branch_emits_only_hard_filter_entries_even_when_other_fields_are_populated() -> None:
    # anomalies/sector_match_source_span/qualitative_fit_reasoning are all
    # populated here to prove the fail branch omits them by construction,
    # not by filtering them out after the fact.
    state = _state(
        hard_filter_passed=False,
        hard_filter_failures=["Missing mandatory diploma: Bac+5", "Insufficient experience: 2.0 years"],
        anomalies=[_anomaly()],
        sector_match_source_span="some span",
        qualitative_fit_reasoning="some reasoning",
    )

    ledger = build_citation_ledger(state, taxonomy_names={})

    assert [entry.fact_type for entry in ledger] == ["hard_filter_failure", "hard_filter_failure"]
    assert ledger[0].id == "hardfilter-0"
    assert ledger[0].source_span == "Missing mandatory diploma: Bac+5"
    assert ledger[1].id == "hardfilter-1"
    assert ledger[1].source_span == "Insufficient experience: 2.0 years"


def test_build_citation_ledger_pass_branch_includes_matched_skill_entry_with_taxonomy_name() -> None:
    matched = NormalizedSkill(raw_term="gp", canonical_id="skill-1", confidence=0.9, matched_via="direct")
    state = _state(
        hard_filter_passed=True, normalized_skills=[matched], normalized_position_skills=[matched]
    )

    ledger = build_citation_ledger(state, taxonomy_names={"skill-1": "Gestion de projet"})

    matched_entries = [entry for entry in ledger if entry.fact_type == "skill_matched"]
    assert len(matched_entries) == 1
    assert matched_entries[0].id == "skill-matched-0"
    assert "Gestion de projet" in matched_entries[0].text


def test_build_citation_ledger_pass_branch_includes_missing_skill_entry_for_unmatched_required_skill() -> None:
    required = NormalizedSkill(raw_term="scrum", canonical_id="skill-2", confidence=0.9, matched_via="direct")
    state = _state(hard_filter_passed=True, normalized_skills=[], normalized_position_skills=[required])

    ledger = build_citation_ledger(state, taxonomy_names={"skill-2": "Scrum"})

    missing_entries = [entry for entry in ledger if entry.fact_type == "skill_missing"]
    assert len(missing_entries) == 1
    assert missing_entries[0].id == "skill-missing-0"
    assert "Scrum" in missing_entries[0].text


def test_build_citation_ledger_pass_branch_includes_sector_match_entry_citing_the_winning_span() -> None:
    state = _state(hard_filter_passed=True, sector_match_source_span="A travaillé dans le secteur bancaire.")

    ledger = build_citation_ledger(state, taxonomy_names={})

    sector_entries = [entry for entry in ledger if entry.fact_type == "sector_match"]
    assert len(sector_entries) == 1
    assert sector_entries[0].id == "sector-0"
    assert sector_entries[0].source_span == "A travaillé dans le secteur bancaire."


def test_build_citation_ledger_pass_branch_omits_sector_match_entry_when_no_source_span() -> None:
    state = _state(hard_filter_passed=True, sector_match_source_span=None)

    ledger = build_citation_ledger(state, taxonomy_names={})

    assert not any(entry.fact_type == "sector_match" for entry in ledger)


def test_build_citation_ledger_pass_branch_includes_one_entry_per_anomaly_with_source_citation_copied() -> None:
    anomaly = _anomaly(description="Écart de 120 jours détecté.", source_citation="span-1\n---\nspan-2")
    state = _state(hard_filter_passed=True, anomalies=[anomaly])

    ledger = build_citation_ledger(state, taxonomy_names={})

    anomaly_entries = [entry for entry in ledger if entry.fact_type == "anomaly"]
    assert len(anomaly_entries) == 1
    assert anomaly_entries[0].id == "anomaly-0"
    assert anomaly_entries[0].text == "Écart de 120 jours détecté."
    assert anomaly_entries[0].source_span == "span-1\n---\nspan-2"


def test_build_citation_ledger_pass_branch_includes_qualitative_assessment_entry_when_present() -> None:
    state = _state(hard_filter_passed=True, qualitative_fit_reasoning="Bonne expérience sectorielle.")

    ledger = build_citation_ledger(state, taxonomy_names={})

    qualitative_entries = [entry for entry in ledger if entry.fact_type == "qualitative_assessment"]
    assert len(qualitative_entries) == 1
    assert qualitative_entries[0].id == "qualitative-0"
    assert qualitative_entries[0].text == "Bonne expérience sectorielle."


def test_build_citation_ledger_pass_branch_omits_qualitative_assessment_entry_when_none() -> None:
    state = _state(hard_filter_passed=True, qualitative_fit_reasoning=None)

    ledger = build_citation_ledger(state, taxonomy_names={})

    assert not any(entry.fact_type == "qualitative_assessment" for entry in ledger)
