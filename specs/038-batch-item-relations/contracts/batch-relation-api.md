# Contract: Batch Item Relation API

**Feature**: 038-batch-item-relations
**Layer**: `taxomesh` public library API

---

## Overview

Two new methods are added: one to `TaxomeshRepositoryBase` (protocol contract) and one to `TaxomeshService` (public facade). All existing methods remain unchanged.

---

## Repository Protocol Contract

**Method**: `TaxomeshRepositoryBase.list_item_relation_links_for_sources`

### Signature

```python
def list_item_relation_links_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]:
```

### Contract Rules

| Rule | Description |
|------|-------------|
| Direction | Only outgoing links (`source_item_id IN source_item_ids`) are returned |
| Empty input | `source_item_ids=[]` or `source_item_ids=set()` → returns `[]` immediately |
| Type filter | `relation_types=None` or `relation_types=[]` → no filter; all types returned |
| Type filter | `relation_types=["x", "y"]` → only links with `relation_type in {"x", "y"}` |
| Ordering | `ORDER BY source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC` |
| Normalization | Caller (service) pre-normalizes `relation_types` values; adapter stores/compares as-is |
| Duplicates | Caller guarantees `source_item_ids` has no duplicates; adapter need not deduplicate |

### Implementations Required

| Adapter | File | Strategy |
|---------|------|----------|
| `JsonRepository` | `adapters/repositories/json_repository.py` | In-memory filter over `self._item_relation_links` |
| `YAMLRepository` | `adapters/repositories/yaml_repository.py` | In-memory filter over `self._item_relation_links` |
| `DjangoRepository` | `adapters/repositories/django_repository.py` | Single ORM query: `source_item_id__in=...`, optional `relation_type__in=...`, `order_by(...)` |

---

## Service Facade Contract

**Method**: `TaxomeshService.list_related_items_for_sources`

### Signature

```python
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> dict[UUID, dict[str, list[Item]]]:
```

### Contract Rules

| Rule | Description |
|------|-------------|
| Direction | Only outgoing relations |
| Empty input | `source_item_ids=[]` → returns `{}` without accessing storage |
| Deduplication | Duplicate UUIDs in `source_item_ids` are silently deduplicated before repo call |
| Type normalization | Each value in `relation_types` is stripped and lowercased before passing to repo |
| Type filter (empty) | `relation_types=None` or `relation_types=[]` → no filter |
| Omit empty sources | Source IDs with no matching links do NOT appear as keys in the result |
| Omit empty types | Relation types with no matching items do NOT appear as nested keys |
| Item resolution | All unique `target_item_id` values are resolved in one `list_items()` call |
| Missing target | `TaxomeshItemNotFoundError` raised if a `target_item_id` is not in `list_items()` result |
| Item ordering | Items within each `[relation_type]` list are ordered by `(sort_index ASC, target_item_id ASC)` |
| No memoize | Method is NOT cached (collection args; batch callers build indexes with varying inputs) |

### Logical Equivalence

For any non-empty `source_item_ids`:

```python
batch = service.list_related_items_for_sources(source_item_ids, relation_types=relation_types)

# Must equal:
for sid in deduplicated(source_item_ids):
    items = service.list_related_items(sid, relation_type=relation_types[0])  # if len==1
    # ... grouped by relation_type
```

The batch result is logically equivalent to the union of individual `list_related_items()` calls with direction="outgoing".

---

## Backward Compatibility

The following existing methods are **not modified**:

| Method | Location | Status |
|--------|----------|--------|
| `TaxomeshRepositoryBase.list_item_relation_links` | `ports/repository.py` | Unchanged |
| `TaxomeshService.list_item_relations` | `application/service.py` | Unchanged |
| `TaxomeshService.list_related_items` | `application/service.py` | Unchanged |

---

## Usage Example

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Before (N queries):
for item_id in track_ids:
    related = service.list_related_items(item_id, relation_type="music_by")

# After (1 query):
result = service.list_related_items_for_sources(
    track_ids,
    relation_types=["music_by"],
)
# result: {track_id: {"music_by": [Item(...), ...]}, ...}
```
