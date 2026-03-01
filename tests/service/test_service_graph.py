"""Failing tests for TaxomeshService.get_graph() — US1.

All tests in this file MUST fail before T004 (implementation) is started,
per the project TDD mandate (CLAUDE.md §Testing Rules).
"""

from __future__ import annotations

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Tag

from .conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flat_category_names(graph: TaxomeshGraph) -> list[str]:
    """Collect every CategoryNode.category.name in the graph, depth-first."""
    names: list[str] = []

    def _walk(nodes: list[CategoryNode]) -> None:
        for node in nodes:
            names.append(node.category.name)
            _walk(node.children)

    _walk(graph.roots)
    return names


# ---------------------------------------------------------------------------
# T003 tests
# ---------------------------------------------------------------------------


def test_get_graph_returns_taxomesh_graph_instance() -> None:
    """get_graph() must return a TaxomeshGraph instance."""
    svc = TaxomeshService(repository=InMemoryRepository())
    result = svc.get_graph()
    assert isinstance(result, TaxomeshGraph)


def test_get_graph_empty_taxonomy_returns_empty_roots() -> None:
    """An empty taxonomy (no user categories) yields roots == []."""
    svc = TaxomeshService(repository=InMemoryRepository())
    graph = svc.get_graph()
    assert graph.roots == []


def test_get_graph_single_category_no_items() -> None:
    """A single category with no items appears in roots with empty items/children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.create_category("Animals")
    graph = svc.get_graph()

    assert len(graph.roots) == 1
    node = graph.roots[0]
    assert node.category.name == "Animals"
    assert node.items == []
    assert node.children == []


def test_get_graph_items_ordered_by_sort_index() -> None:
    """Items within a category node are ordered by sort_index ascending."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat = svc.create_category("Animals")
    item_b = svc.create_item(name="lion", external_id="lion")
    item_a = svc.create_item(name="zebra", external_id="zebra")

    # Place with reversed sort_index so order is non-trivial
    svc.place_item_in_category(item_b.item_id, cat.category_id, sort_index=10)
    svc.place_item_in_category(item_a.item_id, cat.category_id, sort_index=1)

    graph = svc.get_graph()
    items = graph.roots[0].items
    assert len(items) == 2
    assert items[0].external_id == "zebra"  # sort_index=1 comes first
    assert items[1].external_id == "lion"  # sort_index=10 comes second


def test_get_graph_item_in_multiple_categories_appears_in_each() -> None:
    """An item placed in two categories appears under both CategoryNodes."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat_a = svc.create_category("A")
    cat_b = svc.create_category("B")
    item = svc.create_item(name="shared", external_id="shared")

    svc.place_item_in_category(item.item_id, cat_a.category_id)
    svc.place_item_in_category(item.item_id, cat_b.category_id)

    graph = svc.get_graph()
    all_item_ids = [i.item_id for node in graph.roots for i in node.items]
    assert all_item_ids.count(item.item_id) == 2


def test_get_graph_excludes_root_from_graph() -> None:
    """The __root__ category must not appear anywhere in the returned graph."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.create_category("Animals")
    graph = svc.get_graph()

    all_names = _flat_category_names(graph)
    assert "__root__" not in all_names


def test_get_graph_top_level_category_appears_in_roots() -> None:
    """A category whose only parent is root appears in TaxomeshGraph.roots."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.create_category("Animals")
    graph = svc.get_graph()

    root_names = [node.category.name for node in graph.roots]
    assert "Animals" in root_names


def test_get_graph_child_category_not_in_roots() -> None:
    """A category with an explicit parent is NOT in roots; it is in parent.children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent = svc.create_category("Animals")
    child = svc.create_category("Mammals")
    svc.add_category_parent(child.category_id, parent.category_id, sort_index=1)

    graph = svc.get_graph()

    root_names = [node.category.name for node in graph.roots]
    assert "Mammals" not in root_names

    parent_node = next(n for n in graph.roots if n.category.name == "Animals")
    child_names = [n.category.name for n in parent_node.children]
    assert "Mammals" in child_names


def test_get_graph_multi_parent_category_appears_under_each_parent() -> None:
    """A category with two explicit parents appears in both parents' children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent1 = svc.create_category("Animals")
    parent2 = svc.create_category("LivingThings")
    child = svc.create_category("Mammals")
    svc.add_category_parent(child.category_id, parent1.category_id, sort_index=1)
    svc.add_category_parent(child.category_id, parent2.category_id, sort_index=1)

    graph = svc.get_graph()

    parent1_node = next(n for n in graph.roots if n.category.name == "Animals")
    parent2_node = next(n for n in graph.roots if n.category.name == "LivingThings")

    assert any(n.category.name == "Mammals" for n in parent1_node.children)
    assert any(n.category.name == "Mammals" for n in parent2_node.children)


def test_get_graph_children_ordered_by_sort_index() -> None:
    """Children within a CategoryNode are ordered by sort_index ascending."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent = svc.create_category("Animals")
    child_b = svc.create_category("Reptiles")
    child_a = svc.create_category("Mammals")

    svc.add_category_parent(child_b.category_id, parent.category_id, sort_index=10)
    svc.add_category_parent(child_a.category_id, parent.category_id, sort_index=1)

    graph = svc.get_graph()
    parent_node = next(n for n in graph.roots if n.category.name == "Animals")
    children_names = [n.category.name for n in parent_node.children]
    assert children_names == ["Mammals", "Reptiles"]  # sort_index 1 before 10


def test_get_graph_no_tag_data_in_graph() -> None:
    """TaxomeshGraph contains no tag objects, regardless of tags in taxonomy (SC-002)."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat = svc.create_category("Animals")
    item = svc.create_item(name="lion", external_id="lion")
    svc.place_item_in_category(item.item_id, cat.category_id)
    tag = svc.create_tag(name="mammal")
    svc.assign_tag(tag.tag_id, item.item_id)

    graph = svc.get_graph()

    # Walk the graph and confirm no Tag object is reachable
    def _has_tag(obj: object) -> bool:
        return isinstance(obj, Tag)

    for node in graph.roots:
        assert not _has_tag(node.category)
        for it in node.items:
            assert not _has_tag(it)
