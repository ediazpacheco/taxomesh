# API Contract: Graph Serializer

**Feature**: 029-graph-serializer | **Date**: 2026-03-11

## Public Interface

### `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]`

**Module**: `taxomesh.contrib.api.serializers`
**Import**: `from taxomesh.contrib.api import serializers`

| Aspect | Contract |
|--------|----------|
| Input | Any `TaxomeshGraph` returned by `TaxomeshService.get_graph()` |
| Output | `dict[str, Any]` — fully JSON-serializable; no Pydantic models or dataclasses in output |
| Top-level shape | `{"roots": list[dict]}` |
| Node shape | `{"category": dict, "items": list[dict], "children": list[dict]}` |
| `"category"` | Result of `node.category.model_dump()` — same shape as `Category` Pydantic serialization |
| `"items"` | `[item.model_dump() for item in node.items]` — same shape as `Item` Pydantic serialization |
| `"children"` | Recursively serialized child nodes; same node shape at every depth |
| Empty graph | Returns `{"roots": []}` — never raises on valid input |
| Raises | Never raises for any valid `TaxomeshGraph` from the service |
| Side effects | None — pure function |

## Module re-export

`taxomesh/contrib/api/__init__.py` exports `serializers` module:

```python
from taxomesh.contrib.api import serializers
serializers.graph_to_dict(graph)  # accessible
```

## `__all__` update

```python
__all__ = ["errors", "handlers", "schemas", "serializers"]
```
