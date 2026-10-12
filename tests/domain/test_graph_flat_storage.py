"""Flat storage: the graph holds one node per stored category.

A graph that rendered a DAG as a nested tree would rebuild a category reachable through several
parents once per path. For k stacked diamonds that is ``2**(k + 2) - 3`` nodes against ``3k + 1``
stored categories: 25 categories would build 1 021 nodes and 61 would build 4 194 301. A user
reaches that shape with ordinary ``add_parent`` calls, since every link passes ``check_no_cycle``.

This file pins the **storage** side: the graph holds exactly as many nodes as there are stored
categories, whatever the shape. The diamond is a top category, then per level two parents under
every previous id and one joining category under both.

**Navigation is deliberately not pinned to the same number.** Walking ``children`` from the roots
still reaches a shared subtree once per path, because that is what a path traversal means. The
exponential *emission* that results is the serializer's problem, not
storage's. Storage and navigation are independent concerns, and the last test below records that
split rather than hiding it.

k runs to 6 — 19 categories, 253 nodes, instant. The formula is proven by the small ks; k = 20
would be 4 194 301 nodes and is never built here.
"""

from collections.abc import Sequence

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.graph import CategoryNode
from tests.service.conftest import InMemoryRepository

# Each diamond stores three categories — two parents and the one joining them — on top of the
# single category the stack starts from.
STORED_PER_DIAMOND = 3
DIAMOND_KS = [1, 2, 3, 4, 5, 6]


def stack_diamonds(service: TaxomeshService, k: int) -> None:
    """Build k stacked diamonds, the shape the recorded measurement used.

    Each level adds two categories under every id of the level above and one joining category
    under both, so the level below is reachable through two paths and the stacking compounds.

    Args:
        service: The service to build in.
        k: How many diamonds to stack.
    """
    top = service.categories.create("top")
    previous = [top.category_id]
    for level in range(k):
        left = service.categories.create(f"a{level}")
        right = service.categories.create(f"b{level}")
        for parent_id in previous:
            service.categories.add_parent(left.category_id, parent_id)
            service.categories.add_parent(right.category_id, parent_id)
        join = service.categories.create(f"j{level}")
        service.categories.add_parent(join.category_id, left.category_id)
        service.categories.add_parent(join.category_id, right.category_id)
        previous = [join.category_id]


def count_by_path(nodes: Sequence[CategoryNode]) -> int:
    """Count nodes the way a path traversal reaches them — a shared subtree once per path."""
    return sum(1 + count_by_path(node.children) for node in nodes)


class TestFlatStorage:
    """Each stored category is materialised exactly once, whatever the shape."""

    @pytest.mark.parametrize("k", DIAMOND_KS)
    def test_holds_one_node_per_stored_category(self, k: int) -> None:
        """``len(g)`` is the stored category count, not the number of paths through them."""
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, k)

        graph = service.graph()

        assert len(graph) == STORED_PER_DIAMOND * k + 1

    @pytest.mark.parametrize("k", DIAMOND_KS)
    def test_the_node_count_agrees_with_the_category_container(self, k: int) -> None:
        """The graph counts what ``service.categories`` counts — the same rows, counted once.

        Stated against the container rather than the arithmetic above, so the two cannot drift:
        both exclude the implicit root, and every category built here is enabled.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, k)

        graph = service.graph()

        assert len(graph) == len(service.categories)

    @pytest.mark.parametrize("k", DIAMOND_KS)
    def test_a_path_traversal_still_reaches_a_shared_subtree_once_per_path(self, k: int) -> None:
        """Storage is deduplicated; a walk down ``children`` is still per path.

        This is not a defect being pinned in place — it is the distinction the contract draws.
        Flat storage fixes how many nodes *exist*; how many a path traversal *visits* is
        unchanged, and bounding what serialization emits from it is the serializer's job.
        Recording it here means a future change to either side is visible rather than silent.
        """
        service = TaxomeshService(repository=InMemoryRepository())
        stack_diamonds(service, k)

        graph = service.graph()

        assert count_by_path(graph.roots) == 2 ** (k + 2) - 3
