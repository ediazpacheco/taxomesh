"""A rooted graph holds the descendant map a walk over ``categories.list`` builds.

The descendant map of a category maps it, and every category a node-by-node walk from it visits,
to its ordered children. The reference walk below builds it from ``categories.list(parent=…)``:
depth-first, expanding each category once, and visiting children in the order the listing returns
them. The map a rooted graph gives must equal it: cycle-safe, keeping every parent–child
relationship of a multi-parent category, and raising the error the walk would raise first, with
the same message. Each of those gets its own assertion, against the reference walk rather than a
recorded literal.

**The graph is rooted.** ``walk()`` descends the roots and *then sweeps every node that route did
not reach*, orphans included. Over a whole-taxonomy graph that sweep separates it from a map
rooted at one category, which
:meth:`TestTheRootedGraphIsTheRightGraph.test_the_walk_over_the_whole_graph_over_reports`
asserts. A graph built with ``service.graph(root=…)`` has its flat maps pruned to the subtree, so
its own walk *is* the subtree and the sweep finds nothing more.

``graph(root=…)`` is used rather than a node of ``graph()`` and its ``descendants()``, which
reproduce the same map, because it costs a constant 3 storage reads rather than loading the whole
taxonomy. That cost is
gated in ``tests/service/``, where the counting fixture lives.

**Two cases where the graph differs from the reference walk**, both pinned in
:class:`TestParityBoundaries`: the implicit root is not addressable as a subtree root though the
reference walk descends from it, and a root the ``enabled`` filter excludes is refused rather than
walked from.
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from tests.domain.test_graph_deep_chain import CHAIN_LENGTH, build_chain
from tests.domain.test_graph_flat_storage import DIAMOND_KS, stack_diamonds
from tests.domain.test_graph_shared_nodes import build_shared_taxonomy
from tests.domain.test_graph_walk import orphan_category, store_cycle
from tests.service.conftest import InMemoryRepository


def reference_walk(
    service: TaxomeshService, category_id: UUID, *, enabled: bool | None = True
) -> dict[UUID, list[Category]]:
    """Build the descendant map with the reference walk.

    Depth-first from ``category_id``, expanding each category exactly once — which is also what
    makes it cycle-safe — and taking each category's children from ``categories.list``. Written
    iteratively so that a chain deeper than the interpreter's recursion limit is walked rather than
    raising ``RecursionError``, since one of the shapes below is 1 200 deep.

    Args:
        service: The service to walk.
        category_id: The category to walk from; it is a key of the result too.
        enabled: The filter to apply, passed through to ``categories.list`` unchanged.

    Returns:
        Each visited category's identifier mapped to its ordered children; leaves map to an
        empty list.

    Raises:
        TaxomeshCategoryNotFoundError: If ``category_id`` addresses no stored category — raised
            by the first ``categories.list`` call, which is what "the error the reference walk
            would raise first" means.
    """
    visited: dict[UUID, list[Category]] = {}
    stack = [category_id]
    while stack:
        current_id = stack.pop()
        if current_id in visited:
            continue
        children = list(service.categories.list(parent=current_id, enabled=enabled))
        visited[current_id] = children
        # Reversed, so that popping restores the order ``categories.list`` returned them in.
        stack.extend(reversed([child.category_id for child in children]))
    return visited


def descendant_map(graph: TaxomeshGraph, *, start: UUID | None = None) -> dict[UUID, list[Category]]:
    """Build the same map from a graph, walking it and reading each node's children.

    Args:
        graph: The snapshot to read. Rooted at the category of interest for a parity comparison;
            a whole-taxonomy graph reports its orphans here too.
        start: The category whose node and :meth:`CategoryNode.descendants` are read. ``None``
            walks the whole snapshot, which over a rooted graph is the subtree.

    Returns:
        Each walked category's identifier mapped to its children's categories, in stored order.
    """
    nodes = graph.walk() if start is None else (graph[start], *graph[start].descendants())
    return {node.category.category_id: [child.category for child in node.children] for node in nodes}


def categories_by_name(service: TaxomeshService) -> dict[str, Category]:
    """Index a service's categories by name, for the shapes whose builder returns no identifiers."""
    return {category.name: category for category in service.categories.list(enabled=None)}


class TestDescendantMapParity:
    """The descendant map is reproducible from a rooted graph, shape for shape."""

    def test_the_map_reproduces_on_a_shared_taxonomy(self) -> None:
        """The base case: a category shared between two parents, walked from one of them."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, _shared, _leaf = build_shared_taxonomy(service)

        rooted = service.graph(root=alpha.category_id)

        assert descendant_map(rooted) == reference_walk(service, alpha.category_id)

    def test_the_map_reproduces_rooted_below_a_multi_parent_category(self) -> None:
        """Rooting *at* a category with parents outside the subtree changes neither side.

        The map is built from children alone, so the pruned-away parents cannot affect it — but
        they are what a subtree read is most likely to get wrong, which is why this shape is
        stated rather than assumed to follow from the one above.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, 2)
        join = categories_by_name(service)["j0"]

        rooted = service.graph(root=join.category_id)

        assert descendant_map(rooted) == reference_walk(service, join.category_id)
        assert rooted[join.category_id].parents == ()

    @pytest.mark.parametrize("k", DIAMOND_KS)
    def test_the_map_reproduces_on_stacked_diamonds(self, k: int) -> None:
        """The shape where a path traversal blows up and a node-per-category walk does not."""
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, k)
        top = categories_by_name(service)["top"]

        rooted = service.graph(root=top.category_id)

        assert descendant_map(rooted) == reference_walk(service, top.category_id)

    def test_the_map_reproduces_on_a_chain_deeper_than_the_recursion_limit(self) -> None:
        """Said nothing about depth; a recursive implementation of it would still fail here."""
        service = TaxomeshService(repository=InMemoryRepository())
        ids = build_chain(service, CHAIN_LENGTH)

        rooted = service.graph(root=ids[0])

        assert descendant_map(rooted) == reference_walk(service, ids[0])
        assert len(descendant_map(rooted)) == CHAIN_LENGTH

    def test_the_map_reproduces_from_a_start_halfway_down_the_chain(self) -> None:
        """A subtree read is bounded by its start, at depth as anywhere else."""
        service = TaxomeshService(repository=InMemoryRepository())
        ids = build_chain(service, CHAIN_LENGTH)
        midpoint = CHAIN_LENGTH // 2

        rooted = service.graph(root=ids[midpoint])

        assert descendant_map(rooted) == reference_walk(service, ids[midpoint])
        assert len(descendant_map(rooted)) == CHAIN_LENGTH - midpoint


class TestChildOrderParity:
    """Children come in the order ``categories.list`` returns them."""

    def test_every_entry_lists_its_children_in_the_listing_order(self) -> None:
        """Compared against the read itself, not against a recorded literal.

        On ordinary data every sibling ties on ``sort_index``, so the order is decided by the
        identifier tie-break the repository port documents. Hard-coding the expected names would
        pin whichever category happened to be allocated the lower UUID.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, 3)
        top = categories_by_name(service)["top"]

        produced = descendant_map(service.graph(root=top.category_id))

        for category_id, children in produced.items():
            listed = service.categories.list(parent=category_id)
            assert [child.category_id for child in children] == [child.category_id for child in listed]

    def test_a_reordered_parent_is_followed(self) -> None:
        """The order is read from the links, so changing them changes both sides together."""
        service = TaxomeshService(repository=InMemoryRepository())
        parent = service.categories.create("Parent")
        first = service.categories.create("First")
        second = service.categories.create("Second")
        service.categories.add_parent(first.category_id, parent.category_id)
        service.categories.add_parent(second.category_id, parent.category_id)
        service.categories.reorder(parent.category_id, [second.category_id, first.category_id])

        produced = descendant_map(service.graph(root=parent.category_id))

        assert [child.name for child in produced[parent.category_id]] == ["Second", "First"]
        assert produced == reference_walk(service, parent.category_id)


class TestMultiParentEdgesAreKept:
    """Every parent–child relationship of a multi-parent category survives."""

    def test_a_category_under_two_parents_in_the_subtree_is_listed_under_both(self) -> None:
        """The clause a deduplicating implementation would quietly break.

        The join of a diamond is walked once — it is one node — but it is a child of both arms,
        and the map must say so twice.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, 1)
        by_name = categories_by_name(service)
        top, left, right, join = by_name["top"], by_name["a0"], by_name["b0"], by_name["j0"]

        produced = descendant_map(service.graph(root=top.category_id))

        parents_listing_the_join = [
            category_id
            for category_id, children in produced.items()
            if join.category_id in [child.category_id for child in children]
        ]
        assert sorted(parents_listing_the_join, key=str) == sorted([left.category_id, right.category_id], key=str)
        assert produced == reference_walk(service, top.category_id)


class TestCycleSafety:
    """A cycle present in stored data ends both walks the same way."""

    def test_a_stored_cycle_terminates_and_matches_the_reference_walk(self) -> None:
        """Written through the port, since ``add_parent`` refuses to create one.

        Both sides expand each category exactly once, so the cycle's closing edge is reported as
        a child relationship and not followed a second time.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        top = service.categories.create("Top")
        first = service.categories.create("A")
        second = service.categories.create("B")
        service.categories.add_parent(first.category_id, top.category_id)
        service.categories.add_parent(second.category_id, first.category_id)
        store_cycle(service, first.category_id, second.category_id)

        produced = descendant_map(service.graph(root=top.category_id))

        assert produced == reference_walk(service, top.category_id)
        assert [child.name for child in produced[second.category_id]] == ["A"]


class TestErrorParity:
    """The same error, with the same message, as the reference walk raises first."""

    def test_an_unknown_category_raises_what_the_reference_walk_raises(self) -> None:
        """Type and message compared, not merely the type."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)
        unknown = uuid4()

        with pytest.raises(TaxomeshCategoryNotFoundError) as reference_error:
            reference_walk(service, unknown)
        with pytest.raises(TaxomeshCategoryNotFoundError) as rooted_error:
            service.graph(root=unknown)

        assert str(rooted_error.value) == str(reference_error.value)
        assert str(unknown) in str(rooted_error.value)

    def test_the_error_arrives_before_any_of_the_map_is_built(self) -> None:
        """Said "would raise first"; the graph validates its root before reading anything."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph(root=uuid4())


class TestTheRootedGraphIsTheRightGraph:
    """Why the parity is taken over a rooted graph, recorded as a test rather than a comment."""

    def test_the_walk_over_the_whole_graph_over_reports(self) -> None:
        """The same expression over a *whole* graph is not the rooted map, and this is the difference.

        The walk sweeps up every node the roots did not reach, so an orphan and a
        sibling branch both appear in a map bounded to one subtree. Pinned so that
        rooting the graph cannot later be mistaken for an incidental detail.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, _shared, _leaf = build_shared_taxonomy(service)
        stray = orphan_category(service, "Orphan")

        whole = descendant_map(service.graph())

        assert whole != reference_walk(service, alpha.category_id)
        assert beta.category_id in whole
        assert stray.category_id in whole

    def test_the_walk_over_a_rooted_graph_is_the_subtree(self) -> None:
        """The same expression over a rooted graph *is* the map — the maps are pruned to it."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, _shared, _leaf = build_shared_taxonomy(service)
        stray = orphan_category(service, "Orphan")

        rooted = descendant_map(service.graph(root=alpha.category_id))

        assert rooted == reference_walk(service, alpha.category_id)
        assert beta.category_id not in rooted
        assert stray.category_id not in rooted

    def test_walking_the_whole_graph_from_a_start_agrees_on_the_map(self) -> None:
        """The other candidate reproduces the map too — it is the cost and the size that differ.

        Recorded so the choice between them stays a documented trade-off: this form reads the
        whole taxonomy to answer a question about a subtree, and its ``len()`` says so.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, _shared, _leaf = build_shared_taxonomy(service)
        orphan_category(service, "Orphan")

        whole = service.graph()
        rooted = service.graph(root=alpha.category_id)

        assert descendant_map(whole, start=alpha.category_id) == reference_walk(service, alpha.category_id)
        assert descendant_map(whole, start=alpha.category_id) == descendant_map(rooted)
        assert len(whole) > len(rooted)


class TestParityBoundaries:
    """Where the graph deliberately differs from the reference walk, and why."""

    def test_the_implicit_root_is_not_a_subtree_root(self) -> None:
        """The reference walk, the rooted graph and the whole graph's subscript all refuse the root.

        ``categories.list`` answers not-found for the root as a parent, as every member that takes
        a category does, so the reference walk refuses it before the graph is asked.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            reference_walk(service, service._root_id)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph(root=service._root_id)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph()[service._root_id]

    def test_parity_holds_when_the_filter_admits_everything(self) -> None:
        """``enabled=None`` is passed through to both sides unchanged."""
        service = TaxomeshService(repository=InMemoryRepository())
        top = service.categories.create("Top")
        middle = service.categories.create("Mid")
        leaf = service.categories.create("Leaf")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.add_parent(leaf.category_id, middle.category_id)
        service.categories.update(middle.category_id, enabled=False)

        rooted = service.graph(root=top.category_id, enabled=None)

        assert descendant_map(rooted) == reference_walk(service, top.category_id, enabled=None)
        assert len(descendant_map(rooted)) == 3

    def test_a_disabled_branch_is_cut_from_both_sides_alike(self) -> None:
        """Under the default filter the subtree stops where the filter does.

        Parent links are filtered on both endpoints, so a disabled category takes the link to its
        child with it — and the reference walk, filtering the same way, agrees.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        top = service.categories.create("Top")
        middle = service.categories.create("Mid")
        leaf = service.categories.create("Leaf")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.add_parent(leaf.category_id, middle.category_id)
        service.categories.update(middle.category_id, enabled=False)

        rooted = service.graph(root=top.category_id)

        assert descendant_map(rooted) == reference_walk(service, top.category_id)
        assert descendant_map(rooted) == {top.category_id: []}

    def test_a_root_the_filter_excludes_is_refused_rather_than_walked_from(self) -> None:
        """The second boundary: ``enabled=False`` has no rooted counterpart for an enabled category.

        The reference walk would map it — ``categories.list`` filters only the *children* it
        returns, never the parent it was given. A rooted graph has to hold its own root, so a
        filter that excludes it leaves nothing to root at.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        top = service.categories.create("Top")
        middle = service.categories.create("Mid")
        service.categories.add_parent(middle.category_id, top.category_id)
        service.categories.update(middle.category_id, enabled=False)

        assert top.category_id in reference_walk(service, top.category_id, enabled=False)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph(root=top.category_id, enabled=False)
