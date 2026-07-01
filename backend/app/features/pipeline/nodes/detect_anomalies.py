from app.features.pipeline.state import PipelineState


def detect_anomalies(state: PipelineState) -> PipelineState:
    """Rule-based checks (date overlaps, gaps, expired certs) plus an LLM
    plausibility pass over already-extracted typed fields only — never raw
    text again. Runs only when hard_filter_passed is True.
    """
    raise NotImplementedError
