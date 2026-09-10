"""HTTP error mapping for taxomesh exceptions.

Maps the taxomesh exception hierarchy to HTTP status codes and
JSON-serialisable response bodies. Consuming applications call to_tuple()
to translate any TaxomeshError into a (status_code, body) pair without
re-implementing the mapping logic.
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
)

logger = logging.getLogger(__name__)

_HTTP_404: Final[int] = 404
_HTTP_409: Final[int] = 409
_HTTP_422: Final[int] = 422
_HTTP_500: Final[int] = 500

#: The only ``detail`` value a client ever receives for a 500. Public so consuming
#: applications and tests can compare against it instead of duplicating the literal.
GENERIC_SERVER_ERROR_DETAIL: Final[str] = "An internal error occurred."

#: Static log message for a redacted 500. The exception text is carried by ``exc_info``,
#: never interpolated here, so a handler that logs only the formatted message stays safe.
_SERVER_ERROR_LOG_MESSAGE: Final[str] = "Mapping a taxomesh error to HTTP 500"


def to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]:
    """Map a TaxomeshError to an HTTP (status_code, body) pair.

    The mapping order matters: more-specific subclasses are checked before
    their parents. TaxomeshDuplicateSlugError and TaxomeshExternalIdConflictError
    are both validation subclasses but map to 409 (Conflict) rather than 422
    (Unprocessable Entity): both are uniqueness conflicts and surface identically.

    Client errors (404/409/422) carry the exception's own message: it is authored inside
    taxomesh from the caller's own input and is the reason the caller can correct the
    request. Server errors (500) carry GENERIC_SERVER_ERROR_DETAIL instead, because
    TaxomeshRepositoryError wraps the backend's message verbatim — constraint, table and
    column names from the ORM, or the absolute path of a data file. The real exception is
    logged at error level on the "taxomesh" logger rather than discarded.

    Args:
        exc: Any TaxomeshError instance.

    Returns:
        A tuple of (HTTP status code, body dict with a ``detail`` key).
    """
    if isinstance(exc, TaxomeshDuplicateSlugError):
        return _HTTP_409, _client_error_body(exc)
    if isinstance(exc, TaxomeshExternalIdConflictError):
        return _HTTP_409, _client_error_body(exc)
    if isinstance(exc, TaxomeshNotFoundError):
        return _HTTP_404, _client_error_body(exc)
    if isinstance(exc, TaxomeshValidationError):
        return _HTTP_422, _client_error_body(exc)
    if isinstance(exc, TaxomeshRepositoryError):
        return _HTTP_500, _server_error_body(exc)
    return _HTTP_500, _server_error_body(exc)


def _client_error_body(exc: TaxomeshError) -> dict[str, Any]:
    """Build the body for a 4xx: the exception's own, caller-actionable message."""
    return {"detail": str(exc)}


def _server_error_body(exc: TaxomeshError) -> dict[str, Any]:
    """Build the body for a 500 and relocate the real detail to the logger.

    The returned body is independent of *exc*, so nothing about the backend reaches the
    client. ``exc_info`` carries the exception, its traceback, and the chained cause the
    repository adapters attach with ``raise ... from``.
    """
    logger.error(_SERVER_ERROR_LOG_MESSAGE, exc_info=exc)
    return {"detail": GENERIC_SERVER_ERROR_DETAIL}
