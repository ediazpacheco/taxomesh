"""Shared external_id uniqueness helper for file-backed repositories.

Used by JsonRepository and YAMLRepository to enforce the 1:1 constraint
in-process. DjangoRepository uses a database UNIQUE constraint instead.
"""

from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from taxomesh.exceptions import TaxomeshExternalIdConflictError


class _HasExternalId(Protocol):
    external_id: str | None


def check_external_id_unique(
    entity_id: UUID,
    external_id: str | None,
    collection: Mapping[UUID, _HasExternalId],
    entity_name: str,
) -> None:
    """Raise TaxomeshExternalIdConflictError if external_id is already held by a different record.

    Args:
        entity_id: Primary key of the entity being saved (excluded from the scan).
        external_id: The external_id to check. No-op when None.
        collection: All existing records keyed by their primary key UUID.
        entity_name: Human-readable entity type ("item" or "category") used in the error message.

    Raises:
        TaxomeshExternalIdConflictError: If another record (different primary key) already
            holds the same non-None external_id.
    """
    if external_id is None:
        return
    for existing_id, existing in collection.items():
        if existing_id != entity_id and existing.external_id == external_id:
            raise TaxomeshExternalIdConflictError(
                f"external_id {external_id!r} is already assigned to another {entity_name}."
            )
