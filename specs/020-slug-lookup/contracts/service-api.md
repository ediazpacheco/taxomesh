# Service API Contract: Slug Lookup Methods (020-slug-lookup)

## `TaxomeshService.get_category_by_slug`

```
get_category_by_slug(slug: str) -> Category
```

**Description**: Return the Category whose `slug` field equals the given string.

**Arguments**:

| Name   | Type  | Required | Notes                        |
|--------|-------|----------|------------------------------|
| `slug` | `str` | yes      | Exact match; case-sensitive  |

**Returns**: The matching `Category` domain object.

**Raises**:

| Exception                        | Condition                                       |
|----------------------------------|-------------------------------------------------|
| `TaxomeshCategoryNotFoundError`  | No category with the given slug exists          |

**Caching**: Result is memoised with `DEFAULT_CACHE_TTL` seconds TTL.
Cache is invalidated automatically on any write operation (`clear_all_caches()`).

**Notes**:
- Read-only; does not modify any repository state.
- Empty slug always raises `TaxomeshCategoryNotFoundError` (no entity is persisted
  with an empty slug).
- The root category (`__root__`) is never returned (it has no slug).

---

## `TaxomeshService.get_item_by_slug`

```
get_item_by_slug(slug: str) -> Item
```

**Description**: Return the Item whose `slug` field equals the given string.

**Arguments**:

| Name   | Type  | Required | Notes                        |
|--------|-------|----------|------------------------------|
| `slug` | `str` | yes      | Exact match; case-sensitive  |

**Returns**: The matching `Item` domain object.

**Raises**:

| Exception                     | Condition                                    |
|-------------------------------|----------------------------------------------|
| `TaxomeshItemNotFoundError`   | No item with the given slug exists           |

**Caching**: Result is memoised with `DEFAULT_CACHE_TTL` seconds TTL.
Cache is invalidated automatically on any write operation (`clear_all_caches()`).

**Notes**:
- Read-only; does not modify any repository state.
- Empty slug always raises `TaxomeshItemNotFoundError`.
