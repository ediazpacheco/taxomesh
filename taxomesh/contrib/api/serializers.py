"""Graph serialization utilities for HTTP API integration.

Provides a single public function, ``graph_to_dict``, that converts a
``TaxomeshGraph`` snapshot into a plain, fully JSON-serializable dict.
Intended for use in HTTP handler layers where the caller needs to return
the taxonomy graph as a JSON response body.
"""

from typing import Any

from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, Item


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


# Any: heterogeneous JSON dict
def items_to_list(items: list[Item]) -> list[dict[str, Any]]:
    """Serialize a list of Item domain objects to JSON-compatible dicts.

    Args:
        items: List of Item instances (e.g. returned by search_items).

    Returns:
        List of plain dicts produced by Item.model_dump(mode="json").
        Empty list when items is empty.
    """
    return [item.model_dump(mode="json") for item in items]


# Any: heterogeneous JSON dict
def categories_to_list(categories: list[Category]) -> list[dict[str, Any]]:
    """Serialize a list of Category domain objects to JSON-compatible dicts.

    Args:
        categories: List of Category instances (e.g. returned by search_categories).

    Returns:
        List of plain dicts produced by Category.model_dump(mode="json").
        Empty list when categories is empty.
    """
    return [cat.model_dump(mode="json") for cat in categories]
