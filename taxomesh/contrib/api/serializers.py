"""The conversion of rows and graph snapshots to values that JSON can hold, for HTTP answers.

:func:`graph_to_dict` turns a ``TaxomeshGraph`` snapshot into a plain dict that ``json.dumps``
accepts. :func:`items_to_list` and :func:`categories_to_list` do the same for rows. An application
uses them to return the graph or rows as the JSON body of a response.

The graph holds one node for each category, but the serialization is a *tree*: a category that
several parents reach is emitted once **for each path**, because a nested ``children`` document
means that. This has two consequences for the code below.

* The traversal is **iterative**. A chain deeper than the interpreter's recursion limit must
  serialize, and not raise ``RecursionError``: that error is a builtin, which a caller who catches
  this library's errors does not catch.
* Its guard is **path-local**, not global: it holds the ancestors of the node that it emits, and
  nothing else. A global set would stop the second emission of a shared subtree, and change the
  serialized bytes that the tests pin. ``TaxomeshGraph.walk`` uses a global set for the opposite
  reason: it yields each node exactly once. One guard cannot replace the other.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final
from uuid import UUID

from taxomesh.contrib.api.errors import TaxomeshGraphTooLargeError
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, Item

#: The most node dicts that one ``graph_to_dict`` call emits. Past it, the call raises.
#: It is public, so that callers and tests compare against it and do not copy the literal.
#:
#: The number of dicts grows exponentially with shared parents: k stacked diamonds emit
#: ``2^(k+2)-3`` dicts, so 61 stored categories would emit 4 194 301. The graph holds each
#: category once; this limit stops the serializer from making a response body of that size.
#: A plain tree emits one dict for each category, far below the limit.
MAX_EMITTED_NODES: Final[int] = 100_000


@dataclass(frozen=True, slots=True)
class _Enter:
    """A node to emit, and the ``children`` list that its dict goes into."""

    node: CategoryNode
    # Any: the sink holds emitted node dicts, a heterogeneous JSON mix (str, bool, list, nested dict)
    sink: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class _Leave:
    """A marker that the descent has finished with a category, so it leaves the current path."""

    category_id: UUID


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
    path: set[UUID] = set()
    emitted = 0
    stack: list[_Enter | _Leave] = [_Enter(node, roots) for node in reversed(graph.roots)]

    while stack:
        frame = stack.pop()
        if isinstance(frame, _Leave):
            # One _Leave is pushed for each path entry, and it pops before a sibling can enter that
            # identifier again, so remove() finds it. A later defect in that order raises KeyError here.
            path.remove(frame.category_id)
            continue

        category_id = frame.node.category.category_id
        emitted += 1
        if emitted > MAX_EMITTED_NODES:
            raise TaxomeshGraphTooLargeError(
                f"Serializing this graph would emit more than {MAX_EMITTED_NODES} nodes: a category "
                f"reachable through several parents is emitted once per path, so {len(graph)} stored "
                "categories can expand without bound"
            )

        # Any: an emitted node dict is a heterogeneous JSON mix (str, bool, list, nested dict).
        children: list[dict[str, Any]] = []
        frame.sink.append(
            {
                "category": frame.node.category.model_dump(mode="json"),
                "items": [item.model_dump(mode="json") for item in frame.node.items],
                "children": children,
            }
        )

        if category_id in path:
            continue

        path.add(category_id)
        # Pushed BEFORE the children so that it pops AFTER them: the path must stay whole for the
        # whole descent. Pushed after them, it would pop first and clear the path before any child
        # was visited, and the guard would then stop nothing.
        stack.append(_Leave(category_id))
        # Reversed, so that popping restores the children's stored order.
        stack.extend(_Enter(child, children) for child in reversed(frame.node.children))

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
