"""What ``TaxomeshService.graph()`` returns, whole and rooted at a category.

Its roots and their order, children under each parent, items by sort index, the implicit root's
absence, and the rooted form: its type, its pruning to the subtree, and the ids it refuses.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import CategoryParentLink, Tag
from taxomesh.exceptions import TaxomeshCategoryNotFoundError

from .conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flat_category_names(graph: TaxomeshGraph) -> list[str]:
    """Collect every CategoryNode.category.name in the graph, depth-first."""
    names: list[str] = []

    def _walk(nodes: Sequence[CategoryNode]) -> None:
        for node in nodes:
            names.append(node.category.name)
            _walk(node.children)

    _walk(graph.roots)
    return names


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_graph_returns_taxomesh_graph_instance() -> None:
    """graph() must return a TaxomeshGraph instance."""
    svc = TaxomeshService(repository=InMemoryRepository())
    result = svc.graph()
    assert isinstance(result, TaxomeshGraph)


def test_graph_empty_taxonomy_returns_empty_roots() -> None:
    """An empty taxonomy (no user categories) yields roots == []."""
    svc = TaxomeshService(repository=InMemoryRepository())
    graph = svc.graph()
    assert graph.roots == ()


def test_every_backend_builds_the_same_graph(service: TaxomeshService) -> None:
    """On every backend, an empty store has no root, and a child hangs under the parent holding the item."""
    assert service.graph().roots == ()
    parent = service.categories.create("Parent")
    child = service.categories.create("Child")
    service.categories.add_parent(child.category_id, parent.category_id)
    item = service.items.create("item", external_id="item")
    service.items.place_in(item.item_id, parent.category_id)
    service.items.tag(item.item_id, service.tags.create("fiction").tag_id)

    (root,) = service.graph().roots
    assert root.category.category_id == parent.category_id
    assert [node.category.category_id for node in root.children] == [child.category_id]
    assert [placed.item_id for placed in root.items] == [item.item_id]


def test_graph_single_category_no_items() -> None:
    """A single category with no items appears in roots with empty items/children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.categories.create("Animals")
    graph = svc.graph()

    assert len(graph.roots) == 1
    node = graph.roots[0]
    assert node.category.name == "Animals"
    assert node.items == ()
    assert node.children == ()


def test_graph_items_ordered_by_sort_index() -> None:
    """Items within a category node are ordered by sort_index ascending."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat = svc.categories.create("Animals")
    item_b = svc.items.create(name="lion", external_id="lion")
    item_a = svc.items.create(name="zebra", external_id="zebra")

    # Place with reversed sort_index so order is non-trivial
    svc.items.place_in(item_b.item_id, cat.category_id, sort_index=10)
    svc.items.place_in(item_a.item_id, cat.category_id, sort_index=1)

    graph = svc.graph()
    items = graph.roots[0].items
    assert len(items) == 2
    assert items[0].external_id == "zebra"  # sort_index=1 comes first
    assert items[1].external_id == "lion"  # sort_index=10 comes second


def test_graph_item_in_multiple_categories_appears_in_each() -> None:
    """An item placed in two categories appears under both CategoryNodes."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat_a = svc.categories.create("A")
    cat_b = svc.categories.create("B")
    item = svc.items.create(name="shared", external_id="shared")

    svc.items.place_in(item.item_id, cat_a.category_id)
    svc.items.place_in(item.item_id, cat_b.category_id)

    graph = svc.graph()
    all_item_ids = [i.item_id for node in graph.roots for i in node.items]
    assert all_item_ids.count(item.item_id) == 2


def test_graph_excludes_root_from_graph() -> None:
    """The __root__ category must not appear anywhere in the returned graph."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.categories.create("Animals")
    graph = svc.graph()

    all_names = _flat_category_names(graph)
    assert "__root__" not in all_names


def test_graph_top_level_category_appears_in_roots() -> None:
    """A category whose only parent is root appears in TaxomeshGraph.roots."""
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.categories.create("Animals")
    graph = svc.graph()

    root_names = [node.category.name for node in graph.roots]
    assert "Animals" in root_names


def test_graph_child_category_not_in_roots() -> None:
    """A category with an explicit parent is NOT in roots; it is in parent.children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent = svc.categories.create("Animals")
    child = svc.categories.create("Mammals")
    svc.categories.add_parent(child.category_id, parent.category_id, sort_index=1)

    graph = svc.graph()

    root_names = [node.category.name for node in graph.roots]
    assert "Mammals" not in root_names

    parent_node = next(n for n in graph.roots if n.category.name == "Animals")
    child_names = [n.category.name for n in parent_node.children]
    assert "Mammals" in child_names


def test_graph_multi_parent_category_appears_under_each_parent() -> None:
    """A category with two explicit parents appears in both parents' children."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent1 = svc.categories.create("Animals")
    parent2 = svc.categories.create("LivingThings")
    child = svc.categories.create("Mammals")
    svc.categories.add_parent(child.category_id, parent1.category_id, sort_index=1)
    svc.categories.add_parent(child.category_id, parent2.category_id, sort_index=1)

    graph = svc.graph()

    parent1_node = next(n for n in graph.roots if n.category.name == "Animals")
    parent2_node = next(n for n in graph.roots if n.category.name == "LivingThings")

    assert any(n.category.name == "Mammals" for n in parent1_node.children)
    assert any(n.category.name == "Mammals" for n in parent2_node.children)


def test_graph_children_ordered_by_sort_index() -> None:
    """Children within a CategoryNode are ordered by sort_index ascending."""
    svc = TaxomeshService(repository=InMemoryRepository())
    parent = svc.categories.create("Animals")
    child_b = svc.categories.create("Reptiles")
    child_a = svc.categories.create("Mammals")

    svc.categories.add_parent(child_b.category_id, parent.category_id, sort_index=10)
    svc.categories.add_parent(child_a.category_id, parent.category_id, sort_index=1)

    graph = svc.graph()
    parent_node = next(n for n in graph.roots if n.category.name == "Animals")
    children_names = [n.category.name for n in parent_node.children]
    assert children_names == ["Mammals", "Reptiles"]  # sort_index 1 before 10


def test_graph_no_tag_data_in_graph() -> None:
    """TaxomeshGraph contains no tag objects, regardless of tags in taxonomy."""
    svc = TaxomeshService(repository=InMemoryRepository())
    cat = svc.categories.create("Animals")
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, cat.category_id)
    tag = svc.tags.create(name="mammal")
    svc.items.tag(item.item_id, tag.tag_id)

    graph = svc.graph()

    # Walk the graph and confirm no Tag object is reachable
    def _has_tag(obj: object) -> bool:
        return isinstance(obj, Tag)

    for node in graph.roots:
        assert not _has_tag(node.category)
        for it in node.items:
            assert not _has_tag(it)


# ---------------------------------------------------------------------------
# Root ordering
# ---------------------------------------------------------------------------


def test_graph_roots_break_a_sort_index_tie_by_category_id() -> None:
    """Roots sharing a sort index are ordered by category id.

    ``create`` writes ``sort_index=0`` for every root link, so on an ordinary taxonomy *every*
    root sort key ties. The iteration order of a set would resolve the tie by an arbitrary
    function of the stored identifiers, agreeing with id order no more than chance.
    """
    svc = TaxomeshService(repository=InMemoryRepository())
    created = [svc.categories.create(name) for name in ("Alpha", "Beta", "Gamma", "Delta")]

    graph = svc.graph()

    expected = [c.category_id for c in sorted(created, key=lambda c: str(c.category_id))]
    assert [node.category.category_id for node in graph.roots] == expected


def test_graph_roots_agree_with_the_category_collection() -> None:
    """``graph.roots`` and ``svc.categories.roots()`` present the same roots in the same order.

    Both read the root links, and both order them by the port's
    ``(parent_category_id ASC, sort_index ASC, category_id ASC)`` contract, which all four
    adapters implement.
    """
    svc = TaxomeshService(repository=InMemoryRepository())
    for name in ("Alpha", "Beta", "Gamma", "Delta"):
        svc.categories.create(name)

    graph = svc.graph()

    assert [node.category.category_id for node in graph.roots] == [c.category_id for c in svc.categories.roots()]


def test_graph_roots_order_by_sort_index_before_category_id() -> None:
    """A stored sort index outranks the identifier tiebreak.

    Root links carry real sort indexes — ``categories.reorder`` and the admin's drag-and-drop
    both persist them — so the identifier only ever breaks a tie. Ordering the roots *against*
    id order is what makes this fail if the two keys are ever swapped.
    """
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    created = [svc.categories.create(name) for name in ("Alpha", "Beta", "Gamma")]

    wanted = sorted(created, key=lambda c: str(c.category_id), reverse=True)
    svc.categories.reorder(None, [c.category_id for c in wanted])

    graph = svc.graph()

    assert [node.category.category_id for node in graph.roots] == [c.category_id for c in wanted]


# ---------------------------------------------------------------------------
# Rooted graphs
# ---------------------------------------------------------------------------


def _subtree_fixture() -> tuple[TaxomeshService, dict[str, UUID]]:
    """Build ``Alpha → Gamma → Delta``, with ``Delta`` also parented under a second root.

    The second parent is the point. ``Delta`` is inside ``Alpha``'s subtree while one of its
    parents, ``Beta``, is outside it — the shape that decides whether the assembler prunes the
    parent map or leaves a dangling identifier behind.
    """
    svc = TaxomeshService(repository=InMemoryRepository())
    alpha = svc.categories.create("Alpha")
    beta = svc.categories.create("Beta")
    gamma = svc.categories.create("Gamma")
    delta = svc.categories.create("Delta")
    svc.categories.add_parent(gamma.category_id, alpha.category_id)
    svc.categories.add_parent(delta.category_id, gamma.category_id)
    svc.categories.add_parent(delta.category_id, beta.category_id)
    return svc, {
        "alpha": alpha.category_id,
        "beta": beta.category_id,
        "gamma": gamma.category_id,
        "delta": delta.category_id,
    }


def test_graph_rooted_returns_the_same_type() -> None:
    """A rooted graph is the whole-taxonomy type, not a second tree model."""
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["alpha"])

    assert isinstance(rooted, TaxomeshGraph)


def test_graph_rooted_presents_the_root_as_its_only_root() -> None:
    """``roots`` is the category asked for, and nothing else."""
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["alpha"])

    assert [node.category.name for node in rooted.roots] == ["Alpha"]


def test_graph_rooted_prunes_the_flat_maps_to_the_subtree() -> None:
    """The flat maps are pruned, not merely re-rooted — asserted by ``len`` and the walk.

    This is the gate for a failure that is invisible to the obvious test. Narrowing ``roots`` to
    the requested category while leaving ``categories`` / ``children`` / ``parents`` carrying the
    whole taxonomy still satisfies every assertion about ``roots``, and the root node's
    ``descendants()`` are still exactly the subtree — so a test written that way has no power at
    all over the bug. What gives it away is ``len()``, which counts the whole taxonomy, and
    ``walk()``, which sweeps out of the subtree and into ``Beta`` through the pass that exists to
    enumerate orphans.
    """
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["alpha"])

    assert len(rooted) == 3
    assert {node.category.name for node in rooted.walk()} == {"Alpha", "Gamma", "Delta"}
    assert ids["beta"] not in rooted


def test_graph_rooted_drops_a_parent_that_lies_outside_the_subtree() -> None:
    """``Delta``'s out-of-subtree parent is absent, and reaching for it does not explode.

    Left unpruned, ``Beta``'s identifier would survive in the parent map while ``Beta`` itself
    is not a node, and ``node.parents`` would raise a bare ``KeyError`` — a builtin, so it
    escapes a caller catching this library's own errors.
    """
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["alpha"])

    assert [node.category.name for node in rooted[ids["delta"]].parents] == ["Gamma"]
    assert rooted[ids["alpha"]].parents == ()


def test_graph_rooted_keeps_the_children_inside_the_subtree() -> None:
    """Navigation within the subtree is unchanged."""
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["alpha"])

    assert [node.category.name for node in rooted[ids["alpha"]].children] == ["Gamma"]
    assert [node.category.name for node in rooted[ids["gamma"]].children] == ["Delta"]


def test_graph_rooted_at_a_leaf_holds_one_node() -> None:
    """A category with no children roots a graph of exactly itself."""
    svc, ids = _subtree_fixture()

    rooted = svc.graph(root=ids["delta"])

    assert len(rooted) == 1
    assert [node.category.name for node in rooted.roots] == ["Delta"]


def test_graph_rooted_without_items_carries_none() -> None:
    """``include_items=False`` empties a rooted graph exactly as it empties a whole one."""
    svc, ids = _subtree_fixture()
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, ids["gamma"])

    rooted = svc.graph(root=ids["alpha"], include_items=False)

    assert rooted[ids["gamma"]].items == ()


def test_graph_rooted_with_items_carries_the_subtree_items() -> None:
    """The default form carries the items of the categories it kept."""
    svc, ids = _subtree_fixture()
    item = svc.items.create(name="lion", external_id="lion")
    svc.items.place_in(item.item_id, ids["gamma"])

    rooted = svc.graph(root=ids["alpha"])

    assert [i.name for i in rooted[ids["gamma"]].items] == ["lion"]


def test_graph_rooted_at_an_unknown_category_raises() -> None:
    """An identifier the taxonomy does not hold is not-found, not an empty graph."""
    svc, _ = _subtree_fixture()

    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.graph(root=uuid4())


def test_graph_rooted_at_the_implicit_root_raises() -> None:
    """The implicit root is not addressable as a graph root.

    It is a stored row, so a validator that merely asks whether the identifier *exists* lets it
    through — and then quietly answers with the whole taxonomy, or crashes, depending on the
    assembler. The root is invisible to every public read, and this is one of them.
    """
    svc = TaxomeshService(repository=InMemoryRepository())
    svc.categories.create("Alpha")

    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.graph(root=svc._root_id)


def test_graph_rooted_at_a_category_the_enabled_filter_excludes_raises() -> None:
    """A disabled root under the default filter is not-found — not a bare ``KeyError``.

    The validating lookup does **not** apply the ``enabled`` filter: it answers from the whole
    stored corpus. So a disabled category passes validation and then is absent from the rows the
    graph is assembled from. Without a second check that gap surfaces as a builtin ``KeyError``
    carrying a bare UUID, which no caller catching ``TaxomeshError`` can handle.
    """
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    zed = svc.categories.create("Zed")
    stored = repo.find_category(zed.category_id)
    assert stored is not None
    repo.save_category(stored.model_copy(update={"enabled": False}))

    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.graph(root=zed.category_id)


def test_graph_rooted_at_an_enabled_category_under_the_disabled_filter_raises() -> None:
    """The mirror case: ``enabled=False`` excludes an enabled root, and that is not-found too."""
    svc = TaxomeshService(repository=InMemoryRepository())
    alpha = svc.categories.create("Alpha")

    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.graph(root=alpha.category_id, enabled=False)


def test_graph_rooted_terminates_on_a_cycle_in_stored_data() -> None:
    """A cycle reachable from the root terminates, and ``len`` and ``walk`` still agree.

    ``check_no_cycle`` guards the write path only; rows also arrive by direct SQL, a migration or
    a restored backup. This writes one straight through the repository to produce the shape the
    service refuses to create.
    """
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    x = svc.categories.create("X")
    y = svc.categories.create("Y")
    svc.categories.add_parent(y.category_id, x.category_id)
    repo.save_category_parent_link(
        CategoryParentLink(category_id=x.category_id, parent_category_id=y.category_id, sort_index=0)
    )

    rooted = svc.graph(root=x.category_id)

    assert len(rooted) == 2
    assert len(list(rooted.walk())) == 2
