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


class AlreadyReviewedError(DomainError):
    """A review decision has already been recorded for this match."""

    status_code = 409


class NoPendingReviewError(DomainError):
    """No paused human_review interrupt exists for this match's thread --
    the checkpoint was never written, or has already been consumed.
    """

    status_code = 409


class EmbeddingBackendUnavailableError(DomainError):
    """The Ollama embedding backend couldn't be reached for a persisted-
    vector call site (CV/skill-taxonomy embeddings, coarse retrieval,
    skill normalization).

    Deliberately NOT retried against a different provider here -- a
    Gemini-produced vector would be numerically valid but semantically
    incomparable against whatever's already stored in Postgres from
    Ollama, which is silent corruption, worse than a hard failure. See
    ModelRouter.get_embedding_model vs. get_transient_embedding_model.
    """

    status_code = 503


class ReviewPersistenceFailedError(DomainError):
    """The LangGraph checkpoint thread was already resumed/completed for
    this match, but writing the decision back to match_results /
    historical_decisions failed afterwards (dropped connection, constraint
    violation, etc).

    The checkpoint and the DB now disagree: the graph considers the review
    done, but match_results.reviewer_decision is still NULL. This is not a
    permanent stuck state -- retrying submit_review with the same decision
    will detect the already-resumed-but-unwritten checkpoint and recover by
    writing the decision straight to the DB, without touching the graph
    again.
    """

    status_code = 500


async def domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
