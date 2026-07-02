from pathlib import Path
from typing import cast

import pytest

from app.features.pipeline.nodes.ingest import (
    CorruptDocumentError,
    UnsupportedDocumentError,
    extract_raw_text,
    ingest,
)
from app.features.pipeline.state import PipelineState

_TDRS_DIR = Path(__file__).resolve().parents[5] / "docs" / "tdrs"
_REAL_TDRS = [
    "2. TDR Mise en place du SI CI_Avenant contrat_V2.docx",
    "DP _  Developpement de Applicatif avec 4 modules-revu TAM-ST2I (5).docx",
    "TDR (8).pdf",
]


@pytest.mark.parametrize("filename", _REAL_TDRS)
def test_extract_raw_text_parses_real_tdr_samples(filename: str) -> None:
    file_bytes = (_TDRS_DIR / filename).read_bytes()

    text = extract_raw_text(file_bytes, filename)

    assert len(text.strip()) > 200


def test_extract_raw_text_raises_on_unsupported_extension() -> None:
    with pytest.raises(UnsupportedDocumentError):
        extract_raw_text(b"hello", "resume.txt")


def test_extract_raw_text_raises_on_corrupt_pdf() -> None:
    with pytest.raises(CorruptDocumentError):
        extract_raw_text(b"not a real pdf", "resume.pdf")


def test_extract_raw_text_raises_on_corrupt_docx() -> None:
    with pytest.raises(CorruptDocumentError):
        extract_raw_text(b"not a real docx", "resume.docx")


def test_ingest_node_passes_through_non_empty_state() -> None:
    state = cast(PipelineState, {"cv_raw_text": "some cv text", "tdr_raw_text": "some tdr text"})

    result = ingest(state)

    assert result == state


def test_ingest_node_raises_on_empty_cv_raw_text() -> None:
    state = cast(PipelineState, {"cv_raw_text": "  ", "tdr_raw_text": "some tdr text"})

    with pytest.raises(CorruptDocumentError):
        ingest(state)
