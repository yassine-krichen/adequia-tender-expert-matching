from langgraph.graph import END, StateGraph

from app.features.pipeline.nodes.detect_anomalies import detect_anomalies
from app.features.pipeline.nodes.extract import extract
from app.features.pipeline.nodes.generate_report import generate_report
from app.features.pipeline.nodes.ingest import ingest
from app.features.pipeline.nodes.normalize_skills import normalize_skills
from app.features.pipeline.nodes.score import score
from app.features.pipeline.state import PipelineState


def route_after_hard_filter(state: PipelineState) -> str:
    """A candidate that fails a hard filter still gets a report explaining
    the rejection, but skips scoring and anomaly detection.
    """
    return "detect_anomalies" if state["hard_filter_passed"] else "generate_report"


def build_matching_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("ingest", ingest)
    graph.add_node("extract", extract)
    graph.add_node("normalize_skills", normalize_skills)
    graph.add_node("score", score)
    graph.add_node("detect_anomalies", detect_anomalies)
    graph.add_node("generate_report", generate_report)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "normalize_skills")
    graph.add_edge("normalize_skills", "score")
    graph.add_conditional_edges(
        "score",
        route_after_hard_filter,
        {"detect_anomalies": "detect_anomalies", "generate_report": "generate_report"},
    )
    graph.add_edge("detect_anomalies", "generate_report")
    graph.add_edge("generate_report", END)

    return graph
