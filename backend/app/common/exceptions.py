from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for domain-level errors raised by services.

    Services raise typed exceptions; the global handler below maps them to
    HTTP responses so nothing internal leaks to API consumers.
    """

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404


class ValidationFailedError(DomainError):
    status_code = 422


class ExtractionFailedError(DomainError):
    """Structured extraction failed schema validation even after one retry.

    Wraps the underlying pydantic/langchain error so internal validation
    details never leak to API consumers.
    """

    status_code = 422


class ResourceNotReadyError(DomainError):
    """The resource exists but background processing hasn't finished yet.

    e.g. GET /tdrs/{tdr_id} while the worker is still extracting — client
    should be polling GET /tdrs/{tdr_id}/status instead.
    """

    status_code = 409


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
