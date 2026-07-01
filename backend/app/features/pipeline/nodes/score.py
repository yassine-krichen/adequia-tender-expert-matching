from app.features.pipeline.state import PipelineState


def score(state: PipelineState) -> PipelineState:
    """Hybrid scoring: hard filters, then weighted embedding similarity,
    then LLM judgment for qualitative criteria, then memory calibration
    against historical_decisions. See docs/03-agent-pipeline.md node 4.
    """
    raise NotImplementedError
