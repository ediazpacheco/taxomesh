# Data Model: Graph Enhancements (CLI + Admin)

**Branch**: `024-graph-enhancements` | **Date**: 2026-03-08

## Entities (unchanged)

No domain entities are added or modified. All data structures used in this feature
already exist:

| Entity | Source | Relevant fields |
|--------|--------|-----------------|
| `Category` | `taxomesh.domain.models` | `category_id`, `enabled`, `external_id`, `__str__()` |
| `Item` | `taxomesh.domain.models` | `item_id`, `enabled`, `external_id`, `__str__()` |
| `ItemRelationLink` | `taxomesh.domain.models` | `source_item_id`, `target_item_id`, `relation_type`, `sort_index` |
| `CategoryNode` | `taxomesh.domain.graph` | `category`, `items`, `children` |
| `TaxomeshGraph` | `taxomesh.domain.graph` | `roots` |

## New Types (adapter layer only)

### `GraphEntry` (TypedDict) — `taxomesh/contrib/django/admin.py`

Replaces the current `dict[str, object]` in `_flatten_graph` output.

```python
from typing import Literal, TypedDict

class GraphEntry(TypedDict):
    depth: int                            # nesting level (0 = root category)
    kind: Literal["category", "item"]     # node type
    name: str                             # display string (via __str__())
    uuid: str                             # category_id or item_id as string
    enabled: bool                         # enabled/disabled status
    external_id: str                      # raw external_id; "" if absent/None
    linked_url: str | None                # admin change URL for TAXOMESH_LINKED_MODEL; None if not configured or not found
```

### `RelationEntry` (TypedDict) — `taxomesh/contrib/django/admin.py`

Used in the `item_relations` context dict.

```python
class RelationEntry(TypedDict):
    relation_type: str    # normalised relation type string
    target_name: str      # target Item.__str__()
    target_uuid: str      # target item_id as string
```

Context variable type: `dict[str, list[RelationEntry]]` — keyed by source item UUID string.

## New Constant

```python
TAXOMESH_LINKED_MODEL_SETTING: Final[str] = "TAXOMESH_LINKED_MODEL"
```

Defined once in `taxomesh/contrib/django/admin.py`. Read at request time via
`getattr(settings, TAXOMESH_LINKED_MODEL_SETTING, None)`.

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `TAXOMESH_LINKED_MODEL` | `str \| None` | not set | Django model in `"app_label.ModelName"` format. When set and a node has a non-empty `external_id`, an icon-link to `admin:<app>_<model>_change/<pk>/` is rendered. |
