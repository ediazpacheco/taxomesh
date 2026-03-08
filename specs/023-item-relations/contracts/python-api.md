# Python API Contract: Item-to-Item Relations (023-item-relations)

**Date**: 2026-03-08
**Contract type**: Public Python library API

---

## Domain Model: ItemRelationLink

```python
from taxomesh.domain.models import ItemRelationLink

link = ItemRelationLink(
    source_item_id=UUID("..."),
    target_item_id=UUID("..."),
    relation_type="covers",           # required; non-empty string, max 256 chars
    sort_index=0,                     # optional; integer, default 0
    metadata={"confidence": 0.9},     # optional; JSON-serializable dict, default {}
)
```

**Invariants enforced at construction:**
- `source_item_id != target_item_id` → raises `TaxomeshRelationError`
- `relation_type.strip() != ""` → raises `TaxomeshRelationError`

---

## Service Methods

### relate_items — Create or update a directed relation (upsert)

```python
link: ItemRelationLink = service.relate_items(
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
    *,
    sort_index: int = 0,
    metadata: dict[str, Any] | None = None,
) -> ItemRelationLink
```

**Contract:**
- If a relation with the same `(source_item_id, target_item_id, relation_type)` already
  exists, it is updated with the new `sort_index` and `metadata` (upsert).
- Raises `TaxomeshItemNotFoundError` if either item does not exist.
- Raises `TaxomeshRelationError` if `source_item_id == target_item_id` or `relation_type`
  is empty/whitespace.
- Returns the persisted `ItemRelationLink`.

---

### list_item_relations — Query relations for an item

```python
links: list[ItemRelationLink] = service.list_item_relations(
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[ItemRelationLink]
```

**Contract:**
- `direction="outgoing"` (default): returns links where `source_item_id == item_id`.
- `direction="incoming"`: returns links where `target_item_id == item_id`.
- If `relation_type` is provided, only links with that exact `relation_type` are returned.
- Returns an empty list if no matching relations exist.
- Raises `TaxomeshRelationError` if `direction` is not `"outgoing"` or `"incoming"`.

---

### list_related_items — Return Item objects reachable via relations

```python
items: list[Item] = service.list_related_items(
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[Item]
```

**Contract:**
- Internally calls `list_item_relations` then resolves each linked UUID to an `Item`.
- `direction="outgoing"` returns items that are targets of outgoing relations from `item_id`.
- `direction="incoming"` returns items that are sources of incoming relations to `item_id`.
- If `relation_type` is provided, only relations with that exact type are traversed.
- Returns an empty list if no matching relations exist.
- Raises `TaxomeshRelationError` if `direction` is invalid.

---

### remove_item_relation — Delete a specific directed relation

```python
service.remove_item_relation(
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
) -> None
```

**Contract:**
- Deletes the relation identified by the triple.
- Raises `TaxomeshRelationError` if the relation does not exist.
- Has no effect on other relations between the same items with different `relation_type`.

---

## Exception Contract

All new errors raised by this feature:

| Exception | Parent | When raised |
|-----------|--------|-------------|
| `TaxomeshRelationError` | `TaxomeshValidationError` | Self-relation, empty relation_type, invalid direction, relation not found on delete |

Import path: `from taxomesh import TaxomeshRelationError`

---

## CLI Contract

```
taxomesh relation add <source_item_id> <target_item_id> <relation_type>
    [--sort-index INT]
    [--metadata KEY=VALUE ...]

taxomesh relation list <item_id>
    [--type TEXT]
    [--direction outgoing|incoming]

taxomesh relation related <item_id>
    [--type TEXT]
    [--direction outgoing|incoming]

taxomesh relation delete <source_item_id> <target_item_id> <relation_type>
```

**Exit codes**: 0 on success; non-zero on error (consistent with existing CLI commands).
**Output**: Rich table for `list` and `related`; confirmation message for `add` and `delete`.

---

## Repository Protocol Contract

```python
# All three backends (JsonRepository, YAMLRepository, DjangoRepository) implement:

def save_item_relation_link(self, link: ItemRelationLink) -> None: ...
    # Upsert on (source_item_id, target_item_id, relation_type)

def list_item_relation_links(
    self,
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[ItemRelationLink]: ...

def delete_item_relation_link(
    self,
    source_item_id: UUID,
    target_item_id: UUID,
    relation_type: str,
) -> bool: ...
    # Returns True if deleted, False if not found
```

---

## Public __init__.py Exports (additions)

```python
from taxomesh import TaxomeshRelationError  # new
```

`ItemRelationLink` is NOT re-exported from `__init__.py` (consistent with other domain
models — users import from `taxomesh.domain.models` or via the service return types).
