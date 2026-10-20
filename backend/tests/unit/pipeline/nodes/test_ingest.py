from pathlib import Path

import pytest

from app.features.pipeline.nodes.ingest import (
    CorruptDocumentError,
    UnsupportedDocumentError,
    extract_raw_text,
)

_TDRS_DIR = Path(__file__).resolve().parents[5] / "docs" / "tdrs"
_REAL_TDRS = [
    "si-ci-avenant-giz.docx",
    "applicatif-4-modules-st2i.docx",
    "govtech-education-ecosystem.pdf",
]


def test_extract_raw_text_parses_bundled_demo_tdr() -> None:
    filename = "demo-mfpma-plateforme-talents.pdf"
    text = extract_raw_text((_TDRS_DIR / filename).read_bytes(), filename)

    assert len(text.strip()) > 200


# Real tenders are third-party documents and are not distributed with the repo;
# drop them into docs/tdrs/ locally to run these.
@pytest.mark.parametrize("filename", _REAL_TDRS)
def test_extract_raw_text_parses_real_tdr_samples(filename: str) -> None:
    if not (_TDRS_DIR / filename).exists():
        pytest.skip(f"real tender sample {filename} not present")
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
