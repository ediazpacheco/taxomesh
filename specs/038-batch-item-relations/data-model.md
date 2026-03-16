# Data Model: Batch Item Relation Lookup

**Feature**: 038-batch-item-relations

---

## No New Domain Models

This feature introduces no new domain entities. All data is represented by existing models.

---

## Affected Existing Models

### `ItemRelationLink`

**File**: `taxomesh/domain/models/item_relation_link.py`

No changes to this model. Used as the return type of the new repository method.

| Field | Type | Notes |
|-------|------|-------|
| `source_item_id` | `UUID` | The item the relation originates from |
| `target_item_id` | `UUID` | The item the relation points to |
| `relation_type` | `str` (max 256) | Normalized to lowercase; stored and queried as-is |
| `sort_index` | `int` | Controls display order within a (source, relation_type) group; default 0 |
| `metadata` | `dict[str, Any]` | Arbitrary key-value metadata |

**Ordering in batch method**: `(source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC)`

---

### `Item`

**File**: `taxomesh/domain/models/item.py`

No changes to this model. Used as the resolved target in the service batch method.

| Field | Type | Notes |
|-------|------|-------|
| `item_id` | `UUID` | Primary key |
| `name` | `str` (max configured) | Display name |
| `external_id` | `str` | Optional external reference |
| `slug` | `str` | URL-safe identifier |
| `enabled` | `bool` | Active/inactive flag |
| `metadata` | `dict[str, Any]` | Arbitrary metadata |

---

## New Protocol Method Signature

**Added to**: `taxomesh/ports/repository.py` → `TaxomeshRepositoryBase`

```python
def list_item_relation_links_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]:
    """Return outgoing relation links for many source items.

    Only outgoing links (source_item_id in source_item_ids) are returned.
    If relation_types is provided and non-empty, only links whose
    relation_type matches one of the given (already-normalised) values
    are returned. Results are ordered by:
    (source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC).

    Args:
        source_item_ids: Collection of source item UUIDs to query.
            Caller guarantees uniqueness; empty collection returns [].
        relation_types: Optional filter; if non-empty only links with a
            matching relation_type are returned. None or [] means no filter.

    Returns:
        List of matching ItemRelationLink objects in deterministic order;
        empty list if source_item_ids is empty or no links match.
    """
    ...
```

---

## New Service Method Signature

**Added to**: `taxomesh/application/service.py` → `TaxomeshService`

```python
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> dict[UUID, dict[str, list[Item]]]:
    """Return related items grouped by source item ID and relation type.

    Only outgoing relations are considered. Source item IDs with no
    matching links are omitted from the result.

    Args:
        source_item_ids: Collection of source item UUIDs to query.
            Duplicates are silently deduplicated.
        relation_types: Optional filter; case-insensitive. If non-empty,
            only links with a matching relation_type are included. None
            or [] means no filter.

    Returns:
        Nested dict: {source_item_id: {relation_type: [Item, ...]}}
        Only source IDs with at least one matching link appear as keys.
        Items within each list are ordered by (sort_index ASC, target_item_id ASC).

    Raises:
        TaxomeshItemNotFoundError: If any target_item_id referenced by a
            link does not exist in the repository.
    """
```

---

## Return Value Shape

```
dict[UUID, dict[str, list[Item]]]

{
    UUID("aaa..."): {
        "music_by": [Item(item_id=UUID("bbb..."), ...), Item(item_id=UUID("ccc..."), ...)],
        "interpreted_by": [Item(item_id=UUID("ddd..."), ...)],
    },
    UUID("eee..."): {
        "lyrics_by": [Item(item_id=UUID("fff..."), ...)],
    },
}
```

- Top-level keys: only source item IDs that have at least one matching outgoing link.
- Second-level keys: only relation types that have at least one matching link for that source.
- List values: `Item` objects ordered by `(sort_index ASC, target_item_id ASC)`.
