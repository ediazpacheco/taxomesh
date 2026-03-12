"""Graph serialization utilities for HTTP API integration.

Provides a single public function, ``graph_to_dict``, that converts a
``TaxomeshGraph`` snapshot into a plain, fully JSON-serializable dict.
Intended for use in HTTP handler layers where the caller needs to return
the taxonomy graph as a JSON response body.
"""

from typing import Any

from taxomesh.domain.graph import CategoryNode, TaxomeshGraph


# Any: dict values are a heterogeneous JSON mix (str, bool, list, nested dict)
def _node_to_dict(node: CategoryNode) -> dict[str, Any]:
    return {
        "category": node.category.model_dump(mode="json"),
        "items": [item.model_dump(mode="json") for item in node.items],
        "children": [_node_to_dict(child) for child in node.children],
    }


# Any: dict values are a heterogeneous JSON mix (str, bool, list, nested dict)
def graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]:
    """Convert a TaxomeshGraph snapshot to a plain JSON-serializable dict.

    The returned dict has the shape::

        {
            "roots": [
                {
                    "category": {...},   # Category.model_dump(mode="json")
                    "items":    [{...}], # [Item.model_dump(mode="json"), ...]
                    "children": [{...}], # recursively serialized child nodes
                }
            ]
        }

    Args:
        graph: A ``TaxomeshGraph`` produced by ``TaxomeshService.get_graph()``.

    Returns:
        A fully JSON-serializable dict.  Returns ``{"roots": []}`` for an
        empty graph.  Never raises for any valid graph from the service.
    """
    return {"roots": [_node_to_dict(node) for node in graph.roots]}
