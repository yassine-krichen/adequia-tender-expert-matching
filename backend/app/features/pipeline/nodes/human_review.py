from typing import Any

from langgraph.types import interrupt

from app.domain.matching import ReviewDecision
from app.features.pipeline.state import PipelineState


async def human_review(state: PipelineState) -> dict[str, Any]:
    """ADQ-24. Pauses the run via interrupt() -- the checkpointer persists
    everything computed so far, and a later `ainvoke(Command(resume=...))`
    from a different process (the API's submit_review) resumes here with
    the reviewer's decision. No factory needed, unlike every other node:
    interrupt() closes over nothing.

    Runs uniformly for both hard-filter-pass and hard-filter-fail branches
    (both already converge on generate_report before this node) -- a
    reviewer can override a hard-filter rejection, so
    overridden_to_approve must stay reachable for failed candidates too.
    """
    resume_value = interrupt(
        {
            "compatibility_score": state["compatibility_score"],
            "hard_filter_passed": state["hard_filter_passed"],
            "hard_filter_failures": state["hard_filter_failures"],
            "rationale": state["rationale"],
            "anomalies": [a.model_dump(mode="json") for a in state["anomalies"]],
        }
    )
    return {"reviewer_decision": ReviewDecision(resume_value["decision"])}
