# Quickstart: Graph Serializer

**Feature**: 029-graph-serializer

## Returning a graph from an HTTP endpoint

### FastAPI
```python
from taxomesh import TaxomeshService
from taxomesh.contrib.api import handlers, serializers

service = TaxomeshService()

@app.get("/graph")
def get_graph():
    return serializers.graph_to_dict(handlers.get_graph(service))
```

### Django
```python
from django.http import JsonResponse
from taxomesh import TaxomeshService
from taxomesh.contrib.api import handlers, serializers

service = TaxomeshService()

def graph_view(request):
    return JsonResponse(serializers.graph_to_dict(handlers.get_graph(service)))
```

## Output shape

```json
{
  "roots": [
    {
      "category": {
        "category_id": "11111111-...",
        "name": "Music",
        "slug": "music",
        "enabled": true,
        "metadata": {}
      },
      "items": [],
      "children": [
        {
          "category": {"category_id": "22222222-...", "name": "Jazz", ...},
          "items": [
            {"item_id": "33333333-...", "name": "Kind of Blue", ...}
          ],
          "children": []
        }
      ]
    }
  ]
}
```

## Verifying JSON-safety

```python
import json
graph = service.get_graph()
result = serializers.graph_to_dict(graph)
json.dumps(result)  # must not raise TypeError
```
