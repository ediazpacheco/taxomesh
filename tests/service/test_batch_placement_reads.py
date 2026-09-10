"""Behaviour tests for the batched placement read paths (spec 060, finding F1).

The rewrite that removes the N+1 must be invisible to callers. These tests pin
the behaviour that has to survive it: ordering (including the tie-breaks that
only exist because of a stable re-sort), the empty and not-found paths, and the
policy for a link whose endpoint row is gone.

They run through the parametrised ``service`` fixture, so every assertion here
is made four times — once per backend.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError
from taxomesh.utils.memoize import clear_all_caches

# ---------------------------------------------------------------------------
# US1 — list_items(category_id=…) ordering
# ---------------------------------------------------------------------------


class TestListItemsOrdering:
    """FR-015: result order is unchanged by the rewrite."""

    def test_ascending_sort_index(self, service: TaxomeshService) -> None:
        category = service.create_category("Ordered")
        first = service.create_item(name="First")
        second = service.create_item(name="Second")
        third = service.create_item(name="Third")
        # Placed out of order on purpose — sort_index decides, not insertion.
        service.place_item_in_category(third.item_id, category.category_id, sort_index=2)
        service.place_item_in_category(first.item_id, category.category_id, sort_index=0)
        service.place_item_in_category(second.item_id, category.category_id, sort_index=1)
        clear_all_caches()

        result = service.list_items(category_id=category.category_id)

        assert [item.name for item in result] == ["First", "Second", "Third"]

    def test_negative_sort_index_sorts_before_zero(self, service: TaxomeshService) -> None:
        category = service.create_category("Negatives")
        below = service.create_item(name="Below")
        zero = service.create_item(name="Zero")
        above = service.create_item(name="Above")
        service.place_item_in_category(zero.item_id, category.category_id, sort_index=0)
        service.place_item_in_category(above.item_id, category.category_id, sort_index=7)
        service.place_item_in_category(below.item_id, category.category_id, sort_index=-5)
        clear_all_caches()

        result = service.list_items(category_id=category.category_id)

        assert [item.name for item in result] == ["Below", "Zero", "Above"]

    def test_duplicate_sort_index_order_matches_the_link_order(self, service: TaxomeshService) -> None:
        """Ties resolve by the repository's link ordering, preserved by a STABLE re-sort.

        Asserting the tie-break this way rather than hard-coding one keeps the test
        honest across backends, and it is what fails if someone deletes the
        ``sorted(..., key=sort_index)`` call as redundant (research.md R1).
        """
        category = service.create_category("Ties")
        for index in range(5):
            item = service.create_item(name=f"Tied {index}")
            # Every placement shares a sort_index — order comes entirely from the tie-break.
            service.place_item_in_category(item.item_id, category.category_id, sort_index=1)
        clear_all_caches()

        links = sorted(
            service.repository.list_item_parent_links(category_ids=[category.category_id]),
            key=lambda link: link.sort_index,
        )
        result = service.list_items(category_id=category.category_id)

        assert [item.item_id for item in result] == [link.item_id for link in links]

    def test_default_sort_index_is_applied(self, service: TaxomeshService) -> None:
        """Feature 034: a placement made without a sort_index still lands deterministically."""
        category = service.create_category("Defaults")
        for index in range(3):
            item = service.create_item(name=f"Default {index}")
            service.place_item_in_category(item.item_id, category.category_id)
        clear_all_caches()

        result = service.list_items(category_id=category.category_id)

        assert len(result) == 3
        links = service.repository.list_item_parent_links(category_ids=[category.category_id])
        assert {link.sort_index for link in links} == {0}


# ---------------------------------------------------------------------------
# US1 — empty results and unknown identifiers
# ---------------------------------------------------------------------------


class TestListItemsEdges:
    def test_category_with_no_placements_returns_empty(self, service: TaxomeshService) -> None:
        """FR-016."""
        category = service.create_category("Barren")
        clear_all_caches()

        assert service.list_items(category_id=category.category_id) == []

    def test_unknown_category_raises(self, service: TaxomeshService) -> None:
        """FR-013: the existence check survives the rewrite."""
        missing = uuid4()
        clear_all_caches()

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.list_items(category_id=missing)


# ---------------------------------------------------------------------------
# US1 — dangling endpoints (FR-012)
# ---------------------------------------------------------------------------


class TestDanglingPlacementEndpoint:
    """Deletion does not cascade on the file backends (finding E2), so a link can
    outlive its endpoint row. FR-012 keeps today's behaviour: that raises."""

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_item_row_raises_with_the_existing_message(self, backend: str, tmp_path: Path) -> None:
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YAMLRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        category = service.create_category("Holder")
        doomed = service.create_item(name="Doomed")
        service.place_item_in_category(doomed.item_id, category.category_id)

        service.delete_item(doomed.item_id)
        clear_all_caches()
        # The placement link survived the item it points at.
        assert [link.item_id for link in repository.list_item_parent_links(category_ids=[category.category_id])] == [
            doomed.item_id
        ]

        with pytest.raises(TaxomeshItemNotFoundError, match=f"Item not found: {doomed.item_id}"):
            service.list_items(category_id=category.category_id)


# ---------------------------------------------------------------------------
# US2 — get_categories_by_ids port conformance (FR-001 … FR-008)
# ---------------------------------------------------------------------------


class TestGetCategoriesByIdsConformance:
    """The new batch primitive must mirror get_items_by_ids clause for clause.

    Run through the parametrised ``service`` fixture, so every assertion is made
    once per backend (FR-008, SC-006).
    """

    def test_returns_the_requested_rows(self, service: TaxomeshService) -> None:
        first = service.create_category("Batch One")
        second = service.create_category("Batch Two")

        result = service.repository.get_categories_by_ids({first.category_id, second.category_id})

        assert set(result) == {first.category_id, second.category_id}
        assert result[first.category_id].name == "Batch One"

    def test_empty_input_returns_empty_mapping(self, service: TaxomeshService) -> None:
        """FR-004."""
        assert service.repository.get_categories_by_ids([]) == {}

    def test_duplicate_ids_collapse(self, service: TaxomeshService) -> None:
        """FR-002: input is pre-normalised, and a mapping cannot hold a key twice."""
        category = service.create_category("Duplicated")

        result = service.repository.get_categories_by_ids([category.category_id, category.category_id])

        assert list(result) == [category.category_id]

    def test_absent_ids_are_silently_missing(self, service: TaxomeshService) -> None:
        """FR-003: a missing row is an absent key, never an exception."""
        assert service.repository.get_categories_by_ids([uuid4(), uuid4()]) == {}

    def test_mixed_present_and_absent(self, service: TaxomeshService) -> None:
        present = service.create_category("Present")
        absent = uuid4()

        result = service.repository.get_categories_by_ids([present.category_id, absent])

        assert set(result) == {present.category_id}

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        """FR-007: three states, defaulting to unfiltered."""
        live = service.create_category("Live")
        dark = service.create_category("Dark")
        dark_row = service.repository.get_category(dark.category_id)
        assert dark_row is not None
        dark_row.enabled = False
        service.repository.save_category(dark_row)
        clear_all_caches()
        both = {live.category_id, dark.category_id}

        assert set(service.repository.get_categories_by_ids(both)) == both
        assert set(service.repository.get_categories_by_ids(both, enabled=True)) == {live.category_id}
        assert set(service.repository.get_categories_by_ids(both, enabled=False)) == {dark.category_id}


# ---------------------------------------------------------------------------
# US2 — list_category_parent_links parent filter (FR-009, FR-010)
# ---------------------------------------------------------------------------


class TestCategoryParentLinkFilter:
    def test_none_applies_no_filter(self, service: TaxomeshService) -> None:
        parent = service.create_category("Parent")
        child = service.create_category("Child")
        service.add_category_parent(child.category_id, parent.category_id)

        all_links = service.repository.list_category_parent_links()

        assert any(link.category_id == child.category_id for link in all_links)

    def test_empty_collection_matches_nothing(self, service: TaxomeshService) -> None:
        """FR-010: an EMPTY collection is 'match nothing', NOT 'no filter'.

        The trap this guards is the falsy check ``if parent_category_ids:``, which
        would silently return every link in the store.
        """
        parent = service.create_category("Parent")
        child = service.create_category("Child")
        service.add_category_parent(child.category_id, parent.category_id)

        assert service.repository.list_category_parent_links(parent_category_ids=[]) == []

    def test_filters_to_the_named_parents(self, service: TaxomeshService) -> None:
        wanted = service.create_category("Wanted")
        other = service.create_category("Other")
        mine = service.create_category("Mine")
        theirs = service.create_category("Theirs")
        service.add_category_parent(mine.category_id, wanted.category_id)
        service.add_category_parent(theirs.category_id, other.category_id)

        links = service.repository.list_category_parent_links(parent_category_ids=[wanted.category_id])

        assert [link.category_id for link in links] == [mine.category_id]

    def test_ordering_contract_holds_under_the_filter(self, service: TaxomeshService) -> None:
        """FR-010: (parent_category_id, sort_index, category_id) survives filtering."""
        parent = service.create_category("Ordered Parent")
        for index in (2, 0, 1):
            child = service.create_category(f"Child {index}")
            service.add_category_parent(child.category_id, parent.category_id, sort_index=index)

        links = service.repository.list_category_parent_links(parent_category_ids=[parent.category_id])

        assert [link.sort_index for link in links] == [0, 1, 2]


# ---------------------------------------------------------------------------
# US2 — list_categories(parent_id=…) behaviour
# ---------------------------------------------------------------------------


class TestListCategoriesByParent:
    def test_ordering_follows_sort_index(self, service: TaxomeshService) -> None:
        parent = service.create_category("Parent")
        for index, name in ((2, "Third"), (0, "First"), (1, "Second")):
            child = service.create_category(name)
            service.add_category_parent(child.category_id, parent.category_id, sort_index=index)
        clear_all_caches()

        result = service.list_categories(parent_id=parent.category_id)

        assert [category.name for category in result] == ["First", "Second", "Third"]

    def test_negative_and_duplicate_sort_index(self, service: TaxomeshService) -> None:
        parent = service.create_category("Parent")
        below = service.create_category("Below")
        service.add_category_parent(below.category_id, parent.category_id, sort_index=-3)
        for index in range(3):
            tied = service.create_category(f"Tied {index}")
            service.add_category_parent(tied.category_id, parent.category_id, sort_index=5)
        clear_all_caches()

        links = sorted(
            service.repository.list_category_parent_links(parent_category_ids=[parent.category_id]),
            key=lambda link: link.sort_index,
        )
        result = service.list_categories(parent_id=parent.category_id)

        assert result[0].name == "Below"
        assert [category.category_id for category in result] == [link.category_id for link in links]

    def test_leaf_returns_empty(self, service: TaxomeshService) -> None:
        leaf = service.create_category("Leaf")
        clear_all_caches()

        assert service.list_categories(parent_id=leaf.category_id) == []

    def test_unknown_parent_raises(self, service: TaxomeshService) -> None:
        missing = uuid4()
        clear_all_caches()

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.list_categories(parent_id=missing)

    def test_root_listing_still_works(self, service: TaxomeshService) -> None:
        """parent_id=None resolves the root, which performs no existence check."""
        created = service.create_category("Top Level")
        clear_all_caches()

        names = {category.name for category in service.list_categories()}

        assert created.name in names

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        parent = service.create_category("Parent")
        live = service.create_category("Live Child")
        dark = service.create_category("Dark Child")
        service.add_category_parent(live.category_id, parent.category_id, sort_index=0)
        service.add_category_parent(dark.category_id, parent.category_id, sort_index=1)
        dark_row = service.repository.get_category(dark.category_id)
        assert dark_row is not None
        dark_row.enabled = False
        service.repository.save_category(dark_row)
        clear_all_caches()

        assert [c.name for c in service.list_categories(parent_id=parent.category_id)] == ["Live Child"]
        assert [c.name for c in service.list_categories(parent_id=parent.category_id, enabled=False)] == ["Dark Child"]
        assert len(service.list_categories(parent_id=parent.category_id, enabled=None)) == 2

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_child_row_raises(self, backend: str, tmp_path: Path) -> None:
        """FR-012 on the children path — the third of the three, and the one the
        first implementation pass left uncovered (service.py:353)."""
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YAMLRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        parent = service.create_category("Parent")
        doomed = service.create_category("Doomed Child")
        service.add_category_parent(doomed.category_id, parent.category_id)

        service.delete_category(doomed.category_id)
        clear_all_caches()
        # The parent link survived the child it points at.
        assert [
            link.category_id
            for link in repository.list_category_parent_links(parent_category_ids=[parent.category_id])
        ] == [doomed.category_id]

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {doomed.category_id}"):
            service.list_categories(parent_id=parent.category_id)

    def test_external_id_branch_filters_by_parent(self, service: TaxomeshService) -> None:
        """The external_id branch runs its own parent scan (research.md R7) — same filter applies."""
        parent = service.create_category("Parent")
        stranger = service.create_category("Stranger")
        child = service.create_category("Child", external_id="ext-child")
        service.add_category_parent(child.category_id, parent.category_id)
        clear_all_caches()

        assert [c.name for c in service.list_categories(external_id="ext-child", parent_id=parent.category_id)] == [
            "Child"
        ]
        assert service.list_categories(external_id="ext-child", parent_id=stranger.category_id) == []


# ---------------------------------------------------------------------------
# US3 — list_categories_by_item(item_id) behaviour
# ---------------------------------------------------------------------------


class TestListCategoriesByItem:
    def test_ordering_is_the_composite_produced_by_the_stable_re_sort(self, service: TaxomeshService) -> None:
        """research.md R1 — the load-bearing test of this feature.

        The links arrive from the port ordered by ``category_id`` (they are
        filtered to a single item), and the service then applies a STABLE re-sort
        by ``sort_index``. Today's observable order is the composite of the two.
        Delete that re-sort as "redundant" and this test fails.

        The data is built so the two orders genuinely disagree — sort_index is
        assigned in reverse category_id order — otherwise the assertion would
        hold either way and prove nothing.
        """
        item = service.create_item(name="Widely Placed")
        categories = [service.create_category(f"Holder {i}") for i in range(5)]
        by_id = sorted(categories, key=lambda category: str(category.category_id))
        for rank, category in enumerate(reversed(by_id)):
            service.place_item_in_category(item.item_id, category.category_id, sort_index=rank)
        clear_all_caches()

        raw_links = service.repository.list_item_parent_links(item_id=item.item_id)
        expected = [link.category_id for link in sorted(raw_links, key=lambda link: link.sort_index)]
        result = service.list_categories_by_item(item.item_id)

        assert [category.category_id for category in result] == expected
        # The two orders must actually differ, or this test is vacuous.
        assert expected != [link.category_id for link in raw_links]

    def test_ties_fall_back_to_the_link_order(self, service: TaxomeshService) -> None:
        item = service.create_item(name="Tied Placements")
        for index in range(4):
            category = service.create_category(f"Tied Holder {index}")
            service.place_item_in_category(item.item_id, category.category_id, sort_index=3)
        clear_all_caches()

        raw_links = service.repository.list_item_parent_links(item_id=item.item_id)
        result = service.list_categories_by_item(item.item_id)

        assert [category.category_id for category in result] == [link.category_id for link in raw_links]

    def test_unplaced_item_returns_empty(self, service: TaxomeshService) -> None:
        item = service.create_item(name="Homeless")
        clear_all_caches()

        assert service.list_categories_by_item(item.item_id) == []

    def test_unknown_item_raises(self, service: TaxomeshService) -> None:
        missing = uuid4()
        clear_all_caches()

        with pytest.raises(TaxomeshItemNotFoundError, match=f"Item not found: {missing}"):
            service.list_categories_by_item(missing)

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        item = service.create_item(name="Mixed Placements")
        live = service.create_category("Live Holder")
        dark = service.create_category("Dark Holder")
        service.place_item_in_category(item.item_id, live.category_id, sort_index=0)
        service.place_item_in_category(item.item_id, dark.category_id, sort_index=1)
        dark_row = service.repository.get_category(dark.category_id)
        assert dark_row is not None
        dark_row.enabled = False
        service.repository.save_category(dark_row)
        clear_all_caches()

        assert [c.name for c in service.list_categories_by_item(item.item_id)] == ["Live Holder"]
        assert [c.name for c in service.list_categories_by_item(item.item_id, enabled=False)] == ["Dark Holder"]
        assert len(service.list_categories_by_item(item.item_id, enabled=None)) == 2

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_category_row_raises(self, backend: str, tmp_path: Path) -> None:
        """FR-012 on the category side: a dangling placement raises, it is not skipped."""
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YAMLRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        item = service.create_item(name="Orphaned")
        doomed = service.create_category("Doomed Holder")
        service.place_item_in_category(item.item_id, doomed.category_id)

        service.delete_category(doomed.category_id)
        clear_all_caches()

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {doomed.category_id}"):
            service.list_categories_by_item(item.item_id)
