# Data Model: Repository-Level Enabled Filtering

**Branch**: `046-repo-enabled-filter`
**Date**: 2026-03-21

---

## Overview

This feature introduces no new domain entities. `Category` and `Item` already carry
an `enabled: bool` field. The change is purely to the **repository port contract**
(query interface) and its implementations.

---

## Interface Contract Changes

### `TaxomeshRepositoryBase` (port)

#### `list_categories` — updated signature

```
Before:  list_categories() -> list[Category]
After:   list_categories(*, enabled: bool | None = True) -> list[Category]
```

| `enabled` value | Returned records |
|-----------------|------------------|
| `True` (default) | Only categories where `enabled=True` |
| `False` | Only categories where `enabled=False` |
| `None` | All categories regardless of enabled state |

Ordering: unchanged — `(name ASC, category_id ASC)`.
The implicit root category MUST be excluded from results regardless of this parameter
(unchanged from current behaviour).

#### `list_items` — updated signature

```
Before:  list_items() -> list[Item]
After:   list_items(*, enabled: bool | None = True) -> list[Item]
```

| `enabled` value | Returned records |
|-----------------|------------------|
| `True` (default) | Only items where `enabled=True` |
| `False` | Only items where `enabled=False` |
| `None` | All items regardless of enabled state |

Ordering: unchanged — `(name ASC, item_id ASC)`.

---

## Service Layer Interface Changes

### `TaxomeshService.list_categories`

```
Before:  list_categories(*, parent_id=None, external_id=None) -> list[Category]
After:   list_categories(*, parent_id=None, external_id=None, enabled: bool | None = True) -> list[Category]
```

Passes `enabled` through to `repo.list_categories()`.

### `TaxomeshService.list_items`

```
Before:  list_items(*, category_id=None) -> list[Item]
After:   list_items(*, category_id=None, enabled: bool | None = True) -> list[Item]
```

Passes `enabled` through to `repo.list_items()`.

### `TaxomeshService.list_categories_by_item`

```
Before:  list_categories_by_item(item_id: UUID) -> list[Category]
After:   list_categories_by_item(item_id: UUID, *, enabled: bool | None = True) -> list[Category]
```

Python-level filtering applied after `get_category()` per link (see research.md
Decision 3). Docstring updated to remove "disabled categories are included" note.

### `TaxomeshService.search_items`

```
Before:  search_items(query, *, limit, category_id, enabled_only: bool = True, fuzzy, recursive)
After:   search_items(query, *, limit, category_id, enabled: bool = True, fuzzy, recursive)
```

Parameter `enabled_only` renamed to `enabled`. Same behaviour; corpus filtering uses
`enabled` instead of `enabled_only`. Note: `enabled` is `bool` (not `bool | None`)
on search — search always targets either enabled or disabled records.

### `TaxomeshService.search_categories`

```
Before:  search_categories(query, *, limit, parent_id, enabled_only: bool = True, fuzzy)
After:   search_categories(query, *, limit, parent_id, enabled: bool = True, fuzzy)
```

Same rename as `search_items`.

### `TaxomeshService.get_graph`

```
Before:  get_graph() -> TaxomeshGraph
After:   get_graph(*, enabled: bool = True) -> TaxomeshGraph
```

Passes `enabled` to both `repo.list_categories()` and `repo.list_items()` internally.
Both categories and items in the graph are filtered by the same `enabled` value.

---

## Internal Service Methods

### `_get_item_corpus` (private)

Calls `self._repo.list_items(enabled=None)` to load all items for the search index.
No signature change (private method).

### `_get_category_corpus` (private)

Calls `self._repo.list_categories(enabled=None)` to load all categories for the search
index. No signature change (private method).

---

## `enabled` Mapping at Each Layer

| Layer | Parameter name | Type | Default | `None` meaning |
|-------|---------------|------|---------|----------------|
| Repository port | `enabled` | `bool \| None` | `True` | All records |
| Service methods (list) | `enabled` | `bool \| None` | `True` | All records |
| Service methods (search) | `enabled` | `bool` | `True` | N/A |
| CLI flag | `--include-disabled` | flag (bool) | absent=`False` | Maps to `enabled=None` |
| Contrib API handler | `include_disabled` | `bool` | `False` | Maps to `enabled=None` |
| Contrib API schema (search) | `enabled` | `bool` | `True` | N/A |

---

## No Changes To

- `Category` and `Item` domain models — `enabled` field already exists.
- All single-record lookups (`get_category`, `get_item`, slug/external-id lookups).
- `list_category_parent_links`, `list_item_parent_links`, `list_item_relation_links`.
- `list_tags`, `get_tag`, tag-related methods.
- Any write methods (`save_*`, `delete_*`, `create_*`, `update_*`).
