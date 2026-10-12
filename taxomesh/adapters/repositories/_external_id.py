"""The external-id helpers of the file repositories.

``JsonRepository`` and ``YamlRepository`` use them to keep each external id unique within its kind
and to look up many external ids in one pass. ``DjangoRepository`` has a database ``UNIQUE``
constraint instead.
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
    """Raise ``TaxomeshExternalIdConflictError`` if another row of the same kind has the external id.

    Args:
        entity_id: The identifier of the row being saved. The check skips the stored row with
            this identifier.
        external_id: The external id to check. ``None`` checks nothing.
        collection: Every stored row of the kind, by identifier.
        entity_name: The kind, ``"item"`` or ``"category"``, for the error message.

    Raises:
        TaxomeshExternalIdConflictError: If ``external_id`` is not ``None`` and a row with another
            identifier already has it.
    """
    if external_id is None:
        return
    for existing_id, existing in collection.items():
        if existing_id != entity_id and existing.external_id == external_id:
            raise TaxomeshExternalIdConflictError(
                f"External id {external_id!r} is already used by another {entity_name}"
            )


def bulk_lookup_by_external_id[T: _HasExternalIdAndEnabled](
    collection: Mapping[UUID, T],
    external_ids: Collection[str],
    enabled: bool | None,
) -> dict[str, T]:
    """Return the rows of ``collection`` whose external id is in ``external_ids``.

    Args:
        collection: Every stored row of the kind, by identifier.
        external_ids: The external ids to look up, in stored form, with no duplicates.
        enabled: ``True`` returns only the enabled rows, ``False`` only the disabled ones, and
            ``None`` every matching row.

    Returns:
        A dict from the external id of each matching row to the row. An external id that no row
        has is left out.
    """
    target = set(external_ids)
    result: dict[str, T] = {}
    for entity in collection.values():
        if entity.external_id in target and (enabled is None or entity.enabled == enabled):
            assert entity.external_id is not None
            result[entity.external_id] = entity
    return result
