"""Read-count tests for memoize priming (spec 061).

Release 060 replaced per-row resolution with batch reads, which bypass the memoized
accessors. Resolving a row as a *result* stopped priming the entry a later call needs
when that row is passed as an *argument*, so a tree walk — where every child becomes
the next call's parent — pays for each node twice.

These tests measure the case 060's own gates deliberately do not: repeated access.
060 asserts the cost of a *single cold* call, which priming must not change; this file
asserts what a *second* call costs, which is the thing that regressed.

The counting is done with the recording repository from ``test_service_no_full_scan``
rather than a new mechanism, so the numbers here are directly comparable with the
existing gates.
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category
from taxomesh.exceptions import TaxomeshCategoryNotFoundError
from taxomesh.utils.memoize import clear_all_caches
from tests.service.test_service_no_full_scan import RecordingRepository

# A single cold call to either primed method costs: one parent/item validation, one link
# read, one batch resolve. Priming writes to memory and must not change this — it is the
# same constant 060 asserts, restated here so a regression fails in this file too.
COLD_CALL_READS = 3


@pytest.fixture
def spy() -> RecordingRepository:
    return RecordingRepository()


@pytest.fixture
def svc(spy: RecordingRepository) -> TaxomeshService:
    return TaxomeshService(repository=spy)


def _category_reads(spy: RecordingRepository) -> int:
    """Reads that resolve a category row, however they were issued."""
    return spy.count_of("get_category") + spy.count_of("get_categories_by_ids")


# ---------------------------------------------------------------------------
# US1 — a second read does not re-fetch a category the first already returned
# ---------------------------------------------------------------------------


class TestPrimingFromListCategories:
    def test_fetching_a_returned_child_costs_nothing(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()

        svc.list_categories(parent_id=parent.category_id)
        spy.reset()
        result = svc.get_category(child.category_id)

        assert result.category_id == child.category_id
        assert spy.calls == []

    def test_the_returned_value_is_the_real_row(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        """A primed value must be the row itself, not a placeholder or a filtered view."""
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()

        svc.list_categories(parent_id=parent.category_id)
        primed = svc.get_category(child.category_id)

        clear_all_caches()
        spy.reset()
        direct = svc.get_category(child.category_id)
        assert primed == direct


class TestPrimingFromListCategoriesByItem:
    def test_fetching_a_returned_category_costs_nothing(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        category = svc.create_category("Holder")
        item = svc.create_item(name="Held")
        svc.place_item_in_category(item.item_id, category.category_id)
        clear_all_caches()

        svc.list_categories_by_item(item.item_id)
        spy.reset()
        result = svc.get_category(category.category_id)

        assert result.category_id == category.category_id
        assert spy.calls == []


class TestTreeWalkReadCount:
    """The headline number. Exact constants, not bounds — a bound lets a new N+1 back in."""

    @staticmethod
    def _build_tree(svc: TaxomeshService, *, breadth: int, depth: int) -> Category:
        root = svc.create_category("Root")
        frontier = [root]
        for level in range(depth):
            next_frontier = []
            for node_index, node in enumerate(frontier):
                for child_index in range(breadth):
                    child = svc.create_category(f"L{level}-N{node_index}-C{child_index}")
                    svc.add_category_parent(child.category_id, node.category_id)
                    next_frontier.append(child)
            frontier = next_frontier
        return root

    @staticmethod
    def _walk(svc: TaxomeshService, root_id: UUID) -> int:
        """Walk the tree node by node, exactly as a path-building caller would."""
        seen = 0
        queue = [root_id]
        while queue:
            current = queue.pop()
            for child in svc.list_categories(parent_id=current):
                seen += 1
                queue.append(child.category_id)
        return seen

    def test_walk_pays_exactly_one_validation_whatever_the_tree(
        self, spy: RecordingRepository, svc: TaxomeshService
    ) -> None:
        """One link read per call, one batch resolve per non-empty call, ONE validation.

        The single validation is the walk's own root: it is never returned as anybody's
        child, so nothing primes it and its lookup is a genuine miss. Every other node
        arrives as a result first and is a cache hit when it becomes the next call's
        parent — that is precisely what priming restores.

        Asserted as exact constants. A bound would let a new N+1 back in underneath it.
        """
        root = self._build_tree(svc, breadth=3, depth=2)  # 3 + 9 = 12 nodes, 13 calls
        clear_all_caches()
        spy.reset()

        visited = self._walk(svc, root.category_id)

        assert visited == 12
        # 13 calls: 1 root + 12 nodes. 4 are non-empty (root + the 3 level-1 nodes).
        assert spy.count_of("list_category_parent_links") == 13
        assert spy.count_of("get_categories_by_ids") == 4
        assert spy.count_of("get_category") == 1

    def test_validation_count_does_not_grow_with_the_tree(
        self, spy: RecordingRepository, svc: TaxomeshService
    ) -> None:
        """The constant above is genuinely constant: a bigger, deeper tree still pays 1.

        Without priming this number tracks the node count, which is the regression.
        """
        root = self._build_tree(svc, breadth=4, depth=3)  # 4 + 16 + 64 = 84 nodes
        clear_all_caches()
        spy.reset()

        visited = self._walk(svc, root.category_id)

        assert visited == 84
        assert spy.count_of("get_category") == 1

    def test_walk_cost_does_not_grow_with_a_second_pass(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        root = self._build_tree(svc, breadth=3, depth=2)
        clear_all_caches()

        self._walk(svc, root.category_id)
        spy.reset()
        self._walk(svc, root.category_id)

        # Second pass inside the TTL: list_categories itself is memoized, so nothing repeats.
        assert spy.calls == []


# ---------------------------------------------------------------------------
# US2 — release 060 is untouched
# ---------------------------------------------------------------------------


class TestColdCallCostUnchanged:
    """FR-005: priming writes to memory, so a cold call must cost exactly what 060 asserts."""

    def test_list_categories_cold_call(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()
        spy.reset()

        svc.list_categories(parent_id=parent.category_id)

        assert len(spy.calls) == COLD_CALL_READS

    def test_list_categories_by_item_cold_call(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        category = svc.create_category("Holder")
        item = svc.create_item(name="Held")
        svc.place_item_in_category(item.item_id, category.category_id)
        clear_all_caches()
        spy.reset()

        svc.list_categories_by_item(item.item_id)

        assert len(spy.calls) == COLD_CALL_READS


# ---------------------------------------------------------------------------
# US3 — cached values stay correct
# ---------------------------------------------------------------------------


class TestPrimedEntriesStayCorrect:
    def test_a_write_invalidates_a_primed_entry(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()
        svc.list_categories(parent_id=parent.category_id)

        svc.update_category(child.category_id, name="Renamed")
        spy.reset()
        result = svc.get_category(child.category_id)

        assert result.name == "Renamed"
        assert spy.count_of("get_category") == 1, "a write must not leave a stale primed entry"

    def test_an_absent_row_is_not_primed(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        """FR-004: priming must never manufacture a hit for a row the batch did not return."""
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()
        svc.list_categories(parent_id=parent.category_id)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            svc.get_category(uuid4())

    def test_a_disabled_child_is_primed_with_its_true_value(
        self, spy: RecordingRepository, svc: TaxomeshService
    ) -> None:
        """The batch is deliberately unfiltered; the enabled filter must not leak into the cache."""
        parent = svc.create_category("Parent")
        child = svc.create_category("Child")
        svc.add_category_parent(child.category_id, parent.category_id)
        svc.update_category(child.category_id, enabled=False)
        clear_all_caches()

        visible = svc.list_categories(parent_id=parent.category_id, enabled=True)
        assert visible == [], "precondition: the disabled child is filtered out of the result"

        spy.reset()
        fetched = svc.get_category(child.category_id)
        assert fetched.enabled is False
        assert spy.calls == [], "the filtered-out row was still resolved, so it should be primed"


class TestPrimingAcrossBackends:
    """FR-008: the behaviour must hold on every backend, not just the in-memory fixture.

    Read counts cannot be spied on the real adapters, so this asserts the observable
    contract instead: the value served after a batch read is the true row, and a write
    still invalidates it.
    """

    def test_value_and_invalidation(self, service: TaxomeshService) -> None:
        parent = service.create_category("Parent")
        child = service.create_category("Child")
        service.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()

        service.list_categories(parent_id=parent.category_id)
        assert service.get_category(child.category_id).name == "Child"

        service.update_category(child.category_id, name="Renamed")
        assert service.get_category(child.category_id).name == "Renamed"


# ---------------------------------------------------------------------------
# US4 — the item path is left alone
# ---------------------------------------------------------------------------


class TestItemPathIsNotPrimed:
    """FR-007 / SC-006. This is a gate, not an omission.

    Priming items measured at 108 MB on a real corpus against 0.17 MB for categories,
    for no measured benefit, and is reachable through a public unauthenticated endpoint
    on at least one deployment. If a later change adds item priming as an "obvious
    symmetry", this test is the signal that it was considered and refused.
    """

    def test_listing_items_primes_nothing(self, spy: RecordingRepository, svc: TaxomeshService) -> None:
        category = svc.create_category("Holder")
        item = svc.create_item(name="Held")
        svc.place_item_in_category(item.item_id, category.category_id)
        clear_all_caches()

        svc.list_items(category_id=category.category_id)
        spy.reset()
        result = svc.get_item(item.item_id)

        assert result.item_id == item.item_id
        assert spy.count_of("get_item") == 1, "list_items must not prime the per-item cache"
