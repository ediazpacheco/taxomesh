# Quickstart: Repository-Level Enabled Filtering

**Feature**: `046-repo-enabled-filter`

## Before / After Comparison

### Listing categories

```python
# Before (0.1.x): always returns all categories
cats = svc.list_categories()           # includes disabled
cats = svc.list_categories()           # no way to filter by enabled at this level

# After (0.2.x): enabled=True by default
cats = svc.list_categories()           # only enabled (default)
cats = svc.list_categories(enabled=False)   # only disabled
cats = svc.list_categories(enabled=None)    # all records
```

### Listing items

```python
# Before: always returns all items
items = svc.list_items()

# After: only enabled by default
items = svc.list_items()                    # only enabled (default)
items = svc.list_items(enabled=None)        # all records (for admin use)
```

### Searching (renamed parameter)

```python
# Before
results = svc.search_items("jazz", enabled_only=True)

# After (same behaviour, renamed param)
results = svc.search_items("jazz", enabled=True)
results = svc.search_items("jazz", enabled=False)  # search disabled items
```

### Getting the graph

```python
# Before: includes all categories and items
graph = svc.get_graph()

# After: excludes disabled by default
graph = svc.get_graph()                     # only enabled categories + items
graph = svc.get_graph(enabled=None)         # all categories + items (admin)
```

### Categories for an item

```python
# Before: always returns all categories (including disabled)
cats = svc.list_categories_by_item(item.item_id)

# After: only enabled categories by default
cats = svc.list_categories_by_item(item.item_id)            # only enabled
cats = svc.list_categories_by_item(item.item_id, enabled=None)  # all
```

---

## CLI Usage

```bash
# Default: only enabled
taxomesh category list
taxomesh item list

# Include disabled records
taxomesh category list --include-disabled
taxomesh item list --include-disabled
taxomesh graph --include-disabled
```

---

## Contrib API Usage

```python
from taxomesh.contrib.api import handlers

# Default: only enabled
categories = handlers.list_categories(service)
items = handlers.list_items(service)
graph = handlers.get_graph(service)

# Include disabled
categories = handlers.list_categories(service, include_disabled=True)
items = handlers.list_items(service, include_disabled=True)
graph = handlers.get_graph(service, include_disabled=True)

# Search schemas (renamed field)
from taxomesh.contrib.api.schemas import SearchItemsRequest
params = SearchItemsRequest(q="jazz", enabled=True)    # was: enabled_only=True
```

---

## Migration Guide for Callers

| Old call | New call | Notes |
|----------|----------|-------|
| `list_categories()` | `list_categories()` | Now returns only enabled (was: all) |
| `list_items()` | `list_items()` | Now returns only enabled (was: all) |
| `list_categories_by_item(id)` | `list_categories_by_item(id)` | Now returns only enabled (was: all) |
| `search_items(q, enabled_only=True)` | `search_items(q, enabled=True)` | Renamed param, same behaviour |
| `search_items(q, enabled_only=False)` | `search_items(q, enabled=False)` | Renamed param, same behaviour |
| `get_graph()` | `get_graph()` | Now returns only enabled nodes (was: all) |
| Any call needing all records | Add `enabled=None` | e.g. `list_items(enabled=None)` |
