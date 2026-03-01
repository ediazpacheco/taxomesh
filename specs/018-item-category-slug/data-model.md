# Data Model: Item & Category Slug Field

**Branch**: `018-item-category-slug` | **Date**: 2026-03-01

---

## New / Modified Entities

### Category (modified)

| Field | Type | Constraints | Default | Notes |
|---|---|---|---|---|
| `category_id` | `UUID` | PK | `uuid4()` | Unchanged |
| `name` | `str` | max 256 chars | — | Unchanged |
| `description` | `str` | max 100 000 chars | `""` | Unchanged |
| `enabled` | `bool` | — | `True` | Unchanged |
| `external_id` | `str` | max 256 chars | `""` | Unchanged |
| **`slug`** | `str` | **max 256 chars** | **`""`** | **New field** |
| `metadata` | `dict[str, Any]` | — | `{}` | Unchanged |

**Uniqueness**: `slug` is unique within the Category namespace when non-empty. Empty string (`""`) is exempt — any number of categories may share `slug=""`.

**`__str__`**: `"{name} (s: {slug} - id: {category_id})"` when `slug` is non-empty; `"{name} (id: {category_id})"` when `slug=""`. The name is always shown; `external_id` is not part of the Category string representation (per FR-006).

---

### Item (modified)

| Field | Type | Constraints | Default | Notes |
|---|---|---|---|---|
| `item_id` | `UUID` | PK | `uuid4()` | Unchanged |
| `external_id` | `str` | max 256 chars | — | Unchanged |
| **`slug`** | `str` | **max 256 chars** | **`""`** | **New field** |
| `enabled` | `bool` | — | `True` | Unchanged |
| `metadata` | `dict[str, Any]` | — | `{}` | Unchanged |

**Uniqueness**: `slug` is unique within the Item namespace when non-empty. Empty string (`""`) is exempt.

**`__str__`**: `"{slug} ({item_id}) -> {external_id}"` where the slug prefix is omitted when `slug=""`.

---

### TaxomeshDuplicateSlugError (new exception)

```
TaxomeshError
└── TaxomeshValidationError
    └── TaxomeshDuplicateSlugError  ← NEW
```

Raised when a `create_*` or `update_*` operation would assign a non-empty slug that is already held by a *different* entity of the same type.

---

## New Named Constants

| Constant | Value | Location | Purpose |
|---|---|---|---|
| `MAX_SLUG_LENGTH` | `256` | `taxomesh.domain.constants` | Single source of truth for slug field max length |
| `DEFAULT_SLUG` | `""` | `taxomesh.domain.constants` | Canonical "no slug" sentinel |

---

## New Repository Methods

Both `get_item_by_slug` and `get_category_by_slug` are added to `TaxomeshRepositoryBase` (Protocol):

| Method | Signature | Return | Semantics |
|---|---|---|---|
| `get_item_by_slug` | `(slug: str) -> Item \| None` | Matching `Item` or `None` | Linear scan (file repos); DB filter (Django) |
| `get_category_by_slug` | `(slug: str) -> Category \| None` | Matching `Category` or `None` | Linear scan (file repos); DB filter (Django) |

These methods return `None` when no entity holds the given slug — they never raise.

---

## Django ORM Schema Changes

### `taxomesh_category` table

```sql
ALTER TABLE taxomesh_category
    ADD COLUMN slug VARCHAR(256) NOT NULL DEFAULT '';

CREATE UNIQUE INDEX taxomesh_category_slug_unique_nonempty
    ON taxomesh_category (slug)
    WHERE slug != '';

CREATE INDEX taxomesh_category_slug_idx
    ON taxomesh_category (slug);
```

### `taxomesh_item` table

```sql
ALTER TABLE taxomesh_item
    ADD COLUMN slug VARCHAR(256) NOT NULL DEFAULT '';

CREATE UNIQUE INDEX taxomesh_item_slug_unique_nonempty
    ON taxomesh_item (slug)
    WHERE slug != '';

CREATE INDEX taxomesh_item_slug_idx
    ON taxomesh_item (slug);
```

Both indexes are captured in `0001_initial.py` (edited in-place). In Django ORM terms:

```python
# Field
slug = models.CharField(max_length=256, blank=True, default="", db_index=True)

# Meta.constraints
models.UniqueConstraint(
    fields=["slug"],
    condition=~models.Q(slug=""),
    name="taxomesh_category_slug_unique_nonempty",  # or taxomesh_item_slug_unique_nonempty
)
```

---

## Slug Uniqueness Invariant (summary)

| Scenario | Outcome |
|---|---|
| Two items with `slug=""` | Allowed — empty is not unique-checked |
| Two categories with `slug=""` | Allowed |
| Item A with `slug="x"` and Item B with `slug="x"` | Raises `TaxomeshDuplicateSlugError` on B |
| Category A with `slug="x"` and Category B with `slug="x"` | Raises `TaxomeshDuplicateSlugError` on B |
| Item with `slug="x"` and Category with `slug="x"` | Allowed — namespaces are separate |
| Update entity to its own current slug | Allowed — same entity, no conflict |
| Update entity to clear slug (`slug=""`) | Always allowed |

---

## Backward Compatibility

The `slug` field defaults to `""` on all existing entities. File-based repositories (JSON, YAML) deserialise existing records without `slug` by Pydantic's default. Django ORM migration adds the column with `DEFAULT ''`. No existing data is modified. All existing tests continue to pass (SC-006).
