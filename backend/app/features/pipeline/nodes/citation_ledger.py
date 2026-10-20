from pydantic import BaseModel, ConfigDict

from app.features.pipeline.state import PipelineState


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str  # "skill-matched-0", "sector-0", "anomaly-2", "hardfilter-1", "qualitative-0"
    fact_type: str  # "skill_matched" | "skill_missing" | "sector_match" | "anomaly" | "hard_filter_failure" | "qualitative_assessment"
    text: str  # natural-language rendering, what the LLM is allowed to cite
    source_doc: str  # "cv" | "tdr" | "assessment"
    source_span: str


def build_citation_ledger(
    state: PipelineState, *, taxonomy_names: dict[str, str]
) -> list[LedgerEntry]:
    """ADQ-22. Pure, sync -- taxonomy_names is a pre-resolved
    canonical_id -> canonical_name dict, computed by the caller (a DB lookup)
    so this stays I/O-free and trivially testable with a canned state dict,
    matching score.py's convention of pushing precomputation to the caller.

    Branches on hard_filter_passed: a failed candidate gets only
    hard-filter-failure entries, omitted by construction on the pass branch
    (not filtered post-hoc) -- everything else assumes the candidate was
    actually scored.
    """
    if not state["hard_filter_passed"]:
        return [
            LedgerEntry(
                id=f"hardfilter-{i}",
                fact_type="hard_filter_failure",
                text=failure,
                source_doc="assessment",
                source_span=failure,
            )
            for i, failure in enumerate(state["hard_filter_failures"])
        ]

    entries: list[LedgerEntry] = []
    cv_canonical_ids = {
        skill.canonical_id
        for skill in state["normalized_skills"] or []
        if skill.canonical_id is not None
    }

    matched_index = 0
    missing_index = 0
    for required in state["normalized_position_skills"]:
        name = (
            taxonomy_names.get(required.canonical_id, required.raw_term)
            if required.canonical_id is not None
            else required.raw_term
        )
        if required.canonical_id is not None and required.canonical_id in cv_canonical_ids:
            text = f"Le candidat maîtrise {name}"
            entries.append(
                LedgerEntry(
                    id=f"skill-matched-{matched_index}",
                    fact_type="skill_matched",
                    text=text,
                    source_doc="assessment",
                    source_span=text,
                )
            )
            matched_index += 1
        else:
            text = f"Compétence non retrouvée dans le CV : {name}"
            entries.append(
                LedgerEntry(
                    id=f"skill-missing-{missing_index}",
                    fact_type="skill_missing",
                    text=text,
                    source_doc="assessment",
                    source_span=text,
                )
            )
            missing_index += 1

    if state["sector_match_source_span"] is not None:
        entries.append(
            LedgerEntry(
                id="sector-0",
                fact_type="sector_match",
                text="Expérience dans un secteur pertinent identifiée",
                source_doc="cv",
                source_span=state["sector_match_source_span"],
            )
        )

    for i, anomaly in enumerate(state["anomalies"]):
        entries.append(
            LedgerEntry(
                id=f"anomaly-{i}",
                fact_type="anomaly",
                text=anomaly.description,
                source_doc="cv",
                source_span=anomaly.source_citation,
            )
        )

    if state["qualitative_fit_reasoning"] is not None:
        entries.append(
            LedgerEntry(
                id="qualitative-0",
                fact_type="qualitative_assessment",
                text=state["qualitative_fit_reasoning"],
                source_doc="assessment",
                source_span=state["qualitative_fit_reasoning"],
            )
        )

    return entries
