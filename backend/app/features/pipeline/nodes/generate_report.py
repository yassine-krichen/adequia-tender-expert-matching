from app.features.pipeline.state import PipelineState


def generate_report(state: PipelineState) -> PipelineState:
    """Synthesize sub_scores, anomalies, and the match outcome into a cited
    rationale via the stronger routed model. Every factual claim must carry
    a citation into the CV or TDR raw text.
    """
    raise NotImplementedError
