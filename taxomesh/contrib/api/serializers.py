"""The conversion of rows and graph snapshots to values that JSON can hold, for HTTP answers.

:func:`graph_to_dict` turns a ``TaxomeshGraph`` snapshot into a plain dict that ``json.dumps``
accepts. :func:`items_to_list` and :func:`categories_to_list` do the same for rows. An application
uses them to return the graph or rows as the JSON body of a response.

The graph holds one node for each category, but the serialization is a *tree*: a category that
several parents reach is emitted once **for each path**, because a nested ``children`` document
means that. :func:`~taxomesh.domain.paths.walk_paths` makes that walk, and its module says why the
walk is iterative and its guard path-local.
"""

from collections.abc import Sequence
from typing import Any

from taxomesh.contrib.api.errors import TaxomeshGraphTooLargeError
from taxomesh.domain.constants import MAX_EMITTED_NODES
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, Item
from taxomesh.domain.paths import walk_paths

__all__ = ["MAX_EMITTED_NODES", "categories_to_list", "graph_to_dict", "items_to_list"]


# Any: dict values are a heterogeneous JSON mix (str, bool, list, nested dict)
def graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]:
    """Convert a ``TaxomeshGraph`` snapshot to a plain dict that ``json.dumps`` accepts.

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

    A category that several parents reach is emitted once under each of them. A category that
    appears again on its own path, which only a cycle in stored data makes, is emitted where it
    appears again, without its children: its ``children`` is empty there, and the document ends.
    Its children were already emitted higher on the same path. So an empty ``children`` is either a
    category with no children or a cycle that stops there.

    The document starts at ``graph.roots``, so it leaves out each category that no node in
    ``roots`` reaches: a category whose parents the ``enabled`` filter left out, the categories of a
    stored cycle that no top-level category reaches, and each category that only those reach.
    ``graph.walk()`` yields them all.

    Args:
        graph: The graph snapshot that ``TaxomeshService.graph()`` returned.

    Returns:
        A dict that ``json.dumps`` accepts; ``{"roots": []}`` for an empty graph.

    Raises:
        TaxomeshGraphTooLargeError: If the document would hold more than ``MAX_EMITTED_NODES``
            node dicts. Shared parents make the count grow exponentially, so a graph of a few
            dozen categories can pass the limit; without it, the response would have no upper
            size.
    """
    # Any: an emitted node dict is a heterogeneous JSON mix (str, bool, list, nested dict).
    roots: list[dict[str, Any]] = []
    for emitted, visit in enumerate(walk_paths(graph.roots, roots), 1):
        if emitted > MAX_EMITTED_NODES:
            raise TaxomeshGraphTooLargeError(
                f"Serializing this graph would emit more than {MAX_EMITTED_NODES} nodes: a category "
                f"reachable through several parents is emitted once per path, so {len(graph)} stored "
                "categories can expand without bound"
            )
        # Any: an emitted node dict is a heterogeneous JSON mix (str, bool, list, nested dict).
        children: list[dict[str, Any]] = []
        visit.outer.append(
            {
                "category": visit.node.category.model_dump(mode="json"),
                "items": [item.model_dump(mode="json") for item in visit.node.items],
                "children": children,
            }
        )
        visit.inner = children

    return {"roots": roots}


# Any: heterogeneous JSON dict
def items_to_list(items: Sequence[Item]) -> list[dict[str, Any]]:
    """Convert item rows to dicts that ``json.dumps`` accepts.

    Args:
        items: The item rows, in the order to emit them, such as what ``items_search`` returns.

    Returns:
        One ``Item.model_dump(mode="json")`` dict for each row, in that order; empty when ``items``
        is empty.
    """
    return [item.model_dump(mode="json") for item in items]


# Any: heterogeneous JSON dict
def categories_to_list(categories: Sequence[Category]) -> list[dict[str, Any]]:
    """Convert category rows to dicts that ``json.dumps`` accepts.

    Args:
        categories: The category rows, in the order to emit them, such as what
            ``categories_search`` returns.

    Returns:
        One ``Category.model_dump(mode="json")`` dict for each row, in that order; empty when
        ``categories`` is empty.
    """
    return [cat.model_dump(mode="json") for cat in categories]
