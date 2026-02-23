# Data Model: Service Layer and Pluggable Storage (003-service-repository)

**Date**: 2026-02-22
**Source**: `specs/003-service-repository/spec.md` (FR-001 – FR-021)

---

## Layer Map

```
taxomesh/
├── exceptions.py                 ← TaxomeshError hierarchy (cross-cutting)
├── domain/                       ← Existing (unchanged except dag.py added)
│   ├── types.py                  ← ExternalId TypeAlias
│   ├── models.py                 ← Item, Category, Tag, *Link models
│   └── dag.py                   ← check_no_cycle (DAG integrity, Principle VI)
├── ports/
│   └── repository.py             ← TaxomeshRepositoryBase (Protocol, 15 methods)
├── application/
│   └── service.py                ← TaxomeshService
└── adapters/
    └── repositories/
        └── json_repository.py    ← JsonRepository
```

Dependency direction (Principle I): `adapters → application → ports → domain`

---

## Exception Hierarchy (`taxomesh/exceptions.py`)

```
TaxomeshError                              ← base for all library errors
├── TaxomeshNotFoundError                  ← base for all entity-not-found errors
│   ├── TaxomeshCategoryNotFoundError
│   ├── TaxomeshItemNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError                ← domain constraint violations
│   └── TaxomeshCyclicDependencyError      ← DAG cycle detected in add_category_parent
└── TaxomeshRepositoryError                ← storage I/O and parse failures
```

All exception names carry the `Taxomesh` prefix — unambiguous in multi-library codebases.

All exceptions are exported from `taxomesh/__init__.py`.

---

## `TaxomeshRepositoryBase` Protocol (`taxomesh/ports/repository.py`)

A `typing.Protocol` — no `@runtime_checkable`, no inheritance required. Any object that
implements all 15 methods below with compatible signatures is a valid repository.

### Category methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `save_category` | `(self, category: Category) -> None` | `None` | Insert or update |
| `get_category` | `(self, category_id: UUID) -> Category \| None` | `Category` or `None` | `None` if not found |
| `list_categories` | `(self) -> list[Category]` | All stored categories | Empty list if none |
| `delete_category` | `(self, category_id: UUID) -> bool` | `True`=deleted, `False`=not found | |

### Item methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `save_item` | `(self, item: Item) -> None` | `None` | Insert or update |
| `get_item` | `(self, item_id: UUID) -> Item \| None` | `Item` or `None` | `None` if not found |
| `list_items` | `(self) -> list[Item]` | All stored items | Empty list if none |
| `delete_item` | `(self, item_id: UUID) -> bool` | `True`=deleted, `False`=not found | |

### Tag methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `save_tag` | `(self, tag: Tag) -> None` | `None` | Insert or update |
| `get_tag` | `(self, tag_id: UUID) -> Tag \| None` | `Tag` or `None` | `None` if not found |
| `list_tags` | `(self) -> list[Tag]` | All stored tags | Empty list if none |

### Tag ↔ Item association methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `assign_tag` | `(self, tag_id: UUID, item_id: UUID) -> None` | `None` | Idempotent — no-op if association already exists |
| `remove_tag` | `(self, tag_id: UUID, item_id: UUID) -> bool` | `True`=removed, `False`=not found | No error if absent |

`ItemTagLink` is an internal implementation detail of the repository; it is NOT part of the Protocol contract.

### Category parent link methods

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `save_category_parent_link` | `(self, link: CategoryParentLink) -> None` | `None` | Append a new parent link |
| `list_category_parent_links` | `(self) -> list[CategoryParentLink]` | All stored links | Empty list if none |

`CategoryParentLink` is part of the domain model (`taxomesh/domain/models.py`) and IS part of the Protocol contract — it appears in method signatures.

---

## `TaxomeshService` (`taxomesh/application/service.py`)

The single public facade (Principle II). Owns all domain logic; delegates all storage to
the repository.

### Constructor

```
TaxomeshService(repository: TaxomeshRepositoryBase | None = None)
```

- If `repository` is `None`, instantiates `JsonRepository(Path("taxomesh.json"))`.
- Stores the repository as `self._repo`.

### Category operations

| Method | Parameters | Returns | Raises |
|--------|-----------|---------|--------|
| `create_category` | `name: str`, `description: str \| None = None`, `metadata: dict[str, Any] \| None = None` | `Category` | `pydantic.ValidationError` if constraints violated |
| `get_category` | `category_id: UUID` | `Category` | `TaxomeshCategoryNotFoundError` |
| `list_categories` | — | `list[Category]` | — |
| `delete_category` | `category_id: UUID` | `None` | `TaxomeshCategoryNotFoundError` |

### Item operations

| Method | Parameters | Returns | Raises |
|--------|-----------|---------|--------|
| `create_item` | `external_id: ExternalId`, `metadata: dict[str, Any] \| None = None` | `Item` | `pydantic.ValidationError` if constraints violated |
| `get_item` | `item_id: UUID` | `Item` | `TaxomeshItemNotFoundError` |
| `list_items` | — | `list[Item]` | — |
| `delete_item` | `item_id: UUID` | `None` | `TaxomeshItemNotFoundError` |

### Tag operations

| Method | Parameters | Returns | Raises |
|--------|-----------|---------|--------|
| `create_tag` | `name: str`, `metadata: dict[str, Any] \| None = None` | `Tag` | `pydantic.ValidationError` if constraints violated |
| `assign_tag` | `tag_id: UUID`, `item_id: UUID` | `None` | `TaxomeshTagNotFoundError`, `TaxomeshItemNotFoundError` |
| `remove_tag` | `tag_id: UUID`, `item_id: UUID` | `None` | `TaxomeshTagNotFoundError`, `TaxomeshItemNotFoundError` |

**`assign_tag` is idempotent**: if the association already exists, succeeds without error.
**`remove_tag` is a no-op** if both entities exist but no association is present.

### Category parent operations

| Method | Parameters | Returns | Raises |
|--------|-----------|---------|--------|
| `add_category_parent` | `category_id: UUID`, `parent_id: UUID`, `sort_index: int = 0` | `CategoryParentLink` | `TaxomeshCategoryNotFoundError`, `TaxomeshCyclicDependencyError` |

Cycle detection is performed by `taxomesh.domain.dag.check_no_cycle` before the link is persisted.

---

## `JsonRepository` (`taxomesh/adapters/repositories/json_repository.py`)

### Constructor

```
JsonRepository(path: Path | str = Path("taxomesh.json"))
```

- Normalises `path` to `pathlib.Path`.
- If the file does not exist: creates parent directories and writes an empty state document.
- If the file exists but cannot be parsed: raises `TaxomeshRepositoryError`.
- Loads state into memory as four in-memory dicts/lists.

### In-memory state

```python
_categories:             dict[UUID, Category]
_items:                  dict[UUID, Item]
_tags:                   dict[UUID, Tag]
_item_tag_links:         list[ItemTagLink]
_category_parent_links:  list[CategoryParentLink]
```

### JSON file schema

```json
{
  "categories":            { "<uuid-str>": { ...Category fields... } },
  "items":                 { "<uuid-str>": { ...Item fields... } },
  "tags":                  { "<uuid-str>": { ...Tag fields... } },
  "item_tag_links":        [ { "tag_id": "<uuid-str>", "item_id": "<uuid-str>" } ],
  "category_parent_links": [ { "category_id": "<uuid-str>", "parent_category_id": "<uuid-str>", "sort_index": 0 } ]
}
```

All UUID fields are serialised as strings using `model_dump(mode='json')`.
Reconstruction uses `ModelClass.model_validate(data)`.

### Write strategy

After every mutating operation, the full current state is written atomically:
1. Serialise all in-memory state to a JSON string via `model_dump(mode='json')`.
2. Write to a temp file in the same directory as the target (same filesystem = atomic rename).
3. Call `os.fsync(fd)` before closing — flushes OS buffers to disk before rename.
4. Call `os.replace(tmp_path, path)` — POSIX atomic rename; either old or new version
   exists, never a partial/corrupt state.

---

## `taxomesh/__init__.py` — Public Export Surface

```python
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import (
    TaxomeshError,
    TaxomeshNotFoundError,
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
    TaxomeshCyclicDependencyError,
    TaxomeshRepositoryError,
)

__all__ = [
    "TaxomeshService",
    "TaxomeshError",
    "TaxomeshNotFoundError",
    "TaxomeshCategoryNotFoundError",
    "TaxomeshItemNotFoundError",
    "TaxomeshTagNotFoundError",
    "TaxomeshValidationError",
    "TaxomeshCyclicDependencyError",
    "TaxomeshRepositoryError",
]
```

`TaxomeshRepositoryBase` is NOT re-exported from `__init__.py`. Users who need it for
explicit type annotations import it directly:
`from taxomesh.ports.repository import TaxomeshRepositoryBase`
