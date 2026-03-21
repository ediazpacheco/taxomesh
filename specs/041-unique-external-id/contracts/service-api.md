# Contract: TaxomeshService — External ID API

**Feature**: 041-unique-external-id
**Date**: 2026-03-20

---

## New Methods

### `get_item_by_external_id`

```
get_item_by_external_id(external_id: ExternalId) -> Item | None
```

**Arguments**:
- `external_id: str | int | UUID | None` — the external identifier to look up

**Returns**:
- The matching `Item` instance if exactly one record has this `external_id`
- `None` if no Item matches, or if `external_id` is `None`

**Raises**:
- `TaxomeshRepositoryError` — on storage I/O failure

**Behaviour**:
- `None` input → returns `None` immediately (no repository call)
- UUID / int input → coerced to `str` before lookup
- Result is memoized for `DEFAULT_CACHE_TTL` seconds

---

### `get_category_by_external_id`

```
get_category_by_external_id(external_id: ExternalId) -> Category | None
```

**Arguments**:
- `external_id: str | int | UUID | None` — the external identifier to look up

**Returns**:
- The matching `Category` instance if exactly one non-root record has this `external_id`
- `None` if no Category matches, or if `external_id` is `None`

**Raises**:
- `TaxomeshRepositoryError` — on storage I/O failure

**Behaviour**:
- `None` input → returns `None` immediately (no repository call)
- UUID / int input → coerced to `str` before lookup
- Root category is always excluded from results
- Result is memoized for `DEFAULT_CACHE_TTL` seconds

---

## Removed Methods

The following methods are **removed** and MUST NOT be called after this feature:

- `get_items_by_external_id(external_id: ExternalId) -> list[Item]`
- `get_categories_by_external_id(external_id: ExternalId) -> list[Category]`

---

## New Exception

### `TaxomeshExternalIdConflictError`

Raised by repository `save_item` / `save_category` when a non-None `external_id` is already owned by a different record of the same type.

```
TaxomeshExternalIdConflictError(external_id: str)
```

**Message format**: `"external_id '{value}' is already assigned to another {entity_type}."`

**Hierarchy**: `TaxomeshError → TaxomeshValidationError → TaxomeshExternalIdConflictError`

**Exported from**: `taxomesh.__init__`
