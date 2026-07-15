from collections.abc import Callable
from typing import Any, TypeVar

from google.genai.errors import ClientError as GeminiClientError
from groq import BadRequestError as GroqBadRequestError
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from app.common.exceptions import ExtractionFailedError

# ValidationError/OutputParserException: our own or LangChain's schema check
# failed. GroqBadRequestError/GeminiClientError: the provider's own strict
# function-calling rejected the generated arguments (e.g. an extra field, a
# malformed value) before it ever reached our validation — by the time one
# of these reaches this tuple it's guaranteed not a 429 (KeyPool/ModelRouter
# already handles rate-limit rotation before anything propagates this far).
_STRUCTURED_OUTPUT_ERRORS = (
    ValidationError,
    OutputParserException,
    GroqBadRequestError,
    GeminiClientError,
)
_M = TypeVar("_M", bound=BaseModel)


def invoke_structured(
    messages: list[BaseMessage],
    schema: type[_M],
    *,
    primary: Callable[..., Any],
    retry: Callable[..., Any],
    failure_message: str,
) -> _M:
    """Escalates to `retry` on a schema-validation failure (feeding the error
    back into the prompt) before wrapping a still-failing extraction into a
    typed DomainError — internal pydantic/langchain error details never
    reach API consumers.

    Retrying with the *same* model rarely helps: verified empirically (see
    extract.py's original docstring for this helper) that a fast/cheap
    extraction-tier model fails a schema's nesting depth consistently while
    a reasoning-tier model succeeds. Callers that are already reasoning-tier
    (e.g. score.py's qualitative judgment) pass the same callable for both
    `primary` and `retry` — a single-tier retry, no escalation needed.
    """
    try:
        result = primary(messages, structured_output=schema)
    except _STRUCTURED_OUTPUT_ERRORS as first_error:
        retry_messages = [
            *messages,
            HumanMessage(
                content=(
                    "Your previous answer failed schema validation with error: "
                    f"{first_error}. Produce a corrected extraction."
                )
            ),
        ]
        try:
            result = retry(retry_messages, structured_output=schema)
        except _STRUCTURED_OUTPUT_ERRORS as second_error:
            raise ExtractionFailedError(failure_message) from second_error
    assert isinstance(result, schema)
    return result
