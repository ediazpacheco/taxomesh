"""Behaviour tests for the batched placement read paths.

Resolving placements in one batch rather than one row at a time must be invisible
to callers. These tests pin that behaviour: ordering (including the tie-breaks that
exist because of a stable re-sort), the empty and not-found paths, and the policy
for a link whose endpoint row is gone.

They run through the parametrised ``service`` fixture, so every assertion here
is made four times — once per backend.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import CategoryParentLink, ItemParentLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError

# ---------------------------------------------------------------------------
# items.list(category=…) ordering
# ---------------------------------------------------------------------------


class TestItemsListOrdering:
    """A category's items come back in placement order: by sort index, ties by link order."""

    def test_ascending_sort_index(self, service: TaxomeshService) -> None:
        category = service.categories.create("Ordered")
        first = service.items.create(name="First")
        second = service.items.create(name="Second")
        third = service.items.create(name="Third")
        # Placed out of order on purpose — sort_index decides, not insertion.
        service.items.place_in(third.item_id, category.category_id, sort_index=2)
        service.items.place_in(first.item_id, category.category_id, sort_index=0)
        service.items.place_in(second.item_id, category.category_id, sort_index=1)
        service._cache.clear()

        result = service.items.list(category=category.category_id)

        assert [item.name for item in result] == ["First", "Second", "Third"]

    def test_negative_sort_index_sorts_before_zero(self, service: TaxomeshService) -> None:
        category = service.categories.create("Negatives")
        below = service.items.create(name="Below")
        zero = service.items.create(name="Zero")
        above = service.items.create(name="Above")
        service.items.place_in(zero.item_id, category.category_id, sort_index=0)
        service.items.place_in(above.item_id, category.category_id, sort_index=7)
        service.items.place_in(below.item_id, category.category_id, sort_index=-5)
        service._cache.clear()

        result = service.items.list(category=category.category_id)

        assert [item.name for item in result] == ["Below", "Zero", "Above"]

    def test_duplicate_sort_index_order_matches_the_link_order(self, service: TaxomeshService) -> None:
        """Ties resolve by the repository's link ordering, preserved by a STABLE re-sort.

        Asserting the tie-break this way rather than hard-coding one keeps the test
        honest across backends, and it is what fails if someone deletes the
        ``sorted(..., key=sort_index)`` call as redundant.
        """
        category = service.categories.create("Ties")
        for index in range(5):
            item = service.items.create(name=f"Tied {index}")
            # Every placement shares a sort_index — order comes entirely from the tie-break.
            service.items.place_in(item.item_id, category.category_id, sort_index=1)
        service._cache.clear()

        links = sorted(
            service.repository.list_item_parent_links(category_ids=[category.category_id]),
            key=lambda link: link.sort_index,
        )
        result = service.items.list(category=category.category_id)

        assert [item.item_id for item in result] == [link.item_id for link in links]

    def test_default_sort_index_is_applied(self, service: TaxomeshService) -> None:
        """Feature 034: a placement made without a sort_index still lands deterministically."""
        category = service.categories.create("Defaults")
        for index in range(3):
            item = service.items.create(name=f"Default {index}")
            service.items.place_in(item.item_id, category.category_id)
        service._cache.clear()

        result = service.items.list(category=category.category_id)

        assert len(result) == 3
        links = service.repository.list_item_parent_links(category_ids=[category.category_id])
        assert {link.sort_index for link in links} == {0}


# ---------------------------------------------------------------------------
# Empty results and unknown identifiers
# ---------------------------------------------------------------------------


class TestItemsListEdges:
    def test_category_with_no_placements_returns_empty(self, service: TaxomeshService) -> None:
        """A category holding no item lists none."""
        category = service.categories.create("Barren")
        service._cache.clear()

        assert service.items.list(category=category.category_id) == ()

    def test_unknown_category_raises(self, service: TaxomeshService) -> None:
        """A category that is not stored raises its not-found error."""
        missing = uuid4()
        service._cache.clear()

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.items.list(category=missing)


# ---------------------------------------------------------------------------
# Dangling endpoints
# ---------------------------------------------------------------------------


class TestDanglingPlacementEndpoint:
    """A placement naming an item that is not stored raises when a listing meets it.

    Deletes take their links with them, so such a link comes only from a write straight through
    the port, which the file backends store without checking its ends.
    """

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_item_row_raises_with_the_existing_message(self, backend: str, tmp_path: Path) -> None:
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YamlRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        category = service.categories.create("Holder")
        missing = uuid4()
        repository.save_item_parent_link(ItemParentLink(item_id=missing, category_id=category.category_id))

        with pytest.raises(TaxomeshItemNotFoundError, match=f"Item not found: {missing}"):
            service.items.list(category=category.category_id)


# ---------------------------------------------------------------------------
# map_categories_by_id port conformance
# ---------------------------------------------------------------------------


class TestMapCategoriesByIdConformance:
    """The new batch primitive must mirror map_items_by_id clause for clause.

    Run through the parametrised ``service`` fixture, so every assertion is made
    once per backend.
    """

    def test_returns_the_requested_rows(self, service: TaxomeshService) -> None:
        first = service.categories.create("Batch One")
        second = service.categories.create("Batch Two")

        result = service.repository.map_categories_by_id({first.category_id, second.category_id})

        assert set(result) == {first.category_id, second.category_id}
        assert result[first.category_id].name == "Batch One"

    def test_empty_input_returns_empty_mapping(self, service: TaxomeshService) -> None:
        """No identifier gives an empty mapping."""
        assert service.repository.map_categories_by_id([]) == {}

    def test_duplicate_ids_collapse(self, service: TaxomeshService) -> None:
        """Input is pre-normalised, and a mapping cannot hold a key twice."""
        category = service.categories.create("Duplicated")

        result = service.repository.map_categories_by_id([category.category_id, category.category_id])

        assert list(result) == [category.category_id]

    def test_absent_ids_are_silently_missing(self, service: TaxomeshService) -> None:
        """An identifier that names no stored row is an absent key, never an exception."""
        assert service.repository.map_categories_by_id([uuid4(), uuid4()]) == {}

    def test_mixed_present_and_absent(self, service: TaxomeshService) -> None:
        present = service.categories.create("Present")
        absent = uuid4()

        result = service.repository.map_categories_by_id([present.category_id, absent])

        assert set(result) == {present.category_id}

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        """Three states, defaulting to unfiltered."""
        live = service.categories.create("Live")
        dark = service.categories.create("Dark")
        dark_row = service.repository.find_category(dark.category_id)
        assert dark_row is not None
        service.repository.save_category(dark_row.model_copy(update={"enabled": False}))
        service._cache.clear()
        both = {live.category_id, dark.category_id}

        assert set(service.repository.map_categories_by_id(both)) == both
        assert set(service.repository.map_categories_by_id(both, enabled=True)) == {live.category_id}
        assert set(service.repository.map_categories_by_id(both, enabled=False)) == {dark.category_id}


# ---------------------------------------------------------------------------
# list_category_parent_links parent filter
# ---------------------------------------------------------------------------


class TestCategoryParentLinkFilter:
    def test_none_applies_no_filter(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        all_links = service.repository.list_category_parent_links()

        assert any(link.category_id == child.category_id for link in all_links)

    def test_empty_collection_matches_nothing(self, service: TaxomeshService) -> None:
        """An EMPTY collection is 'match nothing', NOT 'no filter'.

        The trap this guards is the falsy check ``if parent_category_ids:``, which
        would silently return every link in the store.
        """
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        assert service.repository.list_category_parent_links(parent_category_ids=[]) == []

    def test_filters_to_the_named_parents(self, service: TaxomeshService) -> None:
        wanted = service.categories.create("Wanted")
        other = service.categories.create("Other")
        mine = service.categories.create("Mine")
        theirs = service.categories.create("Theirs")
        service.categories.add_parent(mine.category_id, wanted.category_id)
        service.categories.add_parent(theirs.category_id, other.category_id)

        links = service.repository.list_category_parent_links(parent_category_ids=[wanted.category_id])

        assert [link.category_id for link in links] == [mine.category_id]

    def test_ordering_contract_holds_under_the_filter(self, service: TaxomeshService) -> None:
        """(parent_category_id, sort_index, category_id) survives filtering."""
        parent = service.categories.create("Ordered Parent")
        for index in (2, 0, 1):
            child = service.categories.create(f"Child {index}")
            service.categories.add_parent(child.category_id, parent.category_id, sort_index=index)

        links = service.repository.list_category_parent_links(parent_category_ids=[parent.category_id])

        assert [link.sort_index for link in links] == [0, 1, 2]


# ---------------------------------------------------------------------------
# categories.list(parent=…) behaviour
# ---------------------------------------------------------------------------


class TestCategoriesListByParent:
    def test_ordering_follows_sort_index(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        for index, name in ((2, "Third"), (0, "First"), (1, "Second")):
            child = service.categories.create(name)
            service.categories.add_parent(child.category_id, parent.category_id, sort_index=index)
        service._cache.clear()

        result = service.categories.list(parent=parent.category_id)

        assert [category.name for category in result] == ["First", "Second", "Third"]

    def test_negative_and_duplicate_sort_index(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        below = service.categories.create("Below")
        service.categories.add_parent(below.category_id, parent.category_id, sort_index=-3)
        for index in range(3):
            tied = service.categories.create(f"Tied {index}")
            service.categories.add_parent(tied.category_id, parent.category_id, sort_index=5)
        service._cache.clear()

        links = sorted(
            service.repository.list_category_parent_links(parent_category_ids=[parent.category_id]),
            key=lambda link: link.sort_index,
        )
        result = service.categories.list(parent=parent.category_id)

        assert result[0].name == "Below"
        assert [category.category_id for category in result] == [link.category_id for link in links]

    def test_leaf_returns_empty(self, service: TaxomeshService) -> None:
        leaf = service.categories.create("Leaf")
        service._cache.clear()

        assert service.categories.list(parent=leaf.category_id) == ()

    def test_unknown_parent_raises(self, service: TaxomeshService) -> None:
        missing = uuid4()
        service._cache.clear()

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.categories.list(parent=missing)

    def test_root_listing_still_works(self, service: TaxomeshService) -> None:
        """parent_id=None resolves the root, which performs no existence check."""
        created = service.categories.create("Top Level")
        service._cache.clear()

        names = {category.name for category in service.categories.roots()}

        assert created.name in names

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        live = service.categories.create("Live Child")
        dark = service.categories.create("Dark Child")
        service.categories.add_parent(live.category_id, parent.category_id, sort_index=0)
        service.categories.add_parent(dark.category_id, parent.category_id, sort_index=1)
        dark_row = service.repository.find_category(dark.category_id)
        assert dark_row is not None
        service.repository.save_category(dark_row.model_copy(update={"enabled": False}))
        service._cache.clear()

        assert [c.name for c in service.categories.list(parent=parent.category_id)] == ["Live Child"]
        assert [c.name for c in service.categories.list(parent=parent.category_id, enabled=False)] == ["Dark Child"]
        assert len(service.categories.list(parent=parent.category_id, enabled=None)) == 2

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_child_row_raises(self, backend: str, tmp_path: Path) -> None:
        """The children path raises for a parent link naming a child that is not stored."""
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YamlRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        parent = service.categories.create("Parent")
        missing = uuid4()
        repository.save_category_parent_link(
            CategoryParentLink(category_id=missing, parent_category_id=parent.category_id)
        )

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.categories.list(parent=parent.category_id)

    def test_external_id_branch_filters_by_parent(self, service: TaxomeshService) -> None:
        """The dropped parent + external_id intersection, composed from the lookup and the listing."""
        parent = service.categories.create("Parent")
        stranger = service.categories.create("Stranger")
        child = service.categories.create("Child", external_id="ext-child")
        service.categories.add_parent(child.category_id, parent.category_id)
        service._cache.clear()

        found = service.categories.get_by_external_id("ext-child")
        assert found is not None
        assert found.name == "Child"
        parents_children = {c.category_id for c in service.categories.list(parent=parent.category_id)}
        strangers_children = {c.category_id for c in service.categories.list(parent=stranger.category_id)}
        assert found.category_id in parents_children
        assert found.category_id not in strangers_children


# ---------------------------------------------------------------------------
# categories.list(item=…) behaviour
# ---------------------------------------------------------------------------


class TestCategoriesListItemIdFilter:
    def test_ordering_is_the_composite_produced_by_the_stable_re_sort(self, service: TaxomeshService) -> None:
        """The categories holding an item come in the order a stable re-sort gives.

        The links arrive from the port ordered by ``category_id`` (they are
        filtered to a single item), and the service then applies a STABLE re-sort
        by ``sort_index``. The observable order is the composite of the two.
        Delete that re-sort as "redundant" and this test fails.

        The data is built so the two orders genuinely disagree — sort_index is
        assigned in reverse category_id order — otherwise the assertion would
        hold either way and prove nothing.
        """
        item = service.items.create(name="Widely Placed")
        categories = [service.categories.create(f"Holder {i}") for i in range(5)]
        by_id = sorted(categories, key=lambda category: str(category.category_id))
        for rank, category in enumerate(reversed(by_id)):
            service.items.place_in(item.item_id, category.category_id, sort_index=rank)
        service._cache.clear()

        raw_links = service.repository.list_item_parent_links(item_ids=[item.item_id])
        expected = [link.category_id for link in sorted(raw_links, key=lambda link: link.sort_index)]
        result = service.categories.list(item=item.item_id)

        assert [category.category_id for category in result] == expected
        # The two orders must actually differ, or this test is vacuous.
        assert expected != [link.category_id for link in raw_links]

    def test_ties_fall_back_to_the_link_order(self, service: TaxomeshService) -> None:
        item = service.items.create(name="Tied Placements")
        for index in range(4):
            category = service.categories.create(f"Tied Holder {index}")
            service.items.place_in(item.item_id, category.category_id, sort_index=3)
        service._cache.clear()

        raw_links = service.repository.list_item_parent_links(item_ids=[item.item_id])
        result = service.categories.list(item=item.item_id)

        assert [category.category_id for category in result] == [link.category_id for link in raw_links]

    def test_unplaced_item_returns_empty(self, service: TaxomeshService) -> None:
        item = service.items.create(name="Homeless")
        service._cache.clear()

        assert service.categories.list(item=item.item_id) == ()

    def test_unknown_item_raises(self, service: TaxomeshService) -> None:
        missing = uuid4()
        service._cache.clear()

        with pytest.raises(TaxomeshItemNotFoundError, match=f"Item not found: {missing}"):
            service.categories.list(item=missing)

    def test_enabled_filtering(self, service: TaxomeshService) -> None:
        item = service.items.create(name="Mixed Placements")
        live = service.categories.create("Live Holder")
        dark = service.categories.create("Dark Holder")
        service.items.place_in(item.item_id, live.category_id, sort_index=0)
        service.items.place_in(item.item_id, dark.category_id, sort_index=1)
        dark_row = service.repository.find_category(dark.category_id)
        assert dark_row is not None
        service.repository.save_category(dark_row.model_copy(update={"enabled": False}))
        service._cache.clear()

        assert [c.name for c in service.categories.list(item=item.item_id)] == ["Live Holder"]
        assert [c.name for c in service.categories.list(item=item.item_id, enabled=False)] == ["Dark Holder"]
        assert len(service.categories.list(item=item.item_id, enabled=None)) == 2

    @pytest.mark.parametrize("backend", ["json", "yaml"])
    def test_missing_category_row_raises(self, backend: str, tmp_path: Path) -> None:
        """A placement naming a category that is not stored raises; it is not skipped."""
        repository = (
            JsonRepository(tmp_path / "dangling.json")
            if backend == "json"
            else YamlRepository(tmp_path / "dangling.yaml")
        )
        service = TaxomeshService(repository=repository)
        item = service.items.create(name="Orphaned")
        missing = uuid4()
        repository.save_item_parent_link(ItemParentLink(item_id=item.item_id, category_id=missing))

        with pytest.raises(TaxomeshCategoryNotFoundError, match=f"Category not found: {missing}"):
            service.categories.list(item=item.item_id)
