# Data Model: Unique External ID (1:1 Constraint)

**Feature**: 041-unique-external-id
**Date**: 2026-03-20

---

## Domain Model Changes

### Item (taxomesh/domain/models/item.py)

| Field | Before | After |
|---|---|---|
| `external_id` type | `Annotated[str, Field(max_length=256)]` | `Annotated[str \| None, Field(max_length=256)]` |
| `external_id` default | `DEFAULT_ITEM_EXTERNAL_ID` (`""`) | `None` |
| Validator | Coerces `None` → `""`, all others → `str` | Coerces `None` → `None`, all others → `str` |

**Validator after**:
```
_coerce_external_id(v):
  if v is None: return None
  return str(v)
```

**Uniqueness**: enforced at repository layer, not in domain model.

---

### Category (taxomesh/domain/models/category.py)

| Field | Before | After |
|---|---|---|
| `external_id` type | `Annotated[str, Field(max_length=256)]` | `Annotated[str \| None, Field(max_length=256)]` |
| `external_id` default | `DEFAULT_CATEGORY_EXTERNAL_ID` (`""`) | `None` |
| Validator | Coerces all → `str` | Coerces `None` → `None`, all others → `str` |

---

### Constants (taxomesh/domain/constants.py)

| Constant | Before | After |
|---|---|---|
| `DEFAULT_ITEM_EXTERNAL_ID` | `Final[str] = ""` | `Final[str \| None] = None` |
| `DEFAULT_CATEGORY_EXTERNAL_ID` | `Final[str] = ""` | `Final[str \| None] = None` |
| `MAX_EXTERNAL_ID_STR_LENGTH` | `Final[int] = 256` | unchanged |

---

## Django ORM Model Changes

### ItemModel (taxomesh/contrib/django/models.py)

| Attribute | Before | After |
|---|---|---|
| `null` | not set (False) | `True` |
| `blank` | `True` | `True` (unchanged) |
| `default` | `DEFAULT_ITEM_EXTERNAL_ID` (`""`) | `None` |
| `db_index` | `True` | removed (unique implies index) |
| `unique` | not set | `True` |

**Field definition after**:
```
external_id = CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, null=True, blank=True, unique=True, default=None)
```

### CategoryModel (taxomesh/contrib/django/models.py)

Same changes as ItemModel above.

---

## Exception Hierarchy Change

**Added** to `taxomesh/exceptions.py` and exported from `taxomesh/__init__.py`:

```
TaxomeshError
└── TaxomeshValidationError
    ├── TaxomeshCyclicDependencyError
    ├── TaxomeshDuplicateSlugError
    └── TaxomeshExternalIdConflictError  ← NEW
```

**Constructor**: accepts `external_id: str` — the conflicting value. Message format:
`"external_id '{value}' is already assigned to another {entity_type}."`

---

## Django Migration

**File**: `taxomesh/contrib/django/migrations/0008_unique_external_id.py`

**Operations** (in order):
1. `RunPython` — convert `external_id = ""` → `NULL` on both `taxomesh_item` and `taxomesh_category`.
2. `AlterField` — `CategoryModel.external_id`: adds `null=True, unique=True`, removes `db_index=True`.
3. `AlterField` — `ItemModel.external_id`: adds `null=True, unique=True`, removes `db_index=True`.

**Rollback** (`reverse_sql`): convert `NULL` → `""` and restore `db_index=True`.

---

## Repository Protocol Changes

### Removed from `TaxomeshRepositoryBase`

| Method | Removed |
|---|---|
| `list_items_by_external_id(external_id: str) -> list[Item]` | ✓ |
| `list_categories_by_external_id(external_id: str) -> list[Category]` | ✓ |

### Added to `TaxomeshRepositoryBase`

| Method | Signature |
|---|---|
| `get_item_by_external_id` | `(external_id: str) -> Item \| None` |
| `get_category_by_external_id` | `(external_id: str) -> Category \| None` |

Note: Input is `str` (caller must coerce before calling protocol). The service layer handles `ExternalId` coercion.

---

## Service Layer Changes

### Removed from `TaxomeshService`

| Method |
|---|
| `get_items_by_external_id(external_id: ExternalId) -> list[Item]` |
| `get_categories_by_external_id(external_id: ExternalId) -> list[Category]` |

### Added to `TaxomeshService`

| Method | Signature | Notes |
|---|---|---|
| `get_item_by_external_id` | `(external_id: ExternalId) -> Item \| None` | Returns `None` if `external_id is None` |
| `get_category_by_external_id` | `(external_id: ExternalId) -> Category \| None` | Returns `None` if `external_id is None`; root excluded |

Both decorated with `@memoize(DEFAULT_CACHE_TTL)`.
