# Data Model: Pluggable Graph Sort Modes (053)

## No new storage entities

This feature introduces no new domain models, no new database tables, and no migrations.
All new constructs are pure in-process types and runtime objects.

---

## New In-Process Types

### SortModeFn  *(type alias)*

A callable that takes the full list of graph entries for a single view level and returns
them in the desired order.

| Field | Type | Description |
|---|---|---|
| input | `list[GraphEntry]` | Entries to sort (all children of one parent, or all roots) |
| output | `list[GraphEntry]` | Sorted entries — caller renders exactly this list |

Defined in: `taxomesh/contrib/django/graph_sort.py`

---

### SortMode  *(type alias — 3-tuple)*

A single registered sort mode, declared on the admin class.

| Position | Name | Type | Description |
|---|---|---|---|
| 0 | `key` | `str` | URL query param value; must be unique within the registry |
| 1 | `label` | `str` | Human-readable label shown in the `<select>` |
| 2 | `fn` | `SortModeFn` | Callable applied to entries when this mode is active |

Defined in: `taxomesh/contrib/django/graph_sort.py`

---

### GraphEntry  *(existing TypedDict — moved)*

No fields added or removed. Currently defined in `admin.py`; will be moved to
`taxomesh/contrib/django/graph_types.py` to resolve the circular import with `graph_sort.py`.
All existing imports in `admin.py` updated to import from `graph_types`.

---

### RelationEntry  *(existing TypedDict — moved)*

Same as `GraphEntry` — moved to `graph_types.py` alongside it. No fields changed.

---

## Registry

The `sort_modes` class attribute on the graph admin mixin acts as the registry.

```
TaxomeshCategoryAdmin.sort_modes: list[SortMode]
    default = [
        ("sort_index_asc",  "Sort index ↑", sort_index_asc),
        ("sort_index_desc", "Sort index ↓", sort_index_desc),
    ]
```

Consumers override this at the class level by appending to the parent's list.
Lookup is O(n) linear scan by key — acceptable given the expected registry size (2–5 entries).

---

## Named Constants

| Constant | Value | Module |
|---|---|---|
| `DEFAULT_SORT_MODE` | `"sort_index_asc"` | `graph_sort.py` |
