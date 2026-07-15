from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.common.exceptions import DomainError


class UnsupportedDocumentError(DomainError):
    status_code = 422


class CorruptDocumentError(DomainError):
    status_code = 422


def extract_raw_text(file_bytes: bytes, filename: str) -> str:
    """Parse a CV/TDR document (text-PDF or docx) into raw text.

    Corrupt or unsupported files raise a typed DomainError — never a
    silent empty string (ADQ-3).
    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(file_bytes, filename)
    if suffix == ".docx":
        return _extract_docx_text(file_bytes, filename)
    raise UnsupportedDocumentError(f"Unsupported document type: {suffix or 'unknown'}")


def _extract_pdf_text(file_bytes: bytes, filename: str) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except PdfReadError as exc:
        raise CorruptDocumentError(f"Could not read PDF: {filename}") from exc

    if not text:
        raise CorruptDocumentError(f"No extractable text found in PDF: {filename}")
    return text


def _extract_docx_text(file_bytes: bytes, filename: str) -> str:
    try:
        document = Document(BytesIO(file_bytes))
    except (PackageNotFoundError, BadZipFile) as exc:
        raise CorruptDocumentError(f"Could not read DOCX: {filename}") from exc

    text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    if not text:
        raise CorruptDocumentError(f"No extractable text found in DOCX: {filename}")
    return text
