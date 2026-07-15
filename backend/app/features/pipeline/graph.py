from langchain_core.embeddings import Embeddings
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.llm.router import ExtractionRouter
from app.features.pipeline.nodes.detect_anomalies import make_detect_anomalies_node
from app.features.pipeline.nodes.generate_report import make_generate_report_node
from app.features.pipeline.nodes.normalize_skills import make_normalize_skills_node
from app.features.pipeline.nodes.score import make_score_node
from app.features.pipeline.state import PipelineState


def route_after_hard_filter(state: PipelineState) -> str:
    """A candidate that fails a hard filter still gets a report explaining
    the rejection, but skips scoring and anomaly detection.
    """
    return "detect_anomalies" if state["hard_filter_passed"] else "generate_report"


def build_matching_graph(
    *,
    session: AsyncSession,
    router: ExtractionRouter,
    mcp_client: MultiServerMCPClient,
    embeddings: Embeddings,
) -> StateGraph[PipelineState]:
    graph = StateGraph(PipelineState)

    # mypy can't match a `Callable[[PipelineState], Awaitable[dict[str,
    # Any]]]`-typed value (as opposed to a literal `def`) against
    # StateGraph.add_node's overloaded Node protocol union -- a known
    # mypy/langgraph limitation, not a real type error (each node closure's
    # signature is otherwise exactly what add_node expects).
    graph.add_node(  # type: ignore[call-overload]
        "normalize_skills", make_normalize_skills_node(session=session, embeddings=embeddings)
    )
    graph.add_node(  # type: ignore[call-overload]
        "score", make_score_node(router=router, mcp_client=mcp_client, embeddings=embeddings)
    )
    graph.add_node("detect_anomalies", make_detect_anomalies_node(router=router))  # type: ignore[call-overload]
    graph.add_node("generate_report", make_generate_report_node(session, router))  # type: ignore[call-overload]

    graph.set_entry_point("normalize_skills")
    graph.add_edge("normalize_skills", "score")
    graph.add_conditional_edges(
        "score",
        route_after_hard_filter,
        {"detect_anomalies": "detect_anomalies", "generate_report": "generate_report"},
    )
    graph.add_edge("detect_anomalies", "generate_report")
    graph.add_edge("generate_report", END)

    return graph
