# Contract: Service Layer Python API (003-service-repository)

**Type**: Python library public import contract
**Date**: 2026-02-22
**Layer**: `taxomesh` (public surface), `taxomesh.ports.repository` (advanced users)

---

## Primary Import Surface

```python
from taxomesh import (
    TaxomeshService,
    # Exceptions — catch any of these
    TaxomeshError,
    TaxomeshNotFoundError,
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
    TaxomeshCyclicDependencyError,
    TaxomeshRepositoryError,
)
```

`JsonRepository` is NOT re-exported from `taxomesh`. Consumers who need to configure it
explicitly (e.g., to set a custom file path) import it directly:

```python
from taxomesh.adapters.repositories.json_repository import JsonRepository
```

`TaxomeshRepositoryBase` is NOT re-exported from `taxomesh`. Consumers implementing a
custom backend may import it for explicit type annotations:

```python
from taxomesh.ports.repository import TaxomeshRepositoryBase
```

---

## `TaxomeshService` Construction Contract

```python
TaxomeshService(
    repository: TaxomeshRepositoryBase | None = None,
) -> TaxomeshService
```

- `repository=None` → automatically uses `JsonRepository(Path("taxomesh.json"))`.
- Any object that structurally satisfies `TaxomeshRepositoryBase` is accepted.
  Explicit inheritance is NOT required.

---

## Category Operations

### `create_category`

```python
service.create_category(
    name: str,                        # required; max 256 chars
    description: str | None = None,   # optional; max 100 000 chars
    metadata: dict[str, Any] | None = None,  # optional; defaults to {}
) -> Category
```

**Raises**: `pydantic.ValidationError` if `name` or `description` violates length constraints.

---

### `get_category`

```python
service.get_category(
    category_id: UUID,
) -> Category
```

**Raises**: `TaxomeshCategoryNotFoundError` if no category with the given `category_id` exists.

---

### `list_categories`

```python
service.list_categories() -> list[Category]
```

Returns an empty list if no categories exist. Never raises.

---

### `delete_category`

```python
service.delete_category(
    category_id: UUID,
) -> None
```

**Raises**: `TaxomeshCategoryNotFoundError` if no category with the given `category_id` exists.

---

## Item Operations

### `create_item`

```python
service.create_item(
    external_id: ExternalId,                  # UUID | str (≤256 chars) | int
    metadata: dict[str, Any] | None = None,   # optional; defaults to {}
) -> Item
```

Returns an `Item` with a library-assigned `item_id` (UUID). The `external_id` is stored
as-is. **Raises**: `pydantic.ValidationError` if `external_id` is a string longer than 256 chars.

---

### `get_item`

```python
service.get_item(
    item_id: UUID,    # the internal library-assigned identifier
) -> Item
```

**Raises**: `TaxomeshItemNotFoundError` if no item with the given `item_id` exists.

---

### `list_items`

```python
service.list_items() -> list[Item]
```

Returns an empty list if no items exist. Never raises.

---

### `delete_item`

```python
service.delete_item(
    item_id: UUID,
) -> None
```

**Raises**: `TaxomeshItemNotFoundError` if no item with the given `item_id` exists.

---

## Tag Operations

### `create_tag`

```python
service.create_tag(
    name: str,                                # required; max 25 chars
    metadata: dict[str, Any] | None = None,   # optional; defaults to {}
) -> Tag
```

**Raises**: `pydantic.ValidationError` if `name` exceeds 25 characters.

---

### `assign_tag`

```python
service.assign_tag(
    tag_id: UUID,
    item_id: UUID,
) -> None
```

Associates the tag with the item. **Idempotent** — calling with an existing association
succeeds without error. **Raises**: `TaxomeshTagNotFoundError` if the tag does not exist;
`TaxomeshItemNotFoundError` if the item does not exist. Tag existence is validated before
item existence — `TaxomeshTagNotFoundError` is raised first when both are absent.

---

### `remove_tag`

```python
service.remove_tag(
    tag_id: UUID,
    item_id: UUID,
) -> None
```

Removes the association between the tag and the item. If both entities exist but no
association is present, this is a **no-op**. **Raises**: `TaxomeshTagNotFoundError` if the tag
does not exist; `TaxomeshItemNotFoundError` if the item does not exist. Tag existence is
validated before item existence — `TaxomeshTagNotFoundError` is raised first when both are absent.

---

## Category Parent Operations

### `add_category_parent`

```python
service.add_category_parent(
    category_id: UUID,        # the child category's identifier
    parent_id: UUID,          # the proposed parent category's identifier
    sort_index: int = 0,      # sort position among this category's parents
) -> CategoryParentLink
```

Records a parent–child relationship between two existing categories. Validates that both
categories exist and that the proposed link does not create a cycle in the category DAG.

**Raises**:
- `TaxomeshCategoryNotFoundError` if `category_id` or `parent_id` does not exist.
- `TaxomeshCyclicDependencyError` if the proposed link would introduce a cycle (including a self-loop where `category_id == parent_id`).

Cycle detection is performed before any data is persisted: if an error is raised, the graph
is left unchanged.

---

## `JsonRepository` Construction Contract

```python
from taxomesh.adapters.repositories.json_repository import JsonRepository
from pathlib import Path

JsonRepository(
    path: Path | str = Path("taxomesh.json"),
) -> JsonRepository
```

**Raises** `TaxomeshRepositoryError` at construction if:
- The file exists but cannot be parsed as valid storage content.
- The file path is a directory.

Creates the file (and any missing parent directories) if it does not exist.

---

## Error Hierarchy

```
TaxomeshError                                  ← catch-all for any taxomesh error
├── TaxomeshNotFoundError                      ← any entity not found
│   ├── TaxomeshCategoryNotFoundError          ← category_id not found
│   ├── TaxomeshItemNotFoundError              ← item_id not found
│   └── TaxomeshTagNotFoundError               ← tag_id not found
├── TaxomeshValidationError                    ← domain constraint violation
│   └── TaxomeshCyclicDependencyError          ← DAG cycle in add_category_parent
└── TaxomeshRepositoryError                    ← storage I/O / parse failure
```

All exception names carry the `Taxomesh` prefix for unambiguous identification in multi-library codebases.

**Catch at any granularity**:

```python
try:
    service.get_category(some_id)
except TaxomeshCategoryNotFoundError:
    ...  # handle specifically
except TaxomeshError:
    ...  # handle any other library error
```

---

## `TaxomeshRepositoryBase` Advanced Contract

Consumers implementing a custom backend must satisfy all 15 Protocol methods:

| Group | Methods |
|-------|---------|
| Category CRUD | `save_category`, `get_category`, `list_categories`, `delete_category` |
| Item CRUD | `save_item`, `get_item`, `list_items`, `delete_item` |
| Tag CRUD | `save_tag`, `get_tag`, `list_tags` |
| Tag ↔ Item association | `assign_tag`, `remove_tag` |
| Category parent links | `save_category_parent_link`, `list_category_parent_links` |

No inheritance from `TaxomeshRepositoryBase` is required; mypy strict enforces structural compliance.

---

## What This Layer Does NOT Provide

- Tag entity deletion — not in scope for this feature.
- Category/item query by attribute (name, metadata) — future spec.
- Category → item listing or tag → item listing — future spec.
- Referential integrity enforcement — repository concern.
- Async interface — explicitly out of scope.
- Removal of category parent links — future spec.
