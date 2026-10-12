"""Navigation from a node: its ancestors and its descendants, and the one walk under both.

A node answers ``parents`` and ``children``, one level each. ``ancestors()`` and
``descendants()`` answer every level: depth-first in stored order, each category once, the node
itself left out. They return tuples, as every other sequence the library hands out.

The graphs here are assembled by hand from flat maps, through the constructor the service uses,
so the stored order of every parent and child list is the order written below. A graph the
service builds orders parents by the port's link order, which depends on generated identifiers.

One generator in ``domain/dag.py`` does the walking for the graph, for its nodes and for a rooted
read. Its own cases come first: they pin what the three callers share.
"""

import inspect
from collections.abc import Iterator, Mapping, Sequence
from uuid import UUID, uuid4

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.dag import depth_first
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category
from tests.domain.test_graph_shared_nodes import build_shared_taxonomy
from tests.domain.test_graph_walk import orphan_category
from tests.service.conftest import InMemoryRepository


def hand_built_graph(
    names: Sequence[str],
    children: Mapping[str, Sequence[str]],
    roots: Sequence[str],
) -> tuple[TaxomeshGraph, dict[str, UUID]]:
    """Assemble a graph from names, with every parent list in the order the children list it.

    Args:
        names: Every category in the graph.
        children: Each category's children, by name, in stored order. A category's parents are
            listed in the order the parents appear here.
        roots: The top-level categories, by name, in order.

    Returns:
        The graph, and each name's identifier.
    """
    ids = {name: uuid4() for name in names}
    parents: dict[UUID, list[UUID]] = {}
    for parent, kids in children.items():
        for kid in kids:
            parents.setdefault(ids[kid], []).append(ids[parent])
    graph = TaxomeshGraph(
        categories={ids[name]: Category(category_id=ids[name], name=name) for name in names},
        children={ids[parent]: [ids[kid] for kid in kids] for parent, kids in children.items()},
        parents=parents,
        items={},
        roots=[ids[name] for name in roots],
    )
    return graph, ids


def two_parent_diamond() -> tuple[TaxomeshGraph, dict[str, UUID]]:
    """Build two top-level categories, a category under both, and a diamond under the first.

    Shape::

        Music                 Genres
          ├─ Jazz ─────────────┘        Jazz has two parents: Music, then Genres
          │    └─ Bop
          └─ Blues
               └─ Bop                   the SAME Bop: Music reaches it twice

    Returns:
        The graph, and each name's identifier.
    """
    return hand_built_graph(
        ["Music", "Genres", "Jazz", "Blues", "Bop"],
        {"Music": ["Jazz", "Blues"], "Genres": ["Jazz"], "Jazz": ["Bop"], "Blues": ["Bop"]},
        ["Music", "Genres"],
    )


def stored_cycle() -> tuple[TaxomeshGraph, dict[str, UUID]]:
    """Build a cycle under a top-level category, as stored data can hold one.

    Shape: ``Top → A → B → A``. The service refuses to write the last link; storage can still
    hold it, having been written by direct SQL, a migration or a restored backup.

    Returns:
        The graph, and each name's identifier.
    """
    return hand_built_graph(["Top", "A", "B"], {"Top": ["A"], "A": ["B"], "B": ["A"]}, ["Top"])


def names(nodes: Sequence[CategoryNode]) -> list[str]:
    """Return the nodes' category names, in order."""
    return [node.category.name for node in nodes]


class TestDepthFirst:
    """The one generator: seeds included, one visited set across them, stored order."""

    def test_it_yields_each_seed_and_what_it_reaches_in_stored_order(self) -> None:
        """Depth-first: a seed, then its first neighbour's whole branch, then the next."""
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()

        assert list(depth_first([a], {a: [b, d], b: [c]})) == [a, b, c, d]

    def test_one_visited_set_spans_the_seeds(self) -> None:
        """A node a first seed reached is not yielded again from a second, nor is a seed."""
        a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()

        assert list(depth_first([a, b, c], {a: [c], b: [c, d]})) == [a, c, b, d]

    def test_a_cycle_ends_the_walk(self) -> None:
        """A neighbour already yielded is skipped, so a cycle cannot loop."""
        a, b = uuid4(), uuid4()

        assert list(depth_first([a], {a: [b], b: [a]})) == [a, b]

    def test_it_is_lazy(self) -> None:
        """An iterator, so a caller can stop early and pay for no more than it read."""
        a = uuid4()

        walk = depth_first([a], {})

        assert isinstance(walk, Iterator)
        assert next(walk) == a


class TestDescendants:
    """Every category below a node, each once, depth-first in stored order."""

    def test_a_diamond_yields_its_shared_category_once(self) -> None:
        """Music reaches Bop through Jazz and through Blues; Bop comes once, where first reached."""
        graph, ids = two_parent_diamond()

        assert names(graph[ids["Music"]].descendants()) == ["Jazz", "Bop", "Blues"]

    def test_a_category_with_two_parents_is_below_each(self) -> None:
        """Genres holds Jazz too, and so everything below Jazz."""
        graph, ids = two_parent_diamond()

        assert names(graph[ids["Genres"]].descendants()) == ["Jazz", "Bop"]

    def test_a_leaf_has_none(self) -> None:
        """The node itself is left out, so a leaf answers an empty tuple."""
        graph, ids = two_parent_diamond()

        assert graph[ids["Bop"]].descendants() == ()

    def test_the_answer_is_a_tuple_of_the_graphs_own_nodes(self) -> None:
        """A tuple, as every sequence the library returns, holding the nodes subscript returns."""
        graph, ids = two_parent_diamond()

        descendants = graph[ids["Jazz"]].descendants()

        assert isinstance(descendants, tuple)
        assert descendants[0] is graph[ids["Bop"]]

    def test_a_stored_cycle_ends_and_leaves_the_node_out(self) -> None:
        """A reaches itself through B; the walk stops there, and A is not its own descendant."""
        graph, ids = stored_cycle()

        assert names(graph[ids["A"]].descendants()) == ["B"]
        assert names(graph[ids["B"]].descendants()) == ["A"]
        assert names(graph[ids["Top"]].descendants()) == ["A", "B"]

    def test_nothing_outside_the_subtree_is_a_descendant(self) -> None:
        """Beta and an orphan no root reaches stay out: the sweep of ``walk()`` is not here."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, _shared, _leaf = build_shared_taxonomy(service)
        orphan_category(service, "Orphan")

        graph = service.graph()

        assert names(graph[alpha.category_id].descendants()) == ["Shared", "Leaf"]


class TestAncestors:
    """Every category above a node, each once, depth-first in stored order."""

    def test_a_diamond_yields_its_shared_ancestor_once(self) -> None:
        """Bop reaches Music through Jazz and through Blues; Music comes once, where first reached.

        Bop's parents are Jazz, then Blues. Jazz's whole branch comes first: its parents, Music
        then Genres. Blues comes last, and its parent Music is already there.
        """
        graph, ids = two_parent_diamond()

        assert names(graph[ids["Bop"]].ancestors()) == ["Jazz", "Music", "Genres", "Blues"]

    def test_a_category_with_two_parents_has_both(self) -> None:
        """In the order its parent links are stored."""
        graph, ids = two_parent_diamond()

        assert names(graph[ids["Jazz"]].ancestors()) == ["Music", "Genres"]

    def test_a_top_level_category_has_none(self) -> None:
        """The implicit root is no node, so a top-level category answers an empty tuple."""
        graph, ids = two_parent_diamond()

        assert graph[ids["Music"]].ancestors() == ()

    def test_the_answer_is_a_tuple_of_the_graphs_own_nodes(self) -> None:
        """A tuple of the nodes subscript returns, the same object for the same category."""
        graph, ids = two_parent_diamond()

        ancestors = graph[ids["Jazz"]].ancestors()

        assert isinstance(ancestors, tuple)
        assert ancestors[0] is graph[ids["Music"]]

    def test_a_stored_cycle_ends_and_leaves_the_node_out(self) -> None:
        """A's parents are Top and B, and B's is A; the walk stops at A and does not yield it."""
        graph, ids = stored_cycle()

        assert names(graph[ids["A"]].ancestors()) == ["Top", "B"]
        assert names(graph[ids["B"]].ancestors()) == ["A", "Top"]

    def test_a_rooted_graph_holds_only_the_ancestors_inside_it(self) -> None:
        """A graph rooted at Alpha does not hold Beta, so Shared's other parent is not an ancestor."""
        service = TaxomeshService(repository=InMemoryRepository())
        alpha, _beta, _shared, leaf = build_shared_taxonomy(service)

        rooted = service.graph(root=alpha.category_id)

        assert names(rooted[leaf.category_id].ancestors()) == ["Shared", "Alpha"]
        assert rooted[alpha.category_id].ancestors() == ()


class TestWalkTakesNoStart:
    """``walk()`` enumerates the whole snapshot; a node's descendants are ``descendants()``."""

    def test_walk_takes_no_parameter(self) -> None:
        """One enumerator with one meaning: every node, each once."""
        assert list(inspect.signature(TaxomeshGraph.walk).parameters) == ["self"]

    def test_walk_still_reaches_every_node_of_a_stored_cycle(self) -> None:
        """Built on the same generator, it keeps its own promise: each node once, then it ends."""
        graph, _ids = stored_cycle()

        assert names(list(graph.walk())) == ["Top", "A", "B"]
