# Contract: TaxomeshRepositoryBase — External ID Protocol

**Feature**: 041-unique-external-id
**Date**: 2026-03-20

---

## New Protocol Methods

### `get_item_by_external_id`

```
get_item_by_external_id(external_id: str) -> Item | None
```

**Arguments**:
- `external_id: str` — already coerced to `str` by the service layer (never `None` at this level)

**Returns**:
- The matching `Item` if found
- `None` if no Item has this `external_id`

**Raises**:
- `TaxomeshRepositoryError` — on storage failure

---

### `get_category_by_external_id`

```
get_category_by_external_id(external_id: str) -> Category | None
```

**Arguments**:
- `external_id: str` — already coerced to `str` by the service layer

**Returns**:
- The matching `Category` if found (root category MAY be returned here; filtering is the service's responsibility)
- `None` if no Category has this `external_id`

**Raises**:
- `TaxomeshRepositoryError` — on storage failure

---

## Modified Protocol Methods (uniqueness enforcement added)

### `save_item`

**Signature**: unchanged `(item: Item) -> None`

**New behaviour**: MUST raise `TaxomeshExternalIdConflictError` if `item.external_id` is not `None` and another record (different `item_id`) already holds the same `external_id`.

---

### `save_category`

**Signature**: unchanged `(category: Category) -> None`

**New behaviour**: MUST raise `TaxomeshExternalIdConflictError` if `category.external_id` is not `None` and another record (different `category_id`) already holds the same `external_id`.

---

## Removed Protocol Methods

- `list_items_by_external_id(external_id: str) -> list[Item]`
- `list_categories_by_external_id(external_id: str) -> list[Category]`

All three implementations (JSON, YAML, Django) MUST remove these methods.
