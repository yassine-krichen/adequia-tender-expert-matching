from app.features.pipeline.state import PipelineState


def ingest(state: PipelineState) -> PipelineState:
    """Parse raw CV/TDR files into text.

    Route scanned/image documents through OCR instead of plain text
    extraction — confirm on real samples before assuming this is needed
    (docs/08-company-data-checklist.md).
    """
    raise NotImplementedError
