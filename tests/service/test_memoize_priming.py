"""Repeated-access read counts: category priming and read-through.

The batch reads resolve many rows at once, bypassing the memoized accessors. Two properties keep
that from costing reads on repeated access, and this file gates both:

* Resolving a row as a *result* primes the entry a later call needs when that row is passed as
  an *argument*, so on a tree walk, where every child becomes the next call's parent, each node
  is read once.
* A batch reads through the cache, so rows already cached are not read again.

The batch-read gates assert the cost of a *single cold* call. These assert what a *second* call
costs.

**The constants are measured, not chosen.** Each is asserted beside what the same pattern costs
when every row is resolved with a read of its own (``PER_ROW_*``), because the comparison is the
point, not the absolute. A different number means the implementation is wrong; do not adjust the
constant.

Counting uses the generic ``CountingRepository`` from ``conftest``, which wraps any backend,
so one constant holds on all four.
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import DEFAULT_CACHE_TTL, TaxomeshService
from taxomesh.domain.models import Category
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from taxomesh.utils import memoize as memoize_module
from taxomesh.utils.memoize import MISS, Miss
from tests.service.conftest import CountedService

# A single cold call to each batched method, as the batch-read gates fix it.
COLD_CALL_READS = 3

# What each pattern costs when every row is resolved with a read of its own.
PER_ROW_WALK_12N = 26
PER_ROW_WALK_84N = 170
PER_ROW_WALK_CONSUMER = 150
PER_ROW_MULTI_PARENT = 12
PER_ROW_FETCH_THEN_LIST = 7
PER_ROW_CATS_BY_ITEM_X40 = 85


def build_tree(svc: TaxomeshService, shape: list[int | list[int]]) -> Category:
    """Build a tree whose level *i* gives each node ``shape[i]`` children.

    A list at a level assigns a per-node breadth, which is how the consumer-shaped tree is
    described.
    """
    root = svc.categories.create("Root")
    frontier = [root]
    for level, per_node in enumerate(shape):
        nxt = []
        for n, node in enumerate(frontier):
            breadth = per_node[n] if isinstance(per_node, list) else per_node
            for c in range(breadth):
                child = svc.categories.create(f"L{level}-N{n}-C{c}")
                svc.categories.add_parent(child.category_id, node.category_id)
                nxt.append(child)
        frontier = nxt
    return root


def consumer_shape() -> list[int | list[int]]:
    """The shape of the one production corpus: 75 nodes over 3 levels, 4 -> 22 -> 48."""
    level2 = [6, 6, 5, 5]
    level3 = [3] * 4 + [2] * 18
    return [4, level2, level3]


def walk(svc: TaxomeshService, root_id: UUID) -> int:
    """Walk node by node, cycle-safe, as a path-building caller does."""
    seen: set[UUID] = set()
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in svc.categories.list(parent=current, enabled=None):
            if child.category_id not in seen:
                seen.add(child.category_id)
                stack.append(child.category_id)
    return len(seen)


class TestPrimingFromCategoryReads:
    """A row returned by a batch read is not read again."""

    def test_fetching_a_returned_child_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kids = [svc.categories.create(f"K{i}") for i in range(3)]
        for kid in kids:
            svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        listed = svc.categories.list(parent=parent.category_id)
        counting_service.reads.reset()

        for child in listed:
            assert svc.categories[child.category_id] == child
        assert counting_service.reads.total == 0

    def test_fetching_a_returned_category_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cats = [svc.categories.create(f"C{i}") for i in range(3)]
        item = svc.items.create(name="I")
        for cat in cats:
            svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        listed = svc.categories.list(item=item.item_id)
        counting_service.reads.reset()

        for category in listed:
            assert svc.categories[category.category_id] == category
        assert counting_service.reads.total == 0

    def test_the_primed_value_is_the_real_row(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)
        primed = svc.categories[kid.category_id]

        svc._cache.clear()
        assert primed == svc.categories[kid.category_id]


class TestReadThrough:
    """The batch consults the cache and fetches only the misses."""

    def test_an_all_cached_batch_reads_no_category_row(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kids = [svc.categories.create(f"K{i}") for i in range(4)]
        for kid in kids:
            svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)

        # Same listing again, with every row already cached. The link query still runs;
        # resolving the rows must not.
        svc.categories._listing.clear_cache()
        counting_service.reads.reset()
        svc.categories.list(parent=parent.category_id)

        assert counting_service.reads.count_of("map_categories_by_id") == 0
        assert counting_service.reads.count_of("find_category") == 0

    def test_a_mixed_batch_fetches_only_the_uncached_rows(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kids = [svc.categories.create(f"K{i}") for i in range(4)]
        for kid in kids:
            svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        # Warm exactly two of the four rows.
        svc.categories[kids[0].category_id]
        svc.categories[kids[1].category_id]

        svc.categories._listing.clear_cache()
        counting_service.reads.reset()
        listed = svc.categories.list(parent=parent.category_id)

        assert {c.category_id for c in listed} == {k.category_id for k in kids}
        # One batch, not one for each row that the cache does not hold, and not one for the cached ones.
        assert counting_service.reads.count_of("map_categories_by_id") == 1


class TestWalkReadCounts:
    """The walk pays exactly one category validation, its own root."""

    def test_walk_12_nodes_depth_2(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [3, 3])
        counting_service.cold()

        assert walk(svc, root.category_id) == 12
        assert counting_service.reads.total == 18
        assert counting_service.reads.total < PER_ROW_WALK_12N
        assert counting_service.reads.count_of("find_category") == 1

    def test_walk_84_nodes_depth_3(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [4, 4, 4])
        counting_service.cold()

        assert walk(svc, root.category_id) == 84
        assert counting_service.reads.total == 107
        assert counting_service.reads.total < PER_ROW_WALK_84N
        assert counting_service.reads.count_of("find_category") == 1

    def test_walk_consumer_shaped_tree(self, counting_service: CountedService) -> None:
        """103, not 0 and not 102.

        The walk's own root is nobody's child, so nothing primes it and its one validation
        is a genuine read. 102 would need every category cached beforehand, the root included,
        which priming cannot reach.
        """
        svc = counting_service.service
        root = build_tree(svc, consumer_shape())
        counting_service.cold()

        assert walk(svc, root.category_id) == 74
        assert counting_service.reads.total == 103
        assert counting_service.reads.total < PER_ROW_WALK_CONSUMER
        assert counting_service.reads.count_of("find_category") == 1

    def test_a_second_walk_inside_the_ttl_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [3, 3])
        counting_service.cold()
        walk(svc, root.category_id)

        counting_service.reads.reset()
        walk(svc, root.category_id)
        assert counting_service.reads.total == 0


class TestRemainingCategoryPatterns:
    """Every category pattern at or below its per-row cost."""

    def test_multi_parent_walk_loses_no_relationship(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = svc.categories.create("Root")
        parents = [svc.categories.create(f"P{i}") for i in range(3)]
        shared = [svc.categories.create(f"S{i}") for i in range(2)]
        for parent in parents:
            svc.categories.add_parent(parent.category_id, root.category_id)
            for child in shared:
                svc.categories.add_parent(child.category_id, parent.category_id)

        counting_service.cold()
        assert walk(svc, root.category_id) == 5
        assert counting_service.reads.total == 9
        assert counting_service.reads.total < PER_ROW_MULTI_PARENT

        # Every parent still reports both shared children — nothing was lost to dedup.
        for parent in parents:
            listed = svc.categories.list(parent=parent.category_id, enabled=None)
            assert {c.category_id for c in listed} == {c.category_id for c in shared}

    def test_fetch_children_by_id_then_list_them(self, counting_service: CountedService) -> None:
        """7 reads: priming alone would cost 8, one more than per-row resolution; read-through saves it."""
        svc = counting_service.service
        parent = svc.categories.create("P")
        kids = [svc.categories.create(f"K{i}") for i in range(5)]
        for kid in kids:
            svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories[parent.category_id]
        for kid in kids:
            svc.categories[kid.category_id]
        svc.categories.list(parent=parent.category_id)

        assert counting_service.reads.total == 7
        assert counting_service.reads.total == PER_ROW_FETCH_THEN_LIST

    def test_categories_list_by_item_over_many_items(self, counting_service: CountedService) -> None:
        """Forty items' categories cost 84 reads, where batch reads that neither prime nor read through cost 120."""
        svc = counting_service.service
        cats = [svc.categories.create(f"City{i}") for i in range(5)]
        items = [svc.items.create(name=f"M{i}") for i in range(40)]
        for index, item in enumerate(items):
            svc.items.place_in(item.item_id, cats[index % 5].category_id)
            svc.items.place_in(item.item_id, cats[(index + 1) % 5].category_id)

        counting_service.cold()
        for item in items:
            svc.categories.list(item=item.item_id)

        assert counting_service.reads.total == 84
        assert counting_service.reads.total < PER_ROW_CATS_BY_ITEM_X40


class TestColdCallCostUnchanged:
    """A single cold call costs exactly what the batch-read gates fix."""

    def test_cold_categories_list(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        for index in range(5):
            kid = svc.categories.create(f"K{index}")
            svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)
        assert counting_service.reads.total == COLD_CALL_READS

    def test_cold_categories_list_by_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        item = svc.items.create(name="I")
        for index in range(5):
            cat = svc.categories.create(f"C{index}")
            svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        svc.categories.list(item=item.item_id)
        assert counting_service.reads.total == COLD_CALL_READS

    def test_cold_items_list(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.categories.create("C")
        for index in range(20):
            item = svc.items.create(name=f"I{index}")
            svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        svc.items.list(category=cat.category_id)
        assert counting_service.reads.total == COLD_CALL_READS


class TestPrimedEntriesStayCorrect:
    """A primed entry is indistinguishable from a normally cached one."""

    def test_a_write_invalidates_a_primed_entry(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)
        svc.categories.update(kid.category_id, name="renamed")

        assert svc.categories[kid.category_id].name == "renamed"

    def test_an_expired_entry_is_absent_to_the_accessor_and_to_read_through(
        self, counting_service: CountedService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Expiry is honoured by both paths, so read-through cannot serve stale rows."""

        class FakeClock:
            now = 0.0

            def monotonic(self) -> float:
                return self.now

        clock = FakeClock()
        monkeypatch.setattr(memoize_module, "time", clock)

        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)
        assert svc.categories._lookup.cached(kid.category_id) is not MISS

        clock.now = DEFAULT_CACHE_TTL + 1.0
        assert svc.categories._lookup.cached(kid.category_id) is MISS

        # The batch must re-fetch rather than serve the expired row.
        svc.categories._listing.clear_cache()
        counting_service.reads.reset()
        svc.categories.list(parent=parent.category_id)
        assert counting_service.reads.count_of("map_categories_by_id") == 1

    def test_an_absent_row_is_not_primed(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)

        missing = uuid4()
        with pytest.raises(TaxomeshCategoryNotFoundError) as excinfo:
            svc.categories[missing]
        assert str(excinfo.value) == f"Category not found: {missing}"

    def test_a_disabled_child_is_primed_with_its_true_value(self, counting_service: CountedService) -> None:
        """The batch reads unfiltered, so a filtered-out row is still cached truthfully."""
        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)
        svc.categories.update(kid.category_id, enabled=False)

        counting_service.cold()
        assert svc.categories.list(parent=parent.category_id) == ()

        counting_service.reads.reset()
        fetched = svc.categories[kid.category_id]
        assert fetched.enabled is False
        assert counting_service.reads.total == 0

    def test_tie_breaks_are_unchanged_by_read_through(self, counting_service: CountedService) -> None:
        """Children with equal sort_index keep their relative order, warm or cold."""
        svc = counting_service.service
        parent = svc.categories.create("P")
        kids = [svc.categories.create(f"K{i}") for i in range(5)]
        for kid in kids:
            svc.categories.add_parent(kid.category_id, parent.category_id, sort_index=0)

        svc._cache.clear()
        cold_order = [c.category_id for c in svc.categories.list(parent=parent.category_id)]

        # Warm every row, then list again — now served through the cache.
        for kid in kids:
            svc.categories[kid.category_id]
        svc.categories._listing.clear_cache()
        warm_order = [c.category_id for c in svc.categories.list(parent=parent.category_id)]

        assert warm_order == cold_order


class TestItemPathIsNotPrimed:
    """Listing items must never populate the per-item cache."""

    def test_listing_items_adds_no_item_cache_entry(self, counting_service: CountedService) -> None:
        """Observed through ``cached`` — not an entry count, not the cache's internals."""
        svc = counting_service.service
        cat = svc.categories.create("C")
        items = [svc.items.create(name=f"I{i}") for i in range(5)]
        for item in items:
            svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        listed = svc.items.list(category=cat.category_id)
        assert len(listed) == 5

        for item in listed:
            assert svc.items._lookup.cached(item.item_id) is MISS

    def test_fetching_a_listed_item_costs_one_read(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.categories.create("C")
        item = svc.items.create(name="I")
        svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        svc.items.list(category=cat.category_id)
        counting_service.reads.reset()

        svc.items[item.item_id]
        assert counting_service.reads.total == 1

    def test_the_category_path_does_prime_by_contrast(self, counting_service: CountedService) -> None:
        """The asymmetry is the feature, so it is asserted rather than left implicit."""
        svc = counting_service.service
        parent = svc.categories.create("P")
        kid = svc.categories.create("K")
        svc.categories.add_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.categories.list(parent=parent.category_id)

        hit = svc.categories._lookup.cached(kid.category_id)
        assert not isinstance(hit, Miss)
        assert hit.category_id == kid.category_id


class TestItemResidual:
    """The accepted cost of leaving the item path alone, stated exactly.

    Each pattern costs at most one read more than per-row resolution for each
    ``items.list(category=…)`` call it contains. These are not aspirational bounds; they are
    the measured values.
    """

    def test_items_list_then_categories_per_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.categories.create("X")
        tags = [svc.categories.create(f"T{i}") for i in range(3)]
        items = [svc.items.create(name=f"I{i}") for i in range(20)]
        for index, item in enumerate(items):
            svc.items.place_in(item.item_id, cat.category_id)
            svc.items.place_in(item.item_id, tags[index % 3].category_id)

        counting_service.cold()
        for item in svc.items.list(category=cat.category_id):
            svc.categories.list(item=item.item_id)

        per_row = 45
        assert counting_service.reads.total == 46
        assert counting_service.reads.total - per_row == 1  # one items.list call in the pattern

    def test_items_list_then_items_subscript_per_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.categories.create("X")
        items = [svc.items.create(name=f"I{i}") for i in range(20)]
        for item in items:
            svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        for item in svc.items.list(category=cat.category_id):
            svc.items[item.item_id]

        per_row = 22
        assert counting_service.reads.total == 23
        assert counting_service.reads.total - per_row == 1

    def test_overlapping_small_item_listings(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        shared = [svc.items.create(name=f"S{i}") for i in range(3)]
        cats = [svc.categories.create(f"C{i}") for i in range(10)]
        for cat in cats:
            for item in shared:
                svc.items.place_in(item.item_id, cat.category_id)

        counting_service.cold()
        for cat in cats:
            svc.items.list(category=cat.category_id)

        per_row = 23
        assert counting_service.reads.total == 30
        assert counting_service.reads.total - per_row == 7  # ten items.list calls, seven extra
