"""Shared external_id helpers for file-backed repositories.

Used by JsonRepository and YAMLRepository to enforce the 1:1 constraint
in-process and to perform bulk lookups. DjangoRepository uses a database
UNIQUE constraint instead.
"""

from collections.abc import Collection, Mapping
from typing import Protocol
from uuid import UUID

from taxomesh.exceptions import TaxomeshExternalIdConflictError


class _HasExternalId(Protocol):
    external_id: str | None


class _HasExternalIdAndEnabled(Protocol):
    external_id: str | None
    enabled: bool


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


def bulk_lookup_by_external_id[T: _HasExternalIdAndEnabled](
    collection: Mapping[UUID, T],
    external_ids: Collection[str],
    enabled: bool | None,
) -> dict[str, T]:
    """Return entities from *collection* whose external_id is in *external_ids*.

    Args:
        collection: All existing records keyed by primary key UUID.
        external_ids: A collection of external ID strings to look up.
            Pre-normalised: no blank strings, no duplicates expected.
        enabled: ``True`` returns only enabled entities; ``False`` only
            disabled; ``None`` returns all matching entities.

    Returns:
        A dict mapping each found external_id to its entity.
    """
    target = set(external_ids)
    result: dict[str, T] = {}
    for entity in collection.values():
        if entity.external_id in target and (enabled is None or entity.enabled == enabled):
            assert entity.external_id is not None
            result[entity.external_id] = entity
    return result
