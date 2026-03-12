# Data Model: Graph Serializer for HTTP Integration

**Feature**: 029-graph-serializer | **Date**: 2026-03-11

## Input Types (unchanged — no modifications)

### `TaxomeshGraph` (dataclass — read-only)
| Field | Type | Description |
|-------|------|-------------|
| `roots` | `list[CategoryNode]` | Top-level category nodes, sorted by sort_index |

### `CategoryNode` (dataclass — read-only, recursive)
| Field | Type | Description |
|-------|------|-------------|
| `category` | `Category` | Full Pydantic Category entity |
| `items` | `list[Item]` | Items in this category, sorted by sort_index |
| `children` | `list[CategoryNode]` | Child category nodes, sorted by sort_index |

## Output Shape (produced by `graph_to_dict`)

```
{
  "roots": [
    {
      "category": { ...Category.model_dump() },
      "items": [ { ...Item.model_dump() }, ... ],
      "children": [
        {
          "category": { ...Category.model_dump() },
          "items": [ ... ],
          "children": [ ... ]   ← recursive to arbitrary depth
        }
      ]
    }
  ]
}
```

All values are JSON-primitive types (str, int, float, bool, None, list, dict).
No UUID objects, no Pydantic model instances, no dataclass instances in output.

## New Module

### `taxomesh/contrib/api/serializers.py`
| Symbol | Visibility | Type | Description |
|--------|------------|------|-------------|
| `graph_to_dict` | public | `(TaxomeshGraph) -> dict[str, Any]` | Top-level entry point |
| `_node_to_dict` | private | `(CategoryNode) -> dict[str, Any]` | Per-node recursive helper |
