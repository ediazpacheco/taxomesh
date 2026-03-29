# Contract: Sort Mode Extension Point

**Module**: `taxomesh.contrib.django.graph_sort`
**Audience**: Consumers who want to add custom sort modes to the admin graph

---

## Type Aliases

```python
from taxomesh.contrib.django.graph_types import GraphEntry

SortModeFn = Callable[[list[GraphEntry]], list[GraphEntry]]
SortMode = tuple[str, str, SortModeFn]
```

---

## Built-in Sort Functions

Both importable from `taxomesh.contrib.django.graph_sort`:

```python
def sort_index_asc(entries: list[GraphEntry]) -> list[GraphEntry]: ...
def sort_index_desc(entries: list[GraphEntry]) -> list[GraphEntry]: ...
```

---

## Default Registry

```python
DEFAULT_SORT_MODE: Final[str] = "sort_index_asc"

DEFAULT_SORT_MODES: Final[list[SortMode]] = [
    ("sort_index_asc",  "Sort index ↑", sort_index_asc),
    ("sort_index_desc", "Sort index ↓", sort_index_desc),
]
```

---

## Admin Class Attribute

```python
class TaxomeshCategoryAdmin(...):
    sort_modes: list[SortMode] = list(DEFAULT_SORT_MODES)
```

---

## Consumer Extension Pattern

```python
from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES, SortMode
from taxomesh.contrib.django.graph_types import GraphEntry

def my_relevance_sort(entries: list[GraphEntry]) -> list[GraphEntry]:
    scores = fetch_relevance_scores([e["uuid"] for e in entries])
    return sorted(entries, key=lambda e: scores.get(e["uuid"], 0), reverse=True)

class MyProjectCategoryAdmin(TaxomeshCategoryAdmin):
    sort_modes: list[SortMode] = [
        *DEFAULT_SORT_MODES,
        ("content_relevance", "Content relevance", my_relevance_sort),
    ]
```

---

## Invariants

- `key` must be unique within the registry — duplicate keys: last entry wins.
- The callable is called once per view render with the full list of entries at that level.
- The callable MUST return a list of the same `GraphEntry` objects (no mutation, no addition/removal required by the contract, but the callable output is rendered as-is).
- An unrecognized `sort_by` query param silently falls back to `DEFAULT_SORT_MODE`.
