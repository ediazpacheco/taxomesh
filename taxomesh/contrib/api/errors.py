"""HTTP error mapping for taxomesh exceptions.

Maps the taxomesh exception hierarchy to HTTP status codes and
JSON-serialisable response bodies. Consuming applications call to_tuple()
to translate any TaxomeshError into a (status_code, body) pair without
re-implementing the mapping logic.
"""

from typing import Any, Final

from taxomesh.exceptions import (
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshNotFoundError,
    TaxomeshRepositoryError,
    TaxomeshValidationError,
)

_HTTP_404: Final[int] = 404
_HTTP_409: Final[int] = 409
_HTTP_422: Final[int] = 422
_HTTP_500: Final[int] = 500


def to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]:
    """Map a TaxomeshError to an HTTP (status_code, body) pair.

    The mapping order matters: more-specific subclasses are checked before
    their parents. TaxomeshDuplicateSlugError is a validation subclass but
    maps to 409 (Conflict) rather than 422 (Unprocessable Entity).

    Args:
        exc: Any TaxomeshError instance.

    Returns:
        A tuple of (HTTP status code, body dict with a ``detail`` key).
    """
    body: dict[str, Any] = {"detail": str(exc)}

    if isinstance(exc, TaxomeshDuplicateSlugError):
        return _HTTP_409, body
    if isinstance(exc, TaxomeshNotFoundError):
        return _HTTP_404, body
    if isinstance(exc, TaxomeshValidationError):
        return _HTTP_422, body
    if isinstance(exc, TaxomeshRepositoryError):
        return _HTTP_500, body
    return _HTTP_500, body
