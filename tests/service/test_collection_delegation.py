"""Every collection member reaches the right port call, end to end against real storage.

Each operation is exercised through its namespace against a real repository, which catches what
is never wrong in review and occasionally wrong in fact: a swapped argument, a filter dropped, a
keyword that should have been positional.

It runs on the parametrized four-backend ``service`` fixture, so each assertion is made once
per backend.

**The one test here that is not routine** is
``TestItemTagging::test_tag_takes_the_item_first``. ``tag(item_id, tag_id)`` takes two ``UUID``
arguments, so passing them in the wrong order compiles, type-checks and silently links the
wrong pair. It is pinned by the asymmetry in the member's own validation order: the tag is
resolved before the item, so a swapped call raises ``TaxomeshTagNotFoundError`` rather than
doing something plausible and wrong.
"""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.related import RelatedItems
from taxomesh.exceptions import (
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)

RELATION_TYPE = "related_to"


class TestCategoryLookups:
    """``svc.categories`` single-row and bulk lookups."""

    def test_get_by_slug(self, service: TaxomeshService) -> None:
        """``get_by_slug`` finds the category by its unique slug."""
        created = service.categories.create("Alpha", slug="alpha")

        assert service.categories.get_by_slug("alpha") == created

    def test_get_by_slug_returns_none(self, service: TaxomeshService) -> None:
        """An unknown slug answers ``None``, like every other ``get*`` member."""
        assert service.categories.get_by_slug("no-such-slug") is None

    def test_get_by_external_id(self, service: TaxomeshService) -> None:
        """``get_by_external_id`` answers ``None`` for an unknown id and the row for a known one."""
        created = service.categories.create("Alpha", external_id="ext-alpha")

        assert service.categories.get_by_external_id("ext-alpha") == created
        assert service.categories.get_by_external_id("ext-missing") is None

    def test_get_many_honours_the_enabled_filter(self, service: TaxomeshService) -> None:
        """``get_many`` is unfiltered by default and filters when asked."""
        created = service.categories.create("Alpha")
        service.categories.update(created.category_id, enabled=False)

        assert created.category_id in service.categories.get_many([created.category_id])
        assert created.category_id not in service.categories.get_many([created.category_id], enabled=True)

    def test_get_many_by_external_id(self, service: TaxomeshService) -> None:
        """``get_many_by_external_id`` keys the mapping by external id, omitting the absent."""
        created = service.categories.create("Alpha", external_id="ext-alpha")

        found = service.categories.get_many_by_external_id(["ext-alpha", "ext-missing"])

        assert found == {"ext-alpha": created}


class TestCategoryListing:
    """``svc.categories`` listing, roots and search."""

    def test_list_by_parent(self, service: TaxomeshService) -> None:
        """``list(parent=…)`` returns that parent's children."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        assert service.categories.list(parent=parent.category_id) == (child,)

    def test_list_by_item(self, service: TaxomeshService) -> None:
        """``list(item=…)`` returns the categories the item is placed in."""
        category = service.categories.create("Holder")
        item = service.items.create(name="Held")
        service.items.place_in(item.item_id, category.category_id)

        assert service.categories.list(item=item.item_id) == (category,)

    def test_list_rejects_both_filters_at_once(self, service: TaxomeshService) -> None:
        """Passing ``parent`` and ``item`` together raises rather than silently ignoring one.

        The two reach different reads, so honouring both is not possible. Choosing
        one quietly is the failure mode this refuses.
        """
        category = service.categories.create("Holder")
        item = service.items.create(name="Held")

        with pytest.raises(TaxomeshValidationError):
            service.categories.list(parent=category.category_id, item=item.item_id)

    def test_roots_lists_the_categories_with_no_parent(self, service: TaxomeshService) -> None:
        """``roots()`` lists the top level, which a category given a parent leaves.

        ``list()`` with no filter lists every category, the child included.
        """
        top = service.categories.create("Top")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, top.category_id)

        assert [category.category_id for category in service.categories.roots()] == [top.category_id]
        assert {top.category_id, child.category_id} <= {c.category_id for c in service.categories.list()}

    def test_search_ranks_by_name(self, service: TaxomeshService) -> None:
        """``search`` reaches the fuzzy search engine."""
        created = service.categories.create("Alphabet")

        assert created in service.categories.search("alpha")


class TestCategoryWrites:
    """``svc.categories`` create, update, delete and placement."""

    def test_create_carries_every_field(self, service: TaxomeshService) -> None:
        """Each keyword reaches the stored row."""
        created = service.categories.create(
            "Alpha",
            description="desc",
            slug="alpha",
            external_id="ext-alpha",
            metadata={"k": "v"},
        )

        assert (created.name, created.description, created.slug) == ("Alpha", "desc", "alpha")
        assert created.external_id == "ext-alpha"
        assert created.metadata == {"k": "v"}

    def test_update_applies_each_field(self, service: TaxomeshService) -> None:
        """``update`` reaches the service's update path with every keyword."""
        created = service.categories.create("Alpha")

        updated = service.categories.update(
            created.category_id,
            name="Beta",
            description="desc",
            slug="beta",
            metadata={"k": "v"},
            enabled=False,
        )

        assert (updated.name, updated.description, updated.slug) == ("Beta", "desc", "beta")
        assert updated.metadata == {"k": "v"}
        assert updated.enabled is False

    def test_delete_removes_the_row(self, service: TaxomeshService) -> None:
        """``delete`` and ``del`` are the same operation."""
        created = service.categories.create("Alpha")

        service.categories.delete(created.category_id)

        assert created.category_id not in service.categories

    def test_add_and_remove_parent(self, service: TaxomeshService) -> None:
        """``add_parent`` links, ``remove_parent`` unlinks, and ``sort_index`` is carried."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")

        link = service.categories.add_parent(child.category_id, parent.category_id, sort_index=3)

        assert (link.category_id, link.parent_category_id, link.sort_index) == (
            child.category_id,
            parent.category_id,
            3,
        )

        service.categories.remove_parent(child.category_id, parent.category_id)

        assert service.categories.list(parent=parent.category_id) == ()

    def test_move_reparents(self, service: TaxomeshService) -> None:
        """``move`` takes the old and new parent as keywords, in that spelling."""
        old_parent = service.categories.create("Old")
        new_parent = service.categories.create("New")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, old_parent.category_id)

        service.categories.move(
            child.category_id,
            from_parent=old_parent.category_id,
            to_parent=new_parent.category_id,
        )

        assert service.categories.list(parent=old_parent.category_id) == ()
        assert service.categories.list(parent=new_parent.category_id) == (child,)

    def test_reorder_sets_the_listing_order(self, service: TaxomeshService) -> None:
        """``reorder`` decides the order ``list(parent=…)`` returns."""
        parent = service.categories.create("Parent")
        first = service.categories.create("First")
        second = service.categories.create("Second")
        for child in (first, second):
            service.categories.add_parent(child.category_id, parent.category_id)

        service.categories.reorder(parent.category_id, [second.category_id, first.category_id])

        assert service.categories.list(parent=parent.category_id) == (second, first)


class TestItemLookups:
    """``svc.items`` single-row and bulk lookups."""

    def test_get_by_slug(self, service: TaxomeshService) -> None:
        """``get_by_slug`` finds the item by its unique slug."""
        created = service.items.create(name="Alpha", slug="alpha")

        assert service.items.get_by_slug("alpha") == created

    def test_get_by_slug_returns_none(self, service: TaxomeshService) -> None:
        """An unknown slug answers ``None``, like every other ``get*`` member."""
        assert service.items.get_by_slug("no-such-slug") is None

    def test_get_by_external_id(self, service: TaxomeshService) -> None:
        """``get_by_external_id`` answers ``None`` for an unknown id and the row for a known one."""
        created = service.items.create(name="Alpha", external_id="ext-alpha")

        assert service.items.get_by_external_id("ext-alpha") == created
        assert service.items.get_by_external_id("ext-missing") is None

    def test_get_many_honours_the_enabled_filter(self, service: TaxomeshService) -> None:
        """``get_many`` is unfiltered by default and filters when asked."""
        created = service.items.create(name="Alpha")
        service.items.update(created.item_id, enabled=False)

        assert created.item_id in service.items.get_many([created.item_id])
        assert created.item_id not in service.items.get_many([created.item_id], enabled=True)

    def test_get_many_by_external_id(self, service: TaxomeshService) -> None:
        """``get_many_by_external_id`` keys the mapping by external id, omitting the absent."""
        created = service.items.create(name="Alpha", external_id="ext-alpha")

        found = service.items.get_many_by_external_id(["ext-alpha", "ext-missing"])

        assert found == {"ext-alpha": created}


class TestItemListing:
    """``svc.items`` listing and search."""

    def test_list_by_category(self, service: TaxomeshService) -> None:
        """``list(category=…)`` returns the items placed in that category."""
        category = service.categories.create("Holder")
        item = service.items.create("Held")
        service.items.place_in(item.item_id, category.category_id)

        assert service.items.list(category=category.category_id) == (item,)

    def test_list_defaults_to_enabled_only(self, service: TaxomeshService) -> None:
        """A disabled item is absent from ``list()`` and present when the filter is lifted.

        Asserted on **identifiers**, not whole rows. ``created`` is the row from before the
        update, and the update stores a new row of the same item, with another ``enabled`` and
        ``version``, so ``created`` equals no stored row on any backend. The identifier is what
        this test is about.
        """
        created = service.items.create("Alpha")
        service.items.update(created.item_id, enabled=False)

        assert created.item_id not in [item.item_id for item in service.items.list()]
        assert created.item_id in [item.item_id for item in service.items.list(enabled=None)]

    def test_search_ranks_by_name(self, service: TaxomeshService) -> None:
        """``search`` reaches the fuzzy search engine."""
        created = service.items.create("Alphabet")

        assert created in service.items.search("alpha")


class TestItemWrites:
    """``svc.items`` create, update, delete and placement."""

    def test_create_carries_every_field(self, service: TaxomeshService) -> None:
        """Each keyword reaches the stored row."""
        created = service.items.create("Alpha", external_id="ext-alpha", slug="alpha", metadata={"k": "v"})

        assert (created.name, created.slug, created.external_id) == ("Alpha", "alpha", "ext-alpha")
        assert created.metadata == {"k": "v"}

    def test_update_applies_each_field(self, service: TaxomeshService) -> None:
        """``update`` reaches the service's update path with every keyword."""
        created = service.items.create("Alpha")

        updated = service.items.update(created.item_id, name="Beta", slug="beta", metadata={"k": "v"}, enabled=False)

        assert (updated.name, updated.slug) == ("Beta", "beta")
        assert updated.metadata == {"k": "v"}
        assert updated.enabled is False

    def test_place_in_and_remove_from(self, service: TaxomeshService) -> None:
        """``place_in`` links the item to a category and ``remove_from`` unlinks it."""
        category = service.categories.create("Holder")
        item = service.items.create("Held")

        link = service.items.place_in(item.item_id, category.category_id, sort_index=2)

        assert (link.item_id, link.category_id, link.sort_index) == (item.item_id, category.category_id, 2)

        service.items.remove_from(item.item_id, category.category_id)

        assert service.items.list(category=category.category_id) == ()

    def test_move_between_categories(self, service: TaxomeshService) -> None:
        """``move`` takes the old and new category as keywords, in that spelling."""
        old_category = service.categories.create("Old")
        new_category = service.categories.create("New")
        item = service.items.create("Held")
        service.items.place_in(item.item_id, old_category.category_id)

        link = service.items.move(
            item.item_id,
            from_category=old_category.category_id,
            to_category=new_category.category_id,
        )

        assert link.category_id == new_category.category_id
        assert service.items.list(category=old_category.category_id) == ()
        assert service.items.list(category=new_category.category_id) == (item,)

    def test_reorder_sets_the_listing_order(self, service: TaxomeshService) -> None:
        """``reorder`` decides the order ``list(category=…)`` returns."""
        category = service.categories.create("Holder")
        first = service.items.create("First")
        second = service.items.create("Second")
        for item in (first, second):
            service.items.place_in(item.item_id, category.category_id)

        service.items.reorder(category.category_id, [second.item_id, first.item_id])

        assert service.items.list(category=category.category_id) == (second, first)


class TestItemTagging:
    """``svc.items.tag`` / ``untag`` — the argument order that reverses."""

    def test_tag_takes_the_item_first(self, service: TaxomeshService) -> None:
        """``tag(item_id, tag_id)`` succeeds; the reversed call is rejected.

        ``items.tag`` validates the tag before the item, so passing an item id where a tag id
        belongs raises ``TaxomeshTagNotFoundError``. That asymmetry is what makes the argument
        order testable at all — both parameters are ``UUID``, so nothing else would notice.
        """
        item = service.items.create("Held")
        tag = service.tags.create("Blue")

        service.items.tag(item.item_id, tag.tag_id)

        with pytest.raises(TaxomeshTagNotFoundError):
            service.items.tag(tag.tag_id, item.item_id)

    def test_untag_takes_the_item_first(self, service: TaxomeshService) -> None:
        """``untag(item_id, tag_id)`` succeeds; the reversed call is rejected."""
        item = service.items.create("Held")
        tag = service.tags.create("Blue")
        service.items.tag(item.item_id, tag.tag_id)

        service.items.untag(item.item_id, tag.tag_id)

        with pytest.raises(TaxomeshTagNotFoundError):
            service.items.untag(tag.tag_id, item.item_id)

    def test_tagging_an_unknown_item_raises(self, service: TaxomeshService) -> None:
        """A stored tag and an item that is not stored raise the item's error, not the tag's."""
        tag = service.tags.create("Blue")

        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.tag(uuid4(), tag.tag_id)


class TestItemRelations:
    """``svc.items`` relation members."""

    def test_relate_and_unrelate(self, service: TaxomeshService) -> None:
        """``relate`` creates the directed link and ``unrelate`` removes it."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")

        link = service.items.relate(item_a.item_id, item_b.item_id, RELATION_TYPE, sort_index=1, metadata={"k": "v"})

        assert (link.source_item_id, link.target_item_id, link.relation_type) == (
            item_a.item_id,
            item_b.item_id,
            RELATION_TYPE,
        )
        assert (link.sort_index, link.metadata) == (1, {"k": "v"})

        service.items.unrelate(item_a.item_id, item_b.item_id, RELATION_TYPE)

        assert service.items.list_relations(item_a.item_id) == ()

    def test_list_relations_and_related(self, service: TaxomeshService) -> None:
        """``list_relations`` returns links; ``list_related`` returns the items behind them."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        service.items.relate(item_a.item_id, item_b.item_id, RELATION_TYPE)

        links = service.items.list_relations(item_a.item_id, relation_types=[RELATION_TYPE])

        assert [link.target_item_id for link in links] == [item_b.item_id]
        assert service.items.list_related(item_a.item_id, relation_types=[RELATION_TYPE]) == (item_b,)

    def test_list_relations_honours_direction(self, service: TaxomeshService) -> None:
        """``direction`` reaches the service unchanged."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        service.items.relate(item_a.item_id, item_b.item_id, RELATION_TYPE)

        assert service.items.list_related(item_b.item_id) == ()
        assert service.items.list_related(item_b.item_id, direction="incoming") == (item_a,)

    def test_get_many_related_groups_by_source(self, service: TaxomeshService) -> None:
        """``get_many_related`` maps each source id to a ``RelatedItems`` view of its related items."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        service.items.relate(item_a.item_id, item_b.item_id, RELATION_TYPE)

        found = service.items.get_many_related([item_a.item_id])

        assert found == {item_a.item_id: RelatedItems(item_id=item_a.item_id, by_type={RELATION_TYPE: (item_b,)})}


class TestTagCollection:
    """``svc.tags``: a container of tags, subscript included."""

    def test_subscript_reaches_the_ports_find_tag(self, service: TaxomeshService) -> None:
        """``svc.tags[tag_id]`` answers the stored tag, read through the port's ``find_tag``."""
        created = service.tags.create("Blue")

        assert service.tags[created.tag_id] == created

    def test_list_returns_every_tag(self, service: TaxomeshService) -> None:
        """``list()`` takes no filter and returns all stored tags."""
        created = service.tags.create("Blue")

        assert service.tags.list() == (created,)

    def test_create_carries_metadata(self, service: TaxomeshService) -> None:
        """``create`` writes metadata, as the service has always allowed."""
        created = service.tags.create("Blue", metadata={"k": "v"})

        assert (created.name, created.metadata) == ("Blue", {"k": "v"})

    def test_update_renames(self, service: TaxomeshService) -> None:
        """``update`` reaches the service's tag update path."""
        created = service.tags.create("Blue")

        updated = service.tags.update(created.tag_id, name="Green")

        assert updated.name == "Green"

    def test_delete_removes_the_row(self, service: TaxomeshService) -> None:
        """``delete`` and ``del`` are the same operation."""
        created = service.tags.create("Blue")

        service.tags.delete(created.tag_id)

        assert service.tags.list() == ()
