"""Depth: a chain deeper than the interpreter's recursion limit.

A graph built by recursing once per level would raise ``RecursionError`` on a deep enough chain
before any caller saw a node. ``RecursionError`` is a builtin, not a ``TaxomeshError``, so a caller
handling this library's own exceptions cannot catch it, which is why depth is a correctness
property here and not a performance note.

**Three legs are pinned here:** building, walking *and* serializing, since
``contrib.api.serializers.graph_to_dict`` descends iteratively as well.

The chain is stored through the repository port. ``categories.create`` plus ``add_parent``
produces the identical stored shape — the graph cannot tell the two apart — but costs 1.3s against
0.04s, all of it in write paths this file does not test.

No recursive helper is used to check the result: six exist across the suite, and every one of them
would raise on this shape for reasons that have nothing to do with what is being tested.
"""

import sys
from uuid import UUID, uuid4

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api.serializers import graph_to_dict
from taxomesh.domain.models import Category, CategoryParentLink
from tests.service.conftest import InMemoryRepository

# Deeper than the default recursion limit of 1000.
CHAIN_LENGTH = 1200


def build_chain(service: TaxomeshService, length: int) -> list[UUID]:
    """Store one chain of categories, each the only child of the one before it.

    Args:
        service: The service whose repository receives the rows.
        length: How many categories to chain.

    Returns:
        The category identifiers, from the top of the chain down to its deepest node.
    """
    repository = service.repository
    ids = [uuid4() for _ in range(length)]
    for position, category_id in enumerate(ids):
        repository.save_category(Category(category_id=category_id, name=f"c{position}"))
    repository.save_category_parent_link(CategoryParentLink(category_id=ids[0], parent_category_id=service._root_id))
    for parent_id, child_id in zip(ids, ids[1:], strict=False):
        repository.save_category_parent_link(CategoryParentLink(category_id=child_id, parent_category_id=parent_id))
    return ids


class TestDeepChain:
    """Building and walking a chain no recursive implementation could handle."""

    def test_the_chain_is_deeper_than_the_recursion_limit(self) -> None:
        """Guard the guard: were this to stop holding, every test below would prove nothing."""
        assert sys.getrecursionlimit() < CHAIN_LENGTH

    def test_building_a_deep_chain_raises_no_recursion_error(self) -> None:
        """A chain deeper than the recursion limit builds, where a recursive build would raise."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_chain(service, CHAIN_LENGTH)

        graph = service.graph()

        assert len(graph) == CHAIN_LENGTH
        assert len(graph.roots) == 1

    def test_walking_a_deep_chain_raises_no_recursion_error(self) -> None:
        """The walk is iterative, so depth costs it heap and not stack."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_chain(service, CHAIN_LENGTH)

        graph = service.graph()

        assert len(list(graph.walk())) == CHAIN_LENGTH
        assert len(list(graph.walk())) == len(graph)

    def test_a_nodes_descendants_raise_no_recursion_error(self) -> None:
        """A node's descendants go just as far down, and count only what hangs below it."""
        service = TaxomeshService(repository=InMemoryRepository())
        ids = build_chain(service, CHAIN_LENGTH)

        graph = service.graph()

        assert len(graph[ids[0]].descendants()) == CHAIN_LENGTH - 1
        midpoint = CHAIN_LENGTH // 2
        assert len(graph[ids[midpoint]].descendants()) == CHAIN_LENGTH - midpoint - 1

    def test_a_nodes_ancestors_raise_no_recursion_error(self) -> None:
        """Upward too: the deepest node has every other one above it."""
        service = TaxomeshService(repository=InMemoryRepository())
        ids = build_chain(service, CHAIN_LENGTH)

        graph = service.graph()

        assert len(graph[ids[-1]].ancestors()) == CHAIN_LENGTH - 1

    def test_serializing_a_deep_chain_raises_no_recursion_error(self) -> None:
        """The third leg: the serializer is iterative too, not only the walk.

        Descended iteratively, in the same idiom as the navigation test below, so the assertion
        cannot fail for the reason it is testing.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        build_chain(service, CHAIN_LENGTH)

        payload = graph_to_dict(service.graph())

        node = payload["roots"][0]
        depth = 1
        while node["children"]:
            node = node["children"][0]
            depth += 1

        assert depth == CHAIN_LENGTH

    def test_navigating_children_reaches_every_link_in_the_chain(self) -> None:
        """Navigation is iterative here on purpose — the suite's six recursive helpers are not reused."""
        service = TaxomeshService(repository=InMemoryRepository())
        build_chain(service, CHAIN_LENGTH)

        node = service.graph().roots[0]
        depth = 1
        while node.children:
            node = node.children[0]
            depth += 1

        assert depth == CHAIN_LENGTH
