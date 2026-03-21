# Service API Contract: Item-to-Categories Lookup (045)

**Branch**: `045-item-categories-lookup` | **Date**: 2026-03-21

This document defines the behavioural contract for the new `TaxomeshService.list_categories_by_item` method.

---

## `TaxomeshService.list_categories_by_item`

### Signature

```python
def list_categories_by_item(self, item_id: UUID) -> list[Category]:
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `item_id` | `UUID` | The library-assigned UUID of the item whose category memberships are queried |

### Return value

A `list[Category]` containing every category in which the item has an active placement link.

- The list is ordered **ascending by `ItemParentLink.sort_index`**.
- When two links share the same `sort_index`, relative order between them is **unspecified**.
- Returns `[]` when the item has no category placements.
- **Disabled categories are included**. This is a structural graph read. Filtering by `enabled` is the consumer's responsibility.

### Raises

| Exception | Condition |
|-----------|-----------|
| `TaxomeshItemNotFoundError` | No item with the given `item_id` exists |

No other exceptions are raised by normal use.

### Behaviour invariants

1. If `item_id` does not correspond to any stored item, `TaxomeshItemNotFoundError` is raised before any link traversal.
2. If the item exists but has zero placement links, an empty list is returned.
3. The returned list contains exactly one `Category` per `ItemParentLink` — no deduplication is needed because an item can have at most one link per category (idempotent `place_item_in_category`).
4. Return order respects `sort_index` ascending; ties have undefined relative order.
5. Disabled categories (`category.enabled == False`) appear in the result.
6. The result is memoized for `DEFAULT_CACHE_TTL` seconds. Any of the following calls fully invalidates the cache (global clear): `place_item_in_category`, `remove_item_from_category`, `reorder_items_in_category`.

### Caching behaviour

| Event | Cache effect |
|-------|-------------|
| First call for a given `item_id` | Result computed and cached for TTL seconds |
| Subsequent call within TTL | Cached result returned (no repository access) |
| `place_item_in_category(...)` called | All caches cleared; next call recomputes |
| `remove_item_from_category(...)` called | All caches cleared; next call recomputes |
| `reorder_items_in_category(...)` called | All caches cleared; next call recomputes |

### Example

```python
svc = TaxomeshService()

music = svc.create_category(name="Music")
jazz  = svc.create_category(name="Jazz")
album = svc.create_item(name="Kind of Blue")

svc.place_item_in_category(album.item_id, jazz.category_id,  sort_index=1)
svc.place_item_in_category(album.item_id, music.category_id, sort_index=5)

cats = svc.list_categories_by_item(album.item_id)
# cats[0].name == "Jazz"   (sort_index=1)
# cats[1].name == "Music"  (sort_index=5)
```

---

## Backwards Compatibility

This is a **purely additive** change. No existing public method is modified. No existing caller is affected.

---

## What this contract does NOT define

- Navigation from category to its parents (`list_parent_categories` / `get_category_path`) — out of scope for this feature.
- HTTP/REST exposure of this method — out of scope; may be added in a follow-up.
