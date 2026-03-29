# Quickstart: Pluggable Graph Sort Modes (053)

## For taxomesh users — no action required

The default behaviour (sort by sort index ascending) is unchanged. No migration, no configuration.

---

## For consumers who want a custom sort mode

### 1. Define your sort function

```python
# myproject/admin_sort.py
from taxomesh.contrib.django.graph_types import GraphEntry

def sort_by_relevance(entries: list[GraphEntry]) -> list[GraphEntry]:
    scores = fetch_my_relevance_scores([e["uuid"] for e in entries])
    return sorted(entries, key=lambda e: scores.get(e["uuid"], 0), reverse=True)
```

### 2. Register it on your admin class

```python
# myproject/admin.py
from taxomesh.contrib.django.admin import TaxomeshCategoryAdmin
from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES, SortMode
from myproject.admin_sort import sort_by_relevance

class MyCategoryAdmin(TaxomeshCategoryAdmin):
    sort_modes: list[SortMode] = [
        *DEFAULT_SORT_MODES,
        ("content_relevance", "Content relevance", sort_by_relevance),
    ]
```

### 3. Done

The "Content relevance" option now appears in the sort selector on the graph page.
taxomesh calls your function with `list[GraphEntry]` — the entries already built for
that view level. Your function returns them sorted however you like.

---

## Built-in sort modes

| Key | Label | Behaviour |
|---|---|---|
| `sort_index_asc` | Sort index ↑ | Ascending by `sort_index` (default) |
| `sort_index_desc` | Sort index ↓ | Descending by `sort_index` |
