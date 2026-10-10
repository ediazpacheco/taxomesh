"""Shared version helpers for the repositories.

``JsonRepository`` and ``YamlRepository`` compare the expected version with the stored row and
assign the next version in memory, inside the save that writes the file. ``DjangoRepository``
filters its ``UPDATE`` on the expected version instead, and raises the same error when no row
matches.
"""

from uuid import UUID

from taxomesh.domain.models import Category, Item
from taxomesh.exceptions import TaxomeshVersionConflictError


def version_conflict(entity_name: str, entity_id: UUID, expected_version: int) -> TaxomeshVersionConflictError:
    """Return the error for a save that expected a version the stored row is not at.

    Args:
        entity_name: The kind of the row, ``"category"`` or ``"item"``, for the message.
        entity_id: The row's identifier.
        expected_version: The version the caller read.

    Returns:
        The error to raise.
    """
    return TaxomeshVersionConflictError(
        f"The {entity_name} {entity_id} is not at version {expected_version}: it changed, or was deleted, "
        "after it was read"
    )


def row_to_store[R: (Category, Item)](
    row: R,
    replaced: R | None,
    *,
    expected_version: int | None,
    entity_name: str,
    entity_id: UUID,
) -> R:
    """Return the row a save stores, after comparing the expected version with the stored one.

    The given row is never changed. An insert stores it as it is; an update stores a copy carrying
    the replaced row's version plus one.

    Args:
        row: The row being saved.
        replaced: The row stored under the same identifier, or ``None`` when there is none.
        expected_version: The version the caller read, or ``None`` for no comparison.
        entity_name: The kind of the row, ``"category"`` or ``"item"``, for the message.
        entity_id: The row's identifier.

    Returns:
        The row to store.

    Raises:
        TaxomeshVersionConflictError: If ``expected_version`` is given and no row is stored, or
            the stored row is at another version.
    """
    if expected_version is not None and (replaced is None or replaced.version != expected_version):
        raise version_conflict(entity_name, entity_id, expected_version)
    return row if replaced is None else row.model_copy(update={"version": replaced.version + 1})
