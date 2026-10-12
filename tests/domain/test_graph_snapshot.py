"""A graph built by hand is a snapshot of its inputs: a later change to a caller's input does not reach it.

``TaxomeshGraph`` is a root export, so a caller can build one from its own dicts and lists. The
graph keeps its own copy of each input, as it does for ``categories`` and ``items``.
"""

from uuid import UUID, uuid4

from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, Item


def _inputs() -> tuple[
    dict[UUID, Category],
    dict[UUID, list[UUID]],
    dict[UUID, list[UUID]],
    dict[UUID, list[Item]],
    list[UUID],
]:
    """Return the plain dicts and lists for a two-category graph: ``top`` with the child ``leaf``."""
    top = Category(name="top")
    leaf = Category(name="leaf")
    item = Item(name="piece")
    categories = {top.category_id: top, leaf.category_id: leaf}
    children = {top.category_id: [leaf.category_id]}
    parents = {leaf.category_id: [top.category_id]}
    items = {leaf.category_id: [item]}
    return categories, children, parents, items, [top.category_id]


def _build() -> tuple[TaxomeshGraph, UUID, UUID, dict[str, object]]:
    """Build the graph, and return it with the identifiers of ``top`` and ``leaf`` and the caller's inputs."""
    categories, children, parents, items, roots = _inputs()
    graph = TaxomeshGraph(categories=categories, children=children, parents=parents, items=items, roots=roots)
    top_id, leaf_id = roots[0], next(key for key in categories if key != roots[0])
    inputs: dict[str, object] = {
        "categories": categories,
        "children": children,
        "parents": parents,
        "items": items,
        "roots": roots,
    }
    return graph, top_id, leaf_id, inputs


def _assert_unchanged(graph: TaxomeshGraph, top_id: UUID, leaf_id: UUID) -> None:
    """Check that the graph still answers as it did when it was built."""
    assert len(graph) == 2
    assert [node.category.name for node in graph.roots] == ["top"]
    assert [node.category.name for node in graph[top_id].children] == ["leaf"]
    assert [node.category.name for node in graph[leaf_id].parents] == ["top"]
    assert [item.name for item in graph[leaf_id].items] == ["piece"]


class TestAHandBuiltGraphKeepsItsOwnCopy:
    def test_clearing_each_nested_list_changes_nothing(self) -> None:
        graph, top_id, leaf_id, inputs = _build()
        for table in (inputs["children"], inputs["parents"], inputs["items"]):
            assert isinstance(table, dict)
            for group in table.values():
                group.clear()

        _assert_unchanged(graph, top_id, leaf_id)

    def test_clearing_each_outer_map_changes_nothing(self) -> None:
        graph, top_id, leaf_id, inputs = _build()
        for table in (inputs["categories"], inputs["children"], inputs["parents"], inputs["items"]):
            assert isinstance(table, dict)
            table.clear()

        _assert_unchanged(graph, top_id, leaf_id)

    def test_clearing_roots_changes_nothing(self) -> None:
        graph, top_id, leaf_id, inputs = _build()
        roots = inputs["roots"]
        assert isinstance(roots, list)
        roots.clear()

        _assert_unchanged(graph, top_id, leaf_id)

    def test_adding_to_the_inputs_changes_nothing(self) -> None:
        graph, top_id, leaf_id, inputs = _build()
        stranger = uuid4()
        children, roots = inputs["children"], inputs["roots"]
        assert isinstance(children, dict)
        assert isinstance(roots, list)
        children[top_id].append(stranger)
        children[stranger] = [leaf_id]
        roots.append(stranger)

        _assert_unchanged(graph, top_id, leaf_id)
