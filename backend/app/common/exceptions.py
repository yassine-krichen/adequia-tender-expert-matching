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


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
