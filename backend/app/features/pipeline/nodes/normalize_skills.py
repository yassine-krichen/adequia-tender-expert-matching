from app.features.pipeline.state import PipelineState


def normalize_skills(state: PipelineState) -> PipelineState:
    """Embed each raw skill/requirement term and retrieve nearest taxonomy entries.

    Agentic, not one-shot: direct match above threshold accepts; low
    confidence triggers one query-rewrite retry; still-unresolved falls back
    to an LLM judgment call. A reranker pass runs on top-K before accepting.
    """
    raise NotImplementedError
