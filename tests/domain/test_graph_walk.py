"""The walk: the graph's only node enumerator.

``len(g)`` counts the nodes a snapshot holds, and ``walk()`` enumerates them: *``len(g)`` equals
the count ``walk()`` yields*. This file pins that, together with the two properties
only an enumerator can express.

**Orphans.** A category can hold no parent link at all and still be a stored row: the service
never leaves one so, but a write below it can. It is then addressable by id and invisible from
``roots``, so a roots-down traversal alone would skip it silently. The walk does not: roots down
first, *then any node not reached that way*.

**Stored cycles.** ``check_no_cycle`` guards the write path only, so the service refuses to build
a cycle — recorded below rather than assumed. Data still arrives by direct SQL, a migration or a
restored backup, so the cycles here are written through the repository port, which runs no such
check. Two shapes are pinned, because they reach the walk by *different halves*: a two-category
cycle leaves ``roots`` **empty**, so only the orphan sweep finds it at all, while a cycle hanging
under a top-level category is reached from the roots and is where a naive recursive traversal
never returns.

One visited set does both jobs — each node once in a DAG with shared branches, and termination on
a cycle. The tests are written so that either job failing shows up on its own.
"""

from uuid import UUID

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError
from tests.domain.test_graph_flat_storage import DIAMOND_KS, stack_diamonds
from tests.domain.test_graph_shared_nodes import build_shared_taxonomy
from tests.service.conftest import InMemoryRepository


def walked_names(graph: TaxomeshGraph) -> list[str]:
    """Return the category names the walk yields, in the order it yields them.

    Args:
        graph: The snapshot to enumerate.

    Returns:
        One name per node yielded — repeated names would mean a node yielded twice.
    """
    return [node.category.name for node in graph.walk()]


def orphan_category(service: TaxomeshService, name: str) -> Category:
    """Create a category and strip, below the service, the link that makes it reachable.

    ``create`` writes a link to the implicit root for every category, and that link is the only
    thing putting a new category in ``roots``. The service never leaves a category without it, so
    the link is deleted through the repository port, as data written outside taxomesh would lack
    it. That leaves a stored row no traversal from the roots can reach — the shape the walk's
    sweep of unreached categories exists for.

    Args:
        service: The service to build in.
        name: The name for the orphaned category.

    Returns:
        The created category, now unreachable from the roots.
    """
    category = service.categories.create(name)
    service.repository.delete_category_parent_link(category.category_id, service._root_id)
    return category


def store_cycle(service: TaxomeshService, category_id: UUID, parent_id: UUID) -> None:
    """Write a parent link straight through the repository port, bypassing cycle detection.

    ``categories.add_parent`` runs ``check_no_cycle`` and refuses this link — which is the point.
    A cycle cannot be *created* through the service, but it can be *present*, having arrived by
    direct SQL, a migration or a restored backup. The port is the honest way to reproduce that:
    it is the same write the service would make, minus the domain check the service adds.

    Args:
        service: The service whose repository receives the link.
        category_id: The child end of the link.
        parent_id: The parent end of the link.
    """
    service.repository.save_category_parent_link(
        CategoryParentLink(category_id=category_id, parent_category_id=parent_id)
    )


class TestWalkEnumeratesEveryNode:
    """Every node exactly once, never in disagreement with ``len``."""

    def test_every_node_is_yielded_exactly_once(self) -> None:
        """The whole snapshot comes out, and nothing comes out twice."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()
        walked = list(graph.walk())

        assert len({id(node) for node in walked}) == len(walked)
        assert {node.category.name for node in walked} == {"Alpha", "Beta", "Shared", "Leaf"}
        assert len(walked) == len(graph)

    def test_a_shared_node_is_yielded_once_though_two_paths_reach_it(self) -> None:
        """The visited set's first job, stated on the shape that needs it."""
        service = TaxomeshService(repository=InMemoryRepository())
        _alpha, _beta, shared, _leaf = build_shared_taxonomy(service)

        graph = service.graph()

        assert len(graph[shared.category_id].parents) == 2
        assert sum(1 for node in graph.walk() if node is graph[shared.category_id]) == 1

    @pytest.mark.parametrize("k", DIAMOND_KS)
    def test_the_walk_count_equals_len_on_the_blowup_shape(self, k: int) -> None:
        """``len(g)`` and the walk agree on the shape that made them able to disagree.

        A path traversal of k stacked diamonds reaches ``2**(k + 2) - 3`` nodes. The walk yields
        each stored category once, so it stays linear in the data — and equal to ``len``.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, k)

        graph = service.graph()

        assert len(list(graph.walk())) == len(graph)

    def test_an_empty_graph_yields_nothing(self) -> None:
        """The invariant holds at zero too."""
        service = TaxomeshService(repository=InMemoryRepository())

        graph = service.graph()

        assert list(graph.walk()) == []
        assert len(graph) == 0

    def test_the_walk_is_an_iterator(self) -> None:
        """The contract says ``Iterator``, so a caller may consume it one node at a time.

        *Which* root comes first is deliberately not asserted. ``create`` gives every category the
        same root-link sort index, so top-level categories tie and the assembler resolves the tie
        by iterating a set — making the order of two roots vary from run to run. That belongs to
        the assembler, not to the walk, and pinning it here would only buy a coin-flip failure.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()
        walk = graph.walk()

        assert iter(walk) is walk
        first = next(walk)
        assert first in graph.roots
        assert len([first, *walk]) == len(graph)

    def test_the_graph_itself_is_not_iterable(self) -> None:
        """``iter(graph)`` raises ``TypeError``, so ``walk`` stays the only enumerator.

        Defining no ``__iter__`` is not enough. With ``__getitem__`` defined, Python's old sequence
        protocol would make the graph iterable anyway, and the first ``next()`` would raise a
        not-found error for the key ``0``. The call form of ``pytest.raises``, because ``mypy``
        rejects the statement ``iter(graph)`` as well.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()

        pytest.raises(TypeError, iter, graph)

    def test_the_graph_itself_is_not_reversible(self) -> None:
        """``reversed(graph)`` raises ``TypeError``, the protocol's second door closed too.

        With ``__len__`` and ``__getitem__`` defined, the same protocol would make the graph
        reversible without a ``__reversed__``, and the first ``next()`` would raise a not-found
        error for the key ``len(graph) - 1``. The call form of ``pytest.raises``, because ``mypy``
        rejects the statement ``reversed(graph)`` as well.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_shared_taxonomy(service)

        graph = service.graph()

        pytest.raises(TypeError, reversed, graph)


class TestWalkIncludesOrphans:
    """Roots down first, then anything that route cannot reach."""

    def test_an_orphan_invisible_from_the_roots_is_still_yielded(self) -> None:
        """The clause that makes ``walk`` an enumerator rather than a traversal."""
        service = TaxomeshService(repository=InMemoryRepository())
        service.categories.create("Kept")
        stray = orphan_category(service, "Orphan")

        graph = service.graph()

        assert stray.category_id not in {node.category.category_id for node in graph.roots}
        assert stray.category_id in graph
        assert sorted(walked_names(graph)) == ["Kept", "Orphan"]

    def test_len_still_equals_the_walk_count_with_an_orphan_present(self) -> None:
        """The invariant cannot be satisfied by skipping what the roots cannot reach."""
        service = TaxomeshService(repository=InMemoryRepository())
        service.categories.create("Kept")
        orphan_category(service, "Orphan")

        graph = service.graph()

        assert len(list(graph.walk())) == len(graph)

    def test_roots_are_walked_before_orphans(self) -> None:
        """Orders the two halves: roots down first, *then* the rest."""
        service = TaxomeshService(repository=InMemoryRepository())
        kept = service.categories.create("Kept")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, kept.category_id)
        orphan_category(service, "Orphan")

        names = walked_names(service.graph())

        orphan_position = names.index("Orphan")
        assert all(names.index(reachable) < orphan_position for reachable in ("Kept", "Child"))

    def test_an_orphan_brings_its_own_subtree(self) -> None:
        """The sweep descends from what it finds; it does not merely yield the stray row.

        ``add_parent`` takes the child off the top level, so its one parent is the orphan and the
        only route to it is through a category the roots cannot reach.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        service.categories.create("Kept")
        stray = orphan_category(service, "OrphanParent")
        child = service.categories.create("OrphanChild")
        service.categories.add_parent(child.category_id, stray.category_id)

        graph = service.graph()

        assert sorted(walked_names(graph)) == ["Kept", "OrphanChild", "OrphanParent"]
        assert len(list(graph.walk())) == len(graph)


class TestWalkTerminatesOnStoredCycles:
    """A cycle already in stored data ends the walk instead of hanging it."""

    def test_the_service_refuses_to_create_the_cycle_these_tests_store(self) -> None:
        """Why the cycles below are written through the port — recorded, not assumed."""
        service = TaxomeshService(repository=InMemoryRepository())
        first = service.categories.create("X")
        second = service.categories.create("Y")
        service.categories.add_parent(second.category_id, first.category_id)

        with pytest.raises(TaxomeshCyclicDependencyError):
            service.categories.add_parent(first.category_id, second.category_id)

    def test_a_cycle_invisible_from_the_roots_terminates(self) -> None:
        """Two categories parenting each other, linked to no root, are top-level by neither route.

        ``roots`` is empty, so the descent yields nothing at all and the orphan sweep is the only
        thing that reaches this cycle — the half a roots-down walk cannot cover.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        first = service.categories.create("X")
        second = service.categories.create("Y")
        service.categories.add_parent(second.category_id, first.category_id)
        store_cycle(service, first.category_id, second.category_id)
        service.repository.delete_category_parent_link(first.category_id, service._root_id)

        graph = service.graph()

        assert graph.roots == ()
        assert sorted(walked_names(graph)) == ["X", "Y"]
        assert len(list(graph.walk())) == len(graph)

    def test_a_cycle_reachable_from_a_root_terminates(self) -> None:
        """The half a naive recursive traversal never returns from."""
        service = TaxomeshService(repository=InMemoryRepository())
        top = service.categories.create("Top")
        first = service.categories.create("A")
        second = service.categories.create("B")
        service.categories.add_parent(first.category_id, top.category_id)
        service.categories.add_parent(second.category_id, first.category_id)
        store_cycle(service, first.category_id, second.category_id)

        graph = service.graph()

        assert [node.category.name for node in graph.roots] == ["Top"]
        assert sorted(walked_names(graph)) == ["A", "B", "Top"]
        assert len(list(graph.walk())) == len(graph)
