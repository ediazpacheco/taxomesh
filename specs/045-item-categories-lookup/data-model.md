# Data Model: Item-to-Categories Lookup (045)

**Branch**: `045-item-categories-lookup` | **Date**: 2026-03-21

---

## Existing Entities (unchanged)

This feature introduces no new domain entities and modifies no existing ones.

### Item
**File**: `taxomesh/domain/models/item.py`

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `item_id` | `UUID` | required | library-assigned |
| `name` | `str` | max 256 chars | |
| `external_id` | `str \| None` | max 256 chars, unique | `None` = no external link |
| `slug` | `str` | max 256 chars | `""` = no slug |
| `enabled` | `bool` | | |
| `metadata` | `dict[str, Any]` | | |

### Category
**File**: `taxomesh/domain/models/category.py`

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `category_id` | `UUID` | required | library-assigned |
| `name` | `str` | max 256 chars | required |
| `description` | `str` | max 100 000 chars | |
| `enabled` | `bool` | | may be `False`; not filtered by this method |
| `external_id` | `str \| None` | max 256 chars, unique | |
| `slug` | `str` | max 256 chars | `""` = no slug |
| `metadata` | `dict[str, Any]` | | |

### ItemParentLink
**File**: `taxomesh/domain/models/item_parent_link.py`

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| `item_id` | `UUID` | required | FK → Item |
| `category_id` | `UUID` | required | FK → Category |
| `sort_index` | `int` | required | ordering within the category; drives return order |

**This is the primary structural record** read by `list_categories_by_item`. The method filters all `ItemParentLink` records by `item_id`, sorts by `sort_index` ascending, and maps `category_id` → `Category`.

---

## Traversal Semantics

```
Item ──(ItemParentLink.item_id)──► ItemParentLink ──(ItemParentLink.category_id)──► Category
                                    └─ sort_index (determines return order)
```

- **One-to-many**: a single item may have links to zero, one, or many categories.
- **Structural read**: the method reflects the graph as stored; no filtering by `enabled` state.
- **Ordering**: ascending `sort_index`; ties are unspecified (no secondary sort guaranteed).

---

## State Transitions Affecting This Method

| Operation | Effect |
|-----------|--------|
| `place_item_in_category(item_id, cat_id, sort_index)` | Adds or updates an `ItemParentLink`; category appears in result |
| `remove_item_from_category(item_id, cat_id)` | Removes the `ItemParentLink`; category disappears from result |
| `reorder_items_in_category(cat_id, item_ids_in_order)` | Updates `sort_index` values on links; may change return order |
| `update_category(cat_id, enabled=False)` | Disables category; category still appears in result (no filter) |
| `delete_item(item_id)` | Item and all its links removed; method raises `TaxomeshItemNotFoundError` |

---

## Persistence Compatibility

| Backend | `list_item_parent_links()` | Notes |
|---------|---------------------------|-------|
| `JsonRepository` | ✅ Confirmed present | Returns all stored `ItemParentLink` records |
| `YAMLRepository` | ✅ Confirmed present | Same |
| `DjangoRepository` | ✅ Confirmed present | Same |
| `InMemoryRepository` (test fixture) | ✅ Confirmed present | Same |

No schema or protocol changes required.
