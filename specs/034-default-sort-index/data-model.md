# Data Model: Default sort_index Ordering

**Feature**: 034-default-sort-index
**Date**: 2026-03-15

---

## No Model Changes

This feature introduces **no new fields, no migrations, and no schema changes**.
All sort fields already exist on the relevant domain models. The change is purely
in how collection-returning methods order their return values.

---

## Existing Fields Used for Sorting

### Category (`taxomesh/domain/models/category.py`)
- `name: str` — used as primary sort key for `list_categories()` unfiltered
- `category_id: UUID` — used as secondary (tie-breaker) sort key

### Item (`taxomesh/domain/models/item.py`)
- `name: str` — used as primary sort key for `list_items()` unfiltered
- `item_id: UUID` — used as secondary (tie-breaker) sort key

### CategoryParentLink (`taxomesh/domain/models/category_parent_link.py`)
- `sort_index: int` — primary sort key
- `category_id: UUID` — secondary sort key
- `parent_category_id: UUID` — tertiary sort key

### ItemParentLink (`taxomesh/domain/models/item_parent_link.py`)
- `sort_index: int` — primary sort key
- `item_id: UUID` — secondary sort key
- `category_id: UUID` — tertiary sort key

### ItemRelationLink (`taxomesh/domain/models/item_relation_link.py`)
- `sort_index: int` — primary sort key
- `source_item_id: UUID` — secondary sort key
- `target_item_id: UUID` — tertiary sort key

---

## Sort Contract Per Method

| Method | Sort key(s) in order |
|--------|----------------------|
| `list_categories()` | `(name ASC, category_id ASC)` |
| `list_items()` | `(name ASC, item_id ASC)` |
| `list_category_parent_links()` | `(parent_category_id ASC, sort_index ASC, category_id ASC)` |
| `list_item_parent_links()` | `(category_id ASC, sort_index ASC, item_id ASC)` |
| `list_item_relation_links()` | `(sort_index ASC, source_item_id ASC, target_item_id ASC)` |
| `list_items_by_external_id()` | `(name ASC, item_id ASC)` |
| `list_categories_by_external_id()` | `(name ASC, category_id ASC)` |

All sort directions are ascending. No descending sorts are introduced.
