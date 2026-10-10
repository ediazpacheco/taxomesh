"""Node identity: one object per category, compared by identity.

A category reachable through two parents is the *same* node object from each: that is what flat
storage buys, and it is stated here as ``is`` rather than ``==`` on purpose.

``CategoryNode`` is not a value object, so it defines neither ``__eq__`` nor ``__hash__`` and
keeps identity semantics. Two views of the same category taken from two *different* graphs
are different objects, because they are views of different snapshots. ``__repr__`` shows the
category's id and name and never its children, so printing a node cannot walk the graph.

Equality and representation go together, so both are pinned here.
"""

import inspect
from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from tests.service.conftest import InMemoryRepository


def build_shared_taxonomy(service: TaxomeshService) -> tuple[Category, Category, Category, Category]:
    """Build the shape the reshape exists for, and return its four categories.

    Shape::

        Alpha            Beta
          └─ Shared        └─ Shared      <- the SAME category, two parents
               └─ Leaf          └─ Leaf

    Args:
        service: The service to build in.

    Returns:
        ``(alpha, beta, shared, leaf)``.
    """
    alpha = service.categories.create("Alpha")
    beta = service.categories.create("Beta")
    shared = service.categories.create("Shared")
    leaf = service.categories.create("Leaf")
    service.categories.add_parent(shared.category_id, alpha.category_id)
    service.categories.add_parent(shared.category_id, beta.category_id)
    service.categories.add_parent(leaf.category_id, shared.category_id)
    return alpha, beta, shared, leaf


def only_child(node: CategoryNode) -> CategoryNode:
    """Return a node's single child, asserting that it has exactly one."""
    children = node.children
    assert len(children) == 1, f"expected exactly one child, got {len(children)}"
    return children[0]


class TestSharedNodeIdentity:
    """A category reachable through several parents is one object."""

    def test_the_same_category_is_the_same_object_from_each_parent(self) -> None:
        """The whole point of flat storage, stated as ``is``."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        from_alpha = only_child(graph[alpha.category_id])
        from_beta = only_child(graph[beta.category_id])
        assert from_alpha is from_beta
        assert from_alpha is graph[shared.category_id]

    def test_repeated_lookup_returns_the_same_object(self) -> None:
        """A node is materialised once and handed back, not rebuilt per access."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        assert graph[shared.category_id] is graph[shared.category_id]

    def test_everything_beneath_a_shared_node_is_shared_too(self) -> None:
        """Sharing is not limited to the node the two paths meet at."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, _shared, leaf = build_shared_taxonomy(service)

        graph = service.graph()

        via_alpha = only_child(only_child(graph[alpha.category_id]))
        via_beta = only_child(only_child(graph[beta.category_id]))
        assert via_alpha is via_beta
        assert via_alpha is graph[leaf.category_id]

    def test_a_shared_node_reports_both_parents(self) -> None:
        """``parents`` is the view a nested tree could not offer at all."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        parent_ids = {parent.category.category_id for parent in graph[shared.category_id].parents}
        assert parent_ids == {alpha.category_id, beta.category_id}

    def test_a_top_level_node_has_no_parents(self) -> None:
        """The implicit root is not a node, so a top-level category's parents are empty.

        Its stored link to the root is real — ``create`` writes one for every category — but the
        root is invisible to every public read, the graph included.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, _shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        assert graph[alpha.category_id].parents == ()


class TestNodeEqualityAndRepr:
    """Equality is identity, and ``repr`` cannot walk the graph."""

    def test_two_graphs_give_different_objects_for_one_category(self) -> None:
        """Two snapshots are two sets of views, even over identical data."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        first = service.graph()
        second = TaxomeshService(repository=service.repository).graph()

        assert first[shared.category_id] is not second[shared.category_id]
        assert first[shared.category_id] != second[shared.category_id]

    def test_a_node_equals_only_itself(self) -> None:
        """No ``__eq__`` is defined, so identity equality applies."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        assert graph[shared.category_id] == graph[shared.category_id]
        assert graph[shared.category_id] != graph[alpha.category_id]

    def test_nodes_are_hashable_by_identity(self) -> None:
        """No ``__hash__`` is defined either, so a node stays usable in a set."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        nodes = {graph[alpha.category_id], graph[beta.category_id], graph[shared.category_id]}
        assert len(nodes) == 3
        assert graph[shared.category_id] in nodes

    def test_repr_shows_the_category_and_never_the_children(self) -> None:
        """Printing a node must not walk the graph — on a deep or shared shape it would not end."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, leaf = build_shared_taxonomy(service)

        graph = service.graph()
        rendered = repr(graph[shared.category_id])

        assert str(shared.category_id) in rendered
        assert shared.name in rendered
        assert leaf.name not in rendered


class TestGraphContainerLaw:
    """Subscript raises, ``get`` never does."""

    def test_membership_and_get_agree_with_subscript(self) -> None:
        """``in`` is true exactly when subscript would not raise."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        assert shared.category_id in graph
        assert graph.get(shared.category_id) is graph[shared.category_id]

    def test_an_unknown_category_is_absent_every_way(self) -> None:
        """An identifier the snapshot never held reports absent on all three routes.

        Stated with an identifier that addresses nothing rather than with a deleted category:
        a graph is a snapshot, so a category deleted *after* it was built is still in it. That
        is the same property :meth:`test_the_graph_is_a_snapshot` pins from the other side.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()
        unknown = uuid4()

        assert unknown not in graph
        assert graph.get(unknown) is None
        with pytest.raises(TaxomeshCategoryNotFoundError):
            graph[unknown]

    def test_get_answers_a_default_for_an_absent_category(self) -> None:
        """``get`` takes a default, as every collection's ``get`` and ``dict.get`` do."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()
        fallback = object()

        assert graph.get(uuid4(), fallback) is fallback
        assert graph.get(shared.category_id, fallback) is graph[shared.category_id]

    def test_get_takes_both_arguments_by_position_only(self) -> None:
        """The key and the default are positional-only, as on a collection and on ``dict``."""
        parameters = list(inspect.signature(TaxomeshGraph.get).parameters.values())[1:]

        assert [parameter.name for parameter in parameters] == ["key", "default"]
        assert all(parameter.kind is inspect.Parameter.POSITIONAL_ONLY for parameter in parameters)
        assert parameters[1].default is None

    def test_the_graph_is_a_snapshot(self) -> None:
        """A view does not observe writes made after it was built."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()
        added = service.categories.create("Later")

        assert added.category_id not in graph


class TestEnabledFilterMembership:
    """What the ``enabled`` filter removes, and what it must not remove with it."""

    def test_a_disabled_category_is_not_in_the_default_snapshot(self) -> None:
        """The filter that the graph was built with decides membership."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)
        service.categories.update(shared.category_id, enabled=False)

        assert shared.category_id not in service.graph()
        assert service.graph(enabled=None)[shared.category_id].category.name == "Shared"

    def test_a_category_whose_only_parent_was_filtered_out_is_not_a_root(self) -> None:
        """A category with a parent is not at the top level, whatever the filter keeps.

        Parent links are filtered on **both** endpoints, so disabling ``Shared`` drops its link
        to ``Leaf`` as well. ``Leaf`` still has that parent, so it holds no link to the root and is
        not a root, as ``categories.roots()`` does not list it. The snapshot holds it, and
        ``walk()`` yields it, so ``len()`` and the walk still agree.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, leaf = build_shared_taxonomy(service)
        service.categories.update(shared.category_id, enabled=False)

        graph = service.graph()

        assert leaf.category_id in graph
        assert leaf.category_id not in {node.category.category_id for node in graph.roots}
        assert leaf.category_id in {node.category.category_id for node in graph.walk()}
        assert graph[leaf.category_id].parents == ()

    def test_navigation_never_reaches_a_category_the_snapshot_lacks(self) -> None:
        """Both-endpoints filtering, stated as the property it protects.

        Every identifier reached by navigating ``children`` or ``parents`` must itself be a
        node of that graph. A filter applied to only one end of a parent link would leave the
        other end dangling, and navigation would fail on it rather than report anything a
        caller could act on.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, beta, shared, leaf = build_shared_taxonomy(service)
        service.categories.update(shared.category_id, enabled=False)

        for enabled in (True, False, None):
            graph = service.graph(enabled=enabled)
            for category in (alpha, beta, shared, leaf):
                node = graph.get(category.category_id)
                if node is None:
                    continue
                for reached in (*node.children, *node.parents):
                    assert reached.category.category_id in graph


class TestGraphFlatConstructor:
    """The graph is built from flat maps — the one constructor tests and service share."""

    def test_a_graph_can_be_built_from_flat_data(self) -> None:
        """A hand-built graph needs no service, and its nodes behave like any other's."""
        alpha = Category(name="Alpha", slug="alpha")
        shared = Category(name="Shared", slug="shared")

        graph = TaxomeshGraph(
            categories={alpha.category_id: alpha, shared.category_id: shared},
            children={alpha.category_id: [shared.category_id]},
            parents={shared.category_id: [alpha.category_id]},
            items={},
            roots=[alpha.category_id],
        )

        assert len(graph) == 2
        assert [node.category.name for node in graph.roots] == ["Alpha"]
        assert only_child(graph[alpha.category_id]) is graph[shared.category_id]
        assert graph[shared.category_id].items == ()
