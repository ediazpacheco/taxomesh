# Data Model: 050-related-items-resilience

**Status**: No model changes — this feature modifies service behaviour only.

## Existing entities used (no changes)

### ItemRelationLink (existing — `taxomesh/domain/models/item_relation_link.py`)

| Field | Type | Notes |
|-------|------|-------|
| `source_item_id` | `UUID` | Source of the directed relation |
| `target_item_id` | `UUID` | Target of the directed relation |
| `relation_type` | `str` (max_length bounded) | Normalised to lowercase |
| `sort_index` | `int` (default 0) | Ordering — not used in warning |
| `metadata` | `dict[str, Any]` | Arbitrary — not used in warning |

The natural composite key `(source_item_id, target_item_id, relation_type)` is what
appears in the warning log message.

### TaxomeshItemNotFoundError (existing — `taxomesh/exceptions.py`)

Raised unchanged when `skip_on_error=False` and a dangling link is encountered.
No changes to the exception class or its hierarchy.

## Service signature change

```python
# Before
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> dict[UUID, dict[str, list[Item]]]:

# After
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
    skip_on_error: bool = True,
) -> dict[UUID, dict[str, list[Item]]]:
```

Return type is unchanged. The new parameter is keyword-only with a default — fully
backwards-compatible.
