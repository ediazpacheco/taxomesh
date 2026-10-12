"""The mapping from taxomesh errors to HTTP answers.

:func:`to_tuple` turns any ``TaxomeshError`` into a ``(status_code, body)`` pair, and JSON can
hold the body. An application calls it, and does not write the mapping again.
"""

import logging
from typing import Any, Final

from taxomesh.exceptions import (
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshExternalIdConflictError,
    TaxomeshNotFoundError,
    TaxomeshRepositoryError,
    TaxomeshValidationError,
    TaxomeshVersionConflictError,
)

logger = logging.getLogger(__name__)


class TaxomeshGraphTooLargeError(TaxomeshError):
    """Raised when the serialization of a graph would emit more nodes than ``MAX_EMITTED_NODES``.

    :func:`taxomesh.contrib.api.serializers.graph_to_dict` raises it, and no module of the core
    does, so it is defined here. It is a ``TaxomeshError`` and not a validation error: the request
    is valid, and the stored data is what cannot be rendered. So it is for the operator: it maps to
    HTTP 500, and its message goes to the log and not to the client.
    """


_HTTP_404: Final[int] = 404
_HTTP_409: Final[int] = 409
_HTTP_422: Final[int] = 422
_HTTP_500: Final[int] = 500

#: The errors answered with 409, checked before their validation parent.
_CONFLICTS: Final[tuple[type[TaxomeshError], ...]] = (
    TaxomeshDuplicateSlugError,
    TaxomeshExternalIdConflictError,
    TaxomeshVersionConflictError,
)

#: The one ``detail`` that a client receives for a 500. It is public, so that an application and
#: the tests compare against it and do not copy the literal.
GENERIC_SERVER_ERROR_DETAIL: Final[str] = "An internal error occurred."

#: The log message of a 500, whose detail the client does not see. ``exc_info`` carries the text
#: of the exception, which is never put into this message, so a handler that logs only the
#: formatted message logs no text of the backend.
_SERVER_ERROR_LOG_MESSAGE: Final[str] = "Mapping a taxomesh error to HTTP 500"


# Any: a JSON response body, whose values the consuming app's response serialises.
def to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]:
    """Map a ``TaxomeshError`` to an HTTP ``(status_code, body)`` pair.

    The order of the checks matters: a subclass is checked before its parent.
    ``TaxomeshDuplicateSlugError`` and ``TaxomeshExternalIdConflictError`` are validation errors,
    but they map to 409 (Conflict) and not to 422 (Unprocessable Entity): both are conflicts on a
    unique value, and they get the same status. ``TaxomeshVersionConflictError`` maps to 409 too:
    the stored row changed after the caller read it. To continue, the caller reads the row again
    and updates it with its new version.

    A client error (404, 409 or 422) carries the exception's own message: taxomesh writes it from
    the caller's input, and it tells the caller what to correct. A server error (500) carries
    ``GENERIC_SERVER_ERROR_DETAIL`` instead, because ``TaxomeshRepositoryError`` carries the
    backend's message as it is: the names of a constraint, a table or a column from the ORM, or the
    path of a data file. The exception is logged at level ``ERROR`` on the logger
    ``taxomesh.contrib.api.errors``, which propagates to ``taxomesh``.

    Args:
        exc: The error to map.

    Returns:
        ``(status code, body)``, where the body is a dict with a ``detail`` key.
    """
    if isinstance(exc, _CONFLICTS):
        return _HTTP_409, _client_error_body(exc)
    if isinstance(exc, TaxomeshNotFoundError):
        return _HTTP_404, _client_error_body(exc)
    if isinstance(exc, TaxomeshValidationError):
        return _HTTP_422, _client_error_body(exc)
    if isinstance(exc, TaxomeshRepositoryError):
        return _HTTP_500, _server_error_body(exc)
    return _HTTP_500, _server_error_body(exc)


# Any: a JSON response body, as to_tuple returns it.
def _client_error_body(exc: TaxomeshError) -> dict[str, Any]:
    """Build the body of a 4xx: the exception's own message, which tells the caller what to correct."""
    return {"detail": str(exc)}


# Any: a JSON response body, as to_tuple returns it.
def _server_error_body(exc: TaxomeshError) -> dict[str, Any]:
    """Build the body of a 500, and log the exception.

    The body does not depend on ``exc``, so no text of the backend reaches the client.
    ``exc_info`` carries the exception, its traceback, and the cause that the repository adapters
    chain with ``raise ... from``.
    """
    logger.error(_SERVER_ERROR_LOG_MESSAGE, exc_info=exc)
    return {"detail": GENERIC_SERVER_ERROR_DETAIL}
