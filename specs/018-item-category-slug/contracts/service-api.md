# Service API Contracts: Item & Category Slug Field

**Branch**: `018-item-category-slug` | **Date**: 2026-03-01

This document captures the public-facing method contracts introduced or extended
by the slug feature. All methods live on `TaxomeshService`.

---

## Modified Methods

### `create_category`

```python
def create_category(
    self,
    name: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    slug: str = "",          # ← NEW optional parameter
) -> Category:
```

**Contract**:
- `slug=""` (default) → no slug stored; uniqueness not checked.
- `slug=<non-empty>` → uniqueness checked; raises `TaxomeshDuplicateSlugError` if taken.
- Returned `Category.slug` equals the passed `slug`.

---

### `update_category`

```python
def update_category(
    self,
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
    slug: str | None = None,   # ← NEW optional parameter
) -> Category:
```

**Contract**:
- `slug=None` → slug unchanged.
- `slug=""` → slug cleared (set to `""`); always succeeds.
- `slug=<non-empty>` → uniqueness checked against all categories with a different `category_id`; raises `TaxomeshDuplicateSlugError` if taken.
- Setting `slug` to the entity's own current slug → succeeds (no conflict with self).

---

### `create_item`

```python
def create_item(
    self,
    external_id: ExternalId,
    metadata: dict[str, Any] | None = None,
    slug: str = "",           # ← NEW optional parameter
) -> Item:
```

**Contract**: Symmetric with `create_category`. Uniqueness is enforced within the Item namespace (separate from Category).

---

### `update_item`

```python
def update_item(
    self,
    item_id: UUID,
    enabled: bool | None = None,
    slug: str | None = None,  # ← NEW optional parameter
) -> Item:
```

**Contract**: Symmetric with `update_category`.

---

## Repository Protocol Extensions

Two new methods are added to `TaxomeshRepositoryBase`:

```python
def get_item_by_slug(self, slug: str) -> Item | None: ...
def get_category_by_slug(self, slug: str) -> Category | None: ...
```

**Contract** (both):
- Returns the matching entity when exactly one entity has this slug.
- Returns `None` when no entity has this slug.
- MUST NOT be called with `slug=""` for uniqueness-check purposes (the service skips the call when slug is empty).
- Never raises — always returns `Item | None` or `Category | None`.

---

## New Exception

```python
class TaxomeshDuplicateSlugError(TaxomeshValidationError):
    """Raised when a non-empty slug is already used by another entity of the same type."""
```

- Exported from `taxomesh/__init__.py` (via the full exception hierarchy).
- Callers can catch at `TaxomeshValidationError` or more specifically at `TaxomeshDuplicateSlugError`.

---

## `__str__` Canonical Format

### `Category.__str__`

| Condition | Output |
|---|---|
| `slug="books"`, `external_id="cat-42"` | `"books ({category_id}) -> cat-42"` |
| `slug=""`, `external_id="cat-42"` | `"({category_id}) -> cat-42"` |
| `slug="books"`, `external_id=""` | `"books ({category_id})"` |
| `slug=""`, `external_id=""` | `"({category_id})"` |

### `Item.__str__`

| Condition | Output |
|---|---|
| `slug="iphone"`, `external_id="sku-001"` | `"iphone ({item_id}) -> sku-001"` |
| `slug=""`, `external_id="sku-001"` | `"({item_id}) -> sku-001"` |

---

## CLI Graph Output Contract

| Condition | Identifier segment rendered |
|---|---|
| Entity has `slug="my-cat"` | `"my-cat (uuid)"` |
| Entity has `slug=""` | `"uuid"` (bare UUID, no parentheses) |
