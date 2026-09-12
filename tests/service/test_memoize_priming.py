"""Repeated-access read counts for spec 061: category priming and read-through.

Release 060 replaced per-row resolution with batch reads, which bypass the memoized
accessors. Two things were lost, and this file gates both:

* Resolving a row as a *result* stopped priming the entry a later call needs when that row
  is passed as an *argument* — so on a tree walk, where every child becomes the next call's
  parent, each node was read twice.
* The batch ignored the cache even when every row it needed was already in it.

060's own gates assert the cost of a *single cold* call, which this feature must not
change. These assert what a *second* call costs, which is what regressed.

**The constants are measured, not chosen.** Every one comes from
``specs/061-memoize-priming/measurements/reads.py`` (research.md R6), re-run and reproduced
2026-09-12. Each is asserted next to its ``0.1.0a49`` value, because the spec's goal is the
comparison, not the absolute. A different number means the implementation is wrong — do not
adjust the constant.

Counting uses the generic ``CountingRepository`` from ``conftest``, which wraps any backend,
so one constant holds on all four (FR-011).
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import DEFAULT_CACHE_TTL, TaxomeshService
from taxomesh.domain.models import Category
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from taxomesh.utils import memoize as memoize_module
from taxomesh.utils.memoize import MISS, Miss, clear_all_caches
from tests.service.conftest import CountedService

# A single cold call to each batched method, fixed by spec 060's gates.
COLD_CALL_READS = 3

# Reads the same pattern cost on 0.1.0a49, before 060 removed the N+1 (research.md R6).
A49_WALK_12N = 26
A49_WALK_84N = 170
A49_WALK_CONSUMER = 150
A49_MULTI_PARENT = 12
A49_FETCH_THEN_LIST = 7
A49_CATS_BY_ITEM_X40 = 85


def build_tree(svc: TaxomeshService, shape: list[int | list[int]]) -> Category:
    """Build a tree whose level *i* gives each node ``shape[i]`` children.

    Mirrors ``measurements/reads.py::tree`` exactly, so the constants transfer. A list at a
    level assigns a per-node breadth, which is how the consumer-shaped tree is described.
    """
    root = svc.create_category("Root")
    frontier = [root]
    for level, per_node in enumerate(shape):
        nxt = []
        for n, node in enumerate(frontier):
            breadth = per_node[n] if isinstance(per_node, list) else per_node
            for c in range(breadth):
                child = svc.create_category(f"L{level}-N{n}-C{c}")
                svc.add_category_parent(child.category_id, node.category_id)
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
        for child in svc.list_categories(parent_id=current, enabled=None):
            if child.category_id not in seen:
                seen.add(child.category_id)
                stack.append(child.category_id)
    return len(seen)


class TestPrimingFromCategoryReads:
    """US1 scenarios 1-2: a row returned by a batch read is not read again."""

    def test_fetching_a_returned_child_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kids = [svc.create_category(f"K{i}") for i in range(3)]
        for kid in kids:
            svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        listed = svc.list_categories(parent_id=parent.category_id)
        counting_service.reads.reset()

        for child in listed:
            assert svc.get_category(child.category_id) == child
        assert counting_service.reads.total == 0

    def test_fetching_a_returned_category_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cats = [svc.create_category(f"C{i}") for i in range(3)]
        item = svc.create_item(name="I")
        for cat in cats:
            svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        listed = svc.list_categories_by_item(item.item_id)
        counting_service.reads.reset()

        for category in listed:
            assert svc.get_category(category.category_id) == category
        assert counting_service.reads.total == 0

    def test_the_primed_value_is_the_real_row(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)
        primed = svc.get_category(kid.category_id)

        clear_all_caches()
        assert primed == svc.get_category(kid.category_id)


class TestReadThrough:
    """US1 scenarios 3-4: the batch consults the cache and fetches only the misses."""

    def test_an_all_cached_batch_reads_no_category_row(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kids = [svc.create_category(f"K{i}") for i in range(4)]
        for kid in kids:
            svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)

        # Same listing again, with every row already cached. The link query still runs;
        # resolving the rows must not.
        svc.list_categories.clear_cache()
        counting_service.reads.reset()
        svc.list_categories(parent_id=parent.category_id)

        assert counting_service.reads.count_of("get_categories_by_ids") == 0
        assert counting_service.reads.count_of("get_category") == 0

    def test_a_mixed_batch_fetches_only_the_uncached_rows(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kids = [svc.create_category(f"K{i}") for i in range(4)]
        for kid in kids:
            svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        # Warm exactly two of the four rows.
        svc.get_category(kids[0].category_id)
        svc.get_category(kids[1].category_id)

        svc.list_categories.clear_cache()
        counting_service.reads.reset()
        listed = svc.list_categories(parent_id=parent.category_id)

        assert {c.category_id for c in listed} == {k.category_id for k in kids}
        # One batch, not one per missing row, and not one for the cached ones.
        assert counting_service.reads.count_of("get_categories_by_ids") == 1


class TestWalkReadCounts:
    """SC-001: the walk pays exactly one category validation, its own root."""

    def test_walk_12_nodes_depth_2(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [3, 3])
        counting_service.cold()

        assert walk(svc, root.category_id) == 12
        assert counting_service.reads.total == 18
        assert counting_service.reads.total < A49_WALK_12N
        assert counting_service.reads.count_of("get_category") == 1

    def test_walk_84_nodes_depth_3(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [4, 4, 4])
        counting_service.cold()

        assert walk(svc, root.category_id) == 84
        assert counting_service.reads.total == 107
        assert counting_service.reads.total < A49_WALK_84N
        assert counting_service.reads.count_of("get_category") == 1

    def test_walk_consumer_shaped_tree(self, counting_service: CountedService) -> None:
        """103, not 0 — and not 102.

        The walk's own root is nobody's child, so nothing primes it and its one validation
        is a genuine read. 102 was the consumer's own figure, measured with every category
        pre-cached including the root; that is not reachable by priming.
        """
        svc = counting_service.service
        root = build_tree(svc, consumer_shape())
        counting_service.cold()

        assert walk(svc, root.category_id) == 74
        assert counting_service.reads.total == 103
        assert counting_service.reads.total < A49_WALK_CONSUMER
        assert counting_service.reads.count_of("get_category") == 1

    def test_a_second_walk_inside_the_ttl_costs_nothing(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = build_tree(svc, [3, 3])
        counting_service.cold()
        walk(svc, root.category_id)

        counting_service.reads.reset()
        walk(svc, root.category_id)
        assert counting_service.reads.total == 0


class TestRemainingCategoryPatterns:
    """SC-002: every category pattern at or below its 0.1.0a49 cost."""

    def test_multi_parent_walk_loses_no_relationship(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        root = svc.create_category("Root")
        parents = [svc.create_category(f"P{i}") for i in range(3)]
        shared = [svc.create_category(f"S{i}") for i in range(2)]
        for parent in parents:
            svc.add_category_parent(parent.category_id, root.category_id)
            for child in shared:
                svc.add_category_parent(child.category_id, parent.category_id)

        counting_service.cold()
        assert walk(svc, root.category_id) == 5
        assert counting_service.reads.total == 9
        assert counting_service.reads.total < A49_MULTI_PARENT

        # Every parent still reports both shared children — nothing was lost to dedup.
        for parent in parents:
            listed = svc.list_categories(parent_id=parent.category_id, enabled=None)
            assert {c.category_id for c in listed} == {c.category_id for c in shared}

    def test_fetch_children_by_id_then_list_them(self, counting_service: CountedService) -> None:
        """Priming alone cost 8 here, one more than 0.1.0a49. Read-through brings it to 7."""
        svc = counting_service.service
        parent = svc.create_category("P")
        kids = [svc.create_category(f"K{i}") for i in range(5)]
        for kid in kids:
            svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.get_category(parent.category_id)
        for kid in kids:
            svc.get_category(kid.category_id)
        svc.list_categories(parent_id=parent.category_id)

        assert counting_service.reads.total == 7
        assert counting_service.reads.total == A49_FETCH_THEN_LIST

    def test_list_categories_by_item_over_many_items(self, counting_service: CountedService) -> None:
        """The shape the consumer measured and rejected on 0.1.0a50: 120 reads, now 84."""
        svc = counting_service.service
        cats = [svc.create_category(f"City{i}") for i in range(5)]
        items = [svc.create_item(name=f"M{i}") for i in range(40)]
        for index, item in enumerate(items):
            svc.place_item_in_category(item.item_id, cats[index % 5].category_id)
            svc.place_item_in_category(item.item_id, cats[(index + 1) % 5].category_id)

        counting_service.cold()
        for item in items:
            svc.list_categories_by_item(item.item_id)

        assert counting_service.reads.total == 84
        assert counting_service.reads.total < A49_CATS_BY_ITEM_X40


class TestColdCallCostUnchanged:
    """SC-003: a single cold call still costs exactly what it costs on 0.1.0a50."""

    def test_cold_list_categories(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        for index in range(5):
            kid = svc.create_category(f"K{index}")
            svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)
        assert counting_service.reads.total == COLD_CALL_READS

    def test_cold_list_categories_by_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        item = svc.create_item(name="I")
        for index in range(5):
            cat = svc.create_category(f"C{index}")
            svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        svc.list_categories_by_item(item.item_id)
        assert counting_service.reads.total == COLD_CALL_READS

    def test_cold_list_items(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.create_category("C")
        for index in range(20):
            item = svc.create_item(name=f"I{index}")
            svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        svc.list_items(category_id=cat.category_id)
        assert counting_service.reads.total == COLD_CALL_READS


class TestPrimedEntriesStayCorrect:
    """US3: a primed entry is indistinguishable from a normally cached one."""

    def test_a_write_invalidates_a_primed_entry(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)
        svc.update_category(kid.category_id, name="renamed")

        assert svc.get_category(kid.category_id).name == "renamed"

    def test_an_expired_entry_is_absent_to_the_accessor_and_to_read_through(
        self, counting_service: CountedService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US3 scenario 2: expiry is honoured by both paths, so read-through cannot serve stale rows."""

        class FakeClock:
            now = 0.0

            def monotonic(self) -> float:
                return self.now

        clock = FakeClock()
        monkeypatch.setattr(memoize_module, "time", clock)

        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)
        assert svc.get_category.cached(kid.category_id) is not MISS

        clock.now = DEFAULT_CACHE_TTL + 1.0
        assert svc.get_category.cached(kid.category_id) is MISS

        # The batch must re-fetch rather than serve the expired row.
        svc.list_categories.clear_cache()
        counting_service.reads.reset()
        svc.list_categories(parent_id=parent.category_id)
        assert counting_service.reads.count_of("get_categories_by_ids") == 1

    def test_an_absent_row_is_not_primed(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)

        missing = uuid4()
        with pytest.raises(TaxomeshCategoryNotFoundError) as excinfo:
            svc.get_category(missing)
        assert str(excinfo.value) == f"Category not found: {missing}"

    def test_a_disabled_child_is_primed_with_its_true_value(self, counting_service: CountedService) -> None:
        """The batch reads unfiltered, so a filtered-out row is still cached truthfully."""
        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)
        svc.update_category(kid.category_id, enabled=False)

        counting_service.cold()
        assert svc.list_categories(parent_id=parent.category_id) == []

        counting_service.reads.reset()
        fetched = svc.get_category(kid.category_id)
        assert fetched.enabled is False
        assert counting_service.reads.total == 0

    def test_tie_breaks_are_unchanged_by_read_through(self, counting_service: CountedService) -> None:
        """Children with equal sort_index keep their relative order, warm or cold."""
        svc = counting_service.service
        parent = svc.create_category("P")
        kids = [svc.create_category(f"K{i}") for i in range(5)]
        for kid in kids:
            svc.add_category_parent(kid.category_id, parent.category_id, sort_index=0)

        clear_all_caches()
        cold_order = [c.category_id for c in svc.list_categories(parent_id=parent.category_id)]

        # Warm every row, then list again — now served through the cache.
        for kid in kids:
            svc.get_category(kid.category_id)
        svc.list_categories.clear_cache()
        warm_order = [c.category_id for c in svc.list_categories(parent_id=parent.category_id)]

        assert warm_order == cold_order


class TestItemPathIsNotPrimed:
    """US5 / FR-007: listing items must never populate the per-item cache."""

    def test_listing_items_adds_no_item_cache_entry(self, counting_service: CountedService) -> None:
        """Observed through ``cached`` — not an entry count, not the cache's internals."""
        svc = counting_service.service
        cat = svc.create_category("C")
        items = [svc.create_item(name=f"I{i}") for i in range(5)]
        for item in items:
            svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        listed = svc.list_items(category_id=cat.category_id)
        assert len(listed) == 5

        for item in listed:
            assert svc.get_item.cached(item.item_id) is MISS

    def test_fetching_a_listed_item_costs_one_read(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.create_category("C")
        item = svc.create_item(name="I")
        svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        svc.list_items(category_id=cat.category_id)
        counting_service.reads.reset()

        svc.get_item(item.item_id)
        assert counting_service.reads.total == 1

    def test_the_category_path_does_prime_by_contrast(self, counting_service: CountedService) -> None:
        """The asymmetry is the feature, so it is asserted rather than left implicit."""
        svc = counting_service.service
        parent = svc.create_category("P")
        kid = svc.create_category("K")
        svc.add_category_parent(kid.category_id, parent.category_id)

        counting_service.cold()
        svc.list_categories(parent_id=parent.category_id)

        hit = svc.get_category.cached(kid.category_id)
        assert not isinstance(hit, Miss)
        assert hit.category_id == kid.category_id


class TestItemResidual:
    """SC-007: the accepted cost of leaving the item path alone, stated exactly.

    Each pattern exceeds 0.1.0a49 by at most one read per ``list_items(category_id=…)``
    call it contains. These are not aspirational bounds — they are the measured values.
    """

    def test_list_items_then_categories_per_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.create_category("X")
        tags = [svc.create_category(f"T{i}") for i in range(3)]
        items = [svc.create_item(name=f"I{i}") for i in range(20)]
        for index, item in enumerate(items):
            svc.place_item_in_category(item.item_id, cat.category_id)
            svc.place_item_in_category(item.item_id, tags[index % 3].category_id)

        counting_service.cold()
        for item in svc.list_items(category_id=cat.category_id):
            svc.list_categories_by_item(item.item_id)

        a49 = 45
        assert counting_service.reads.total == 46
        assert counting_service.reads.total - a49 == 1  # one list_items call in the pattern

    def test_list_items_then_get_item_per_item(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        cat = svc.create_category("X")
        items = [svc.create_item(name=f"I{i}") for i in range(20)]
        for item in items:
            svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        for item in svc.list_items(category_id=cat.category_id):
            svc.get_item(item.item_id)

        a49 = 22
        assert counting_service.reads.total == 23
        assert counting_service.reads.total - a49 == 1

    def test_overlapping_small_item_listings(self, counting_service: CountedService) -> None:
        svc = counting_service.service
        shared = [svc.create_item(name=f"S{i}") for i in range(3)]
        cats = [svc.create_category(f"C{i}") for i in range(10)]
        for cat in cats:
            for item in shared:
                svc.place_item_in_category(item.item_id, cat.category_id)

        counting_service.cold()
        for cat in cats:
            svc.list_items(category_id=cat.category_id)

        a49 = 23
        assert counting_service.reads.total == 30
        assert counting_service.reads.total - a49 == 7  # ten list_items calls, seven extra
