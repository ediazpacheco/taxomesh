"""Storage reads the graph costs, as an exact constant per graph form.

The graph reads through a **memoized flat loader** keyed by ``(enabled, include_items)``, with
an **unmemoized assembler** building the node views over it. Caching the flat
rows rather than the assembled product is what keeps retention at one copy of the taxonomy
instead of one snapshot per requested root.

All four forms are pinned here:

* ``graph(include_items=False)`` — **2** reads, and **no item row touched at all**, so a caller
  drawing a navigation menu does not load every item.
* ``graph()`` — **4**, the two above plus the item placements and the items.
* ``graph(root=X, include_items=False)`` — **3**, the validation of ``X`` then the two
  structure reads, however large the subtree, where a node-by-node walk costs a read per
  category.
* ``graph(root=X)`` — **5**, the validation then the four.

The two **rooted** forms cost one read more than their unrooted counterparts — the validation
of ``root`` — and that read comes **first**, because the root is validated before the loader
runs. Validating afterwards produces the same total and a different order, so only the ordered
list tells the two implementations apart.

**The constants are measured, not chosen**, and the *ordered call list* is what carries the
weight. A total is a weak assertion: two reads is reproduced by any two reads, including the
wrong two.

Counting uses the generic ``CountingRepository`` from ``conftest``, which wraps any backend,
so one constant holds on all four.
"""

import pytest

from taxomesh.application.service import TaxomeshService
from tests.service.conftest import CountedService

# A graph WITH items issues exactly these four repository calls, in this order, once each.
GRAPH_READS = 4
GRAPH_CALLS = [
    "list_categories",
    "list_category_parent_links",
    "list_item_parent_links",
    "list_items",
]

# Of those four, these two exist only to populate ``CategoryNode.items``. A structure-only graph
# skips both, which is why they are named separately.
ITEM_READS = 2

# A structure-only graph issues the first two and nothing else. The ORDER is asserted, not
# just the count: the other read-count gates depend on the loader's call order too, so a
# reordering has to fail here rather than somewhere further away.
STRUCTURE_READS = 2
STRUCTURE_CALLS = [
    "list_categories",
    "list_category_parent_links",
]

# A graph rooted at one category costs its unrooted counterpart plus ONE validating read, and
# that read comes FIRST: ``root`` is validated before the loader runs. Validating afterwards
# produces the same total and a different list, which is the whole reason these are ordered.
#
# The validating read surfaces as ``find_category``, the port's single-row lookup. A gate
# spelling a name the port does not have would count nothing here and pass against an
# implementation issuing no validation at all.
ROOTED_STRUCTURE_READS = 3
ROOTED_STRUCTURE_CALLS = [
    "find_category",
    "list_categories",
    "list_category_parent_links",
]

ROOTED_GRAPH_READS = 5
ROOTED_GRAPH_CALLS = [
    "find_category",
    "list_categories",
    "list_category_parent_links",
    "list_item_parent_links",
    "list_items",
]


def build_tree(service: TaxomeshService, width: int, depth: int) -> list[str]:
    """Build a tree of the given shape, plus one shared node and a few items.

    Returns the names of the categories created, so a caller can assert the tree is the size
    it asked for rather than trusting the builder.
    """
    names: list[str] = []
    roots = [service.categories.create(f"r{i}") for i in range(width)]
    names.extend(c.name for c in roots)
    level = roots
    for d in range(depth):
        nxt = []
        for parent in level:
            for i in range(width):
                child = service.categories.create(f"c{d}-{parent.name}-{i}")
                service.categories.add_parent(child.category_id, parent.category_id)
                names.append(child.name)
                nxt.append(child)
        level = nxt
    # A category reachable through two parents — the shape that makes the nested tree
    # duplicate a branch, and that flat storage will materialise exactly once.
    if len(roots) >= 2 and level:
        service.categories.add_parent(level[0].category_id, roots[1].category_id)
    for i in range(5):
        item = service.items.create(f"i{i}")
        service.items.place_in(item.item_id, roots[0].category_id)
    return names


class TestWholeGraphReadCounts:
    """What a whole-taxonomy graph carrying its items costs."""

    @pytest.mark.parametrize("enabled", [True, False, None], ids=["enabled", "disabled", "all"])
    def test_costs_four_reads_whatever_the_enabled_filter(
        self, counting_service: CountedService, enabled: bool | None
    ) -> None:
        """The enabled filter changes what is returned, never how many reads it takes."""
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph(enabled=enabled)

        assert counting_service.reads.total == GRAPH_READS
        assert counting_service.reads.calls == GRAPH_CALLS

    def test_cost_does_not_grow_with_the_tree(self, counting_service: CountedService) -> None:
        """A bigger, deeper tree costs the same four reads.

        The read count is constant in the tree; the number of ``CategoryNode`` objects built is
        not, which the graph's own tests bound.
        """
        build_tree(counting_service.service, width=3, depth=2)
        counting_service.cold()

        counting_service.service.graph()

        assert counting_service.reads.total == GRAPH_READS
        assert counting_service.reads.calls == GRAPH_CALLS

    def test_the_whole_item_corpus_is_read_when_items_are_wanted(self, counting_service: CountedService) -> None:
        """Asking for items costs the whole item corpus, which ``include_items=False`` avoids.

        Two of the four reads exist only to fill ``CategoryNode.items``. A caller who needs a
        navigation menu and takes this form pays for every item in the corpus.
        ``include_items=False`` is the form that does not; see the class below.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph()

        item_reads = counting_service.reads.count_of("list_items") + counting_service.reads.count_of(
            "list_item_parent_links"
        )
        assert item_reads == ITEM_READS

    def test_a_second_call_is_free(self, counting_service: CountedService) -> None:
        """The repeat costs nothing, because the flat read behind it is memoized.

        What is memoized is the flat loader, not the assembled graph: the assembler runs again on
        the second call, and does not go back to storage.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph()
        reads_after_first = counting_service.reads.total
        counting_service.service.graph()

        assert reads_after_first == GRAPH_READS
        assert counting_service.reads.total == GRAPH_READS


class TestStructureOnlyGraphReadCounts:
    """What a graph built without items costs."""

    @pytest.mark.parametrize("enabled", [True, False, None], ids=["enabled", "disabled", "all"])
    def test_costs_two_reads_whatever_the_enabled_filter(
        self, counting_service: CountedService, enabled: bool | None
    ) -> None:
        """Structure alone costs the two category reads, in that order.

        The ordered list is the load-bearing half of this assertion. A *total* of two is
        reproduced by any two reads — including the wrong two — so a count alone would pass on
        an implementation that read the items and skipped the parent links.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph(enabled=enabled, include_items=False)

        assert counting_service.reads.total == STRUCTURE_READS
        assert counting_service.reads.calls == STRUCTURE_CALLS

    def test_loads_no_item_rows_at_all(self, counting_service: CountedService) -> None:
        """No item row is read, asserted by read count rather than by output.

        Empty ``node.items`` would also be produced by a graph that read every item row and
        then discarded it. Only the read count can tell those two apart.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph(include_items=False)

        assert counting_service.reads.count_of("list_items") == 0
        assert counting_service.reads.count_of("list_item_parent_links") == 0

    def test_cost_does_not_grow_with_the_tree(self, counting_service: CountedService) -> None:
        """A bigger, deeper tree costs the same two reads."""
        build_tree(counting_service.service, width=3, depth=2)
        counting_service.cold()

        counting_service.service.graph(include_items=False)

        assert counting_service.reads.total == STRUCTURE_READS
        assert counting_service.reads.calls == STRUCTURE_CALLS

    def test_a_second_call_is_free(self, counting_service: CountedService) -> None:
        """The structure-only form is memoized on its own key, like the whole-graph form."""
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph(include_items=False)
        counting_service.service.graph(include_items=False)

        assert counting_service.reads.total == STRUCTURE_READS

    def test_the_default_is_the_same_entry_as_asking_for_items(self, counting_service: CountedService) -> None:
        """``graph()`` and ``graph(include_items=True)`` reach one cache entry.

        ``memoize`` keys on the *actual* call shape and applies no defaults, so a form that
        reached the loader with a different argument spelling would silently cost a second full
        read while every assertion about the returned graph stayed green.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph()
        counting_service.service.graph(include_items=True)

        assert counting_service.reads.total == GRAPH_READS

    def test_the_two_forms_do_not_serve_each_other(self, counting_service: CountedService) -> None:
        """The loader is keyed by ``(enabled, include_items)``, so neither form answers the other.

        Stated as the honest cost: a structure-only graph cannot satisfy a later caller who
        wants items, and that caller pays the full four reads rather than the two it is missing.
        That is the price of keying the loader on the request instead of accumulating rows, and
        it is what bounds retention to six entries.
        """
        build_tree(counting_service.service, width=2, depth=1)
        counting_service.cold()

        counting_service.service.graph(include_items=False)
        assert counting_service.reads.total == STRUCTURE_READS

        counting_service.service.graph(include_items=True)

        assert counting_service.reads.total == STRUCTURE_READS + GRAPH_READS


class TestRootedGraphReadCounts:
    """What a graph rooted at one category costs.

    ``enabled`` is exercised over ``True`` and ``None`` only. ``False`` would filter out the very
    category being rooted at, which is not a read-count case but a not-found one — pinned for
    behaviour in ``test_service_graph.py``.
    """

    @pytest.mark.parametrize("enabled", [True, None], ids=["enabled", "all"])
    def test_rooted_structure_costs_three_reads_in_order(
        self, counting_service: CountedService, enabled: bool | None
    ) -> None:
        """The validation, then the two structure reads — in that order.

        The order is the assertion. Validating *after* the loader gives the same total of three
        and a different list, so a bare count cannot tell the two implementations apart, and only
        one of them keeps the validation cheap when the rows are already warm.
        """
        build_tree(counting_service.service, width=2, depth=1)
        root_id = counting_service.service.categories.roots()[0].category_id
        counting_service.cold()

        counting_service.service.graph(root=root_id, enabled=enabled, include_items=False)

        assert counting_service.reads.total == ROOTED_STRUCTURE_READS
        assert counting_service.reads.calls == ROOTED_STRUCTURE_CALLS

    def test_rooted_graph_with_items_costs_five_reads_in_order(self, counting_service: CountedService) -> None:
        """Carrying the items adds the same two reads it adds to the unrooted form."""
        build_tree(counting_service.service, width=2, depth=1)
        root_id = counting_service.service.categories.roots()[0].category_id
        counting_service.cold()

        counting_service.service.graph(root=root_id)

        assert counting_service.reads.total == ROOTED_GRAPH_READS
        assert counting_service.reads.calls == ROOTED_GRAPH_CALLS

    def test_cost_does_not_grow_with_the_subtree(self, counting_service: CountedService) -> None:
        """A bigger, deeper subtree costs the same three reads, where a walk costs one per node."""
        build_tree(counting_service.service, width=3, depth=2)
        root_id = counting_service.service.categories.roots()[0].category_id
        counting_service.cold()

        counting_service.service.graph(root=root_id, include_items=False)

        assert counting_service.reads.total == ROOTED_STRUCTURE_READS
        assert counting_service.reads.calls == ROOTED_STRUCTURE_CALLS

    def test_a_second_call_is_free(self, counting_service: CountedService) -> None:
        """Warm, a rooted graph costs nothing at all — the validating read is memoized too."""
        build_tree(counting_service.service, width=2, depth=1)
        root_id = counting_service.service.categories.roots()[0].category_id
        counting_service.cold()

        counting_service.service.graph(root=root_id, include_items=False)
        reads_after_first = counting_service.reads.total
        counting_service.service.graph(root=root_id, include_items=False)

        assert reads_after_first == ROOTED_STRUCTURE_READS
        assert counting_service.reads.total == ROOTED_STRUCTURE_READS

    def test_a_second_root_costs_only_its_own_validation(self, counting_service: CountedService) -> None:
        """One more root costs one read, measured rather than asserted.

        A *different* root in the same TTL window costs **one** read — the new identifier's
        validation — because the rows it is assembled from are already held. That is the whole
        reason the loader is the memoized unit and the assembler is not: a caller rendering one
        rooted graph per category pays one read apiece instead of one full taxonomy read apiece,
        and retains one copy of the taxonomy rather than one snapshot per category.
        """
        build_tree(counting_service.service, width=2, depth=1)
        roots = counting_service.service.categories.roots()
        first_id, second_id = roots[0].category_id, roots[1].category_id
        counting_service.cold()

        counting_service.service.graph(root=first_id, include_items=False)
        assert counting_service.reads.total == ROOTED_STRUCTURE_READS
        counting_service.reads.reset()

        counting_service.service.graph(root=second_id, include_items=False)

        assert counting_service.reads.total == 1
        assert counting_service.reads.calls == ["find_category"]
