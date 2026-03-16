"""Tests for taxomesh.contrib.api.handlers — delegation to TaxomeshService."""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.schemas import (
    AddParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceInCategoryRequest,
    SearchCategoriesRequest,
    SearchItemsRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
)

# ---------------------------------------------------------------------------
# Category handlers
# ---------------------------------------------------------------------------


class TestListCategories:
    """Tests for handlers.list_categories."""

    def test_returns_list(self, service: TaxomeshService) -> None:
        """Returns a list (empty initially at top level)."""
        result = handlers.list_categories(service)
        assert isinstance(result, list)

    def test_includes_created_category(self, service: TaxomeshService) -> None:
        """A created category appears in the listing."""
        service.create_category(name="Fiction")
        result = handlers.list_categories(service)
        assert any(c.name == "Fiction" for c in result)


class TestGetCategory:
    """Tests for handlers.get_category."""

    def test_returns_category(self, service: TaxomeshService) -> None:
        """Returns the matching Category by id."""
        cat = service.create_category(name="Science")
        result = handlers.get_category(service, cat.category_id)
        assert isinstance(result, Category)
        assert result.category_id == cat.category_id

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshCategoryNotFoundError."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.get_category(service, uuid4())


class TestGetCategoryBySlug:
    """Tests for handlers.get_category_by_slug."""

    def test_returns_category(self, service: TaxomeshService) -> None:
        """Returns the matching Category by slug."""
        service.create_category(name="History", slug="history")
        result = handlers.get_category_by_slug(service, "history")
        assert result.slug == "history"

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent slug raises TaxomeshCategoryNotFoundError."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.get_category_by_slug(service, "no-such-slug")


class TestCreateCategory:
    """Tests for handlers.create_category."""

    def test_creates_and_returns_category(self, service: TaxomeshService) -> None:
        """Returns a Category with the provided fields."""
        body = CreateCategoryRequest(name="Travel", description="Trip stuff", slug="travel")
        result = handlers.create_category(service, body)
        assert isinstance(result, Category)
        assert result.name == "Travel"
        assert result.description == "Trip stuff"
        assert result.slug == "travel"

    def test_category_persisted(self, service: TaxomeshService) -> None:
        """The created category can be retrieved by id afterwards."""
        body = CreateCategoryRequest(name="Art")
        result = handlers.create_category(service, body)
        fetched = service.get_category(result.category_id)
        assert fetched.name == "Art"


class TestUpdateCategory:
    """Tests for handlers.update_category."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        cat = service.create_category(name="Old")
        body = UpdateCategoryRequest(name="New")
        result = handlers.update_category(service, cat.category_id, body)
        assert result.name == "New"

    def test_none_fields_unchanged(self, service: TaxomeshService) -> None:
        """Fields left as None are not modified."""
        cat = service.create_category(name="Keep", description="desc")
        body = UpdateCategoryRequest()
        result = handlers.update_category(service, cat.category_id, body)
        assert result.name == "Keep"
        assert result.description == "desc"


class TestDeleteCategory:
    """Tests for handlers.delete_category."""

    def test_deletes_category(self, service: TaxomeshService) -> None:
        """Category is removed after deletion."""
        cat = service.create_category(name="Temp")
        handlers.delete_category(service, cat.category_id)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.get_category(cat.category_id)

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshCategoryNotFoundError."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.delete_category(service, uuid4())


# ---------------------------------------------------------------------------
# Item handlers
# ---------------------------------------------------------------------------


class TestListItems:
    """Tests for handlers.list_items."""

    def test_returns_list(self, service: TaxomeshService) -> None:
        """Returns a list (empty initially)."""
        result = handlers.list_items(service)
        assert isinstance(result, list)

    def test_includes_created_item(self, service: TaxomeshService) -> None:
        """A created item appears in the listing."""
        service.create_item(name="Widget")
        result = handlers.list_items(service)
        assert any(i.name == "Widget" for i in result)


class TestGetItem:
    """Tests for handlers.get_item."""

    def test_returns_item(self, service: TaxomeshService) -> None:
        """Returns the matching Item by id."""
        item = service.create_item(name="Gadget")
        result = handlers.get_item(service, item.item_id)
        assert isinstance(result, Item)
        assert result.item_id == item.item_id

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshItemNotFoundError."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.get_item(service, uuid4())


class TestGetItemBySlug:
    """Tests for handlers.get_item_by_slug."""

    def test_returns_item(self, service: TaxomeshService) -> None:
        """Returns the matching Item by slug."""
        service.create_item(name="Gadget", slug="gadget")
        result = handlers.get_item_by_slug(service, "gadget")
        assert result.slug == "gadget"

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent slug raises TaxomeshItemNotFoundError."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.get_item_by_slug(service, "no-such-slug")


class TestGetItemsByExternalId:
    """Tests for handlers.get_items_by_external_id."""

    def test_returns_matching_items(self, service: TaxomeshService) -> None:
        """Returns all items with the given external_id."""
        service.create_item(name="X", external_id="ext-99")
        result = handlers.get_items_by_external_id(service, "ext-99")
        assert len(result) == 1
        assert result[0].external_id == "ext-99"

    def test_returns_empty_for_unknown(self, service: TaxomeshService) -> None:
        """Returns an empty list when no item matches."""
        result = handlers.get_items_by_external_id(service, "ghost")
        assert result == []


class TestCreateItem:
    """Tests for handlers.create_item."""

    def test_creates_and_returns_item(self, service: TaxomeshService) -> None:
        """Returns an Item with the provided fields."""
        body = CreateItemRequest(name="Widget", external_id="w1", slug="widget")
        result = handlers.create_item(service, body)
        assert isinstance(result, Item)
        assert result.name == "Widget"
        assert result.external_id == "w1"

    def test_item_persisted(self, service: TaxomeshService) -> None:
        """The created item can be retrieved by id afterwards."""
        body = CreateItemRequest(name="Gadget")
        result = handlers.create_item(service, body)
        fetched = service.get_item(result.item_id)
        assert fetched.name == "Gadget"


class TestUpdateItem:
    """Tests for handlers.update_item."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        item = service.create_item(name="Old Item")
        body = UpdateItemRequest(name="New Item")
        result = handlers.update_item(service, item.item_id, body)
        assert result.name == "New Item"

    def test_updates_enabled(self, service: TaxomeshService) -> None:
        """enabled field is updated when provided."""
        item = service.create_item(name="Active")
        body = UpdateItemRequest(enabled=False)
        result = handlers.update_item(service, item.item_id, body)
        assert result.enabled is False

    def test_updates_external_id(self, service: TaxomeshService) -> None:
        """external_id field is updated when provided."""
        item = service.create_item(name="Item")
        body = UpdateItemRequest(external_id="ext-42")
        result = handlers.update_item(service, item.item_id, body)
        assert result.external_id == "ext-42"


class TestDeleteItem:
    """Tests for handlers.delete_item."""

    def test_deletes_item(self, service: TaxomeshService) -> None:
        """Item is removed after deletion."""
        item = service.create_item(name="Gone")
        handlers.delete_item(service, item.item_id)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item(item.item_id)

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshItemNotFoundError."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.delete_item(service, uuid4())


# ---------------------------------------------------------------------------
# Tag handlers
# ---------------------------------------------------------------------------


class TestListTags:
    """Tests for handlers.list_tags."""

    def test_returns_list(self, service: TaxomeshService) -> None:
        """Returns a list (empty initially)."""
        result = handlers.list_tags(service)
        assert isinstance(result, list)

    def test_includes_created_tag(self, service: TaxomeshService) -> None:
        """A created tag appears in the listing."""
        service.create_tag(name="sci-fi")
        result = handlers.list_tags(service)
        assert any(t.name == "sci-fi" for t in result)


class TestCreateTag:
    """Tests for handlers.create_tag."""

    def test_creates_and_returns_tag(self, service: TaxomeshService) -> None:
        """Returns a Tag with the provided fields."""
        body = CreateTagRequest(name="fantasy")
        result = handlers.create_tag(service, body)
        assert isinstance(result, Tag)
        assert result.name == "fantasy"


class TestUpdateTag:
    """Tests for handlers.update_tag."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        tag = service.create_tag(name="old-tag")
        body = UpdateTagRequest(name="new-tag")
        result = handlers.update_tag(service, tag.tag_id, body)
        assert result.name == "new-tag"

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshTagNotFoundError."""
        with pytest.raises(TaxomeshTagNotFoundError):
            handlers.update_tag(service, uuid4(), UpdateTagRequest(name="x"))


class TestDeleteTag:
    """Tests for handlers.delete_tag."""

    def test_deletes_tag(self, service: TaxomeshService) -> None:
        """Tag is removed after deletion; list_tags no longer includes it."""
        tag = service.create_tag(name="temp-tag")
        handlers.delete_tag(service, tag.tag_id)
        remaining = service.list_tags()
        assert all(t.tag_id != tag.tag_id for t in remaining)

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshTagNotFoundError."""
        with pytest.raises(TaxomeshTagNotFoundError):
            handlers.delete_tag(service, uuid4())


# ---------------------------------------------------------------------------
# Relationship handlers
# ---------------------------------------------------------------------------


class TestAddCategoryParent:
    """Tests for handlers.add_category_parent."""

    def test_returns_link(self, service: TaxomeshService) -> None:
        """Returns a CategoryParentLink for the new relationship."""
        parent = service.create_category(name="Parent")
        child = service.create_category(name="Child")
        body = AddParentRequest(parent_id=parent.category_id, sort_index=1)
        result = handlers.add_category_parent(service, child.category_id, body)
        assert isinstance(result, CategoryParentLink)
        assert result.parent_category_id == parent.category_id
        assert result.sort_index == 1


class TestRemoveCategoryParent:
    """Tests for handlers.remove_category_parent."""

    def test_removes_parent(self, service: TaxomeshService) -> None:
        """Parent relationship is removed without error."""
        parent = service.create_category(name="P")
        child = service.create_category(name="C")
        service.add_category_parent(child.category_id, parent.category_id)
        handlers.remove_category_parent(service, child.category_id, parent.category_id)
        # No exception means success; we simply verify it doesn't raise.


class TestPlaceItemInCategory:
    """Tests for handlers.place_item_in_category."""

    def test_returns_link(self, service: TaxomeshService) -> None:
        """Returns an ItemParentLink for the placement."""
        cat = service.create_category(name="Shelf")
        item = service.create_item(name="Book")
        body = PlaceInCategoryRequest(category_id=cat.category_id, sort_index=2)
        result = handlers.place_item_in_category(service, item.item_id, body)
        assert isinstance(result, ItemParentLink)
        assert result.category_id == cat.category_id
        assert result.sort_index == 2


class TestRemoveItemFromCategory:
    """Tests for handlers.remove_item_from_category."""

    def test_removes_placement(self, service: TaxomeshService) -> None:
        """Item placement is removed without error."""
        cat = service.create_category(name="Bin")
        item = service.create_item(name="Junk")
        service.place_item_in_category(item.item_id, cat.category_id)
        handlers.remove_item_from_category(service, item.item_id, cat.category_id)
        items_in_cat = service.list_items(category_id=cat.category_id)
        assert item.item_id not in [i.item_id for i in items_in_cat]


class TestAssignTag:
    """Tests for handlers.assign_tag."""

    def test_assigns_tag(self, service: TaxomeshService) -> None:
        """Tag is assigned to item without error (idempotent)."""
        tag = service.create_tag(name="hot")
        item = service.create_item(name="Product")
        handlers.assign_tag(service, tag.tag_id, item.item_id)
        # Second call is idempotent — no error.
        handlers.assign_tag(service, tag.tag_id, item.item_id)


class TestRemoveTagFromItem:
    """Tests for handlers.remove_tag_from_item."""

    def test_removes_tag(self, service: TaxomeshService) -> None:
        """Tag association is removed without error."""
        tag = service.create_tag(name="cool")
        item = service.create_item(name="Thing")
        service.assign_tag(tag.tag_id, item.item_id)
        handlers.remove_tag_from_item(service, tag.tag_id, item.item_id)
        # No exception = success.


# ---------------------------------------------------------------------------
# Search handlers
# ---------------------------------------------------------------------------


class TestSearchItems:
    """Tests for handlers.search_items."""

    def test_returns_matching_items(self, service: TaxomeshService) -> None:
        """Items matching the query are returned as Item instances."""
        service.create_item(name="Anibal Troilo")
        service.create_item(name="Carlos Gardel")
        params = SearchItemsRequest(q="Troilo")
        result = handlers.search_items(service, params)
        assert any(i.name == "Anibal Troilo" for i in result)
        assert all(isinstance(i, Item) for i in result)

    def test_blank_q_returns_empty(self, service: TaxomeshService) -> None:
        """Blank query returns an empty list."""
        service.create_item(name="Troilo")
        params = SearchItemsRequest(q="")
        result = handlers.search_items(service, params)
        assert result == []

    def test_enabled_only_excludes_disabled(self, service: TaxomeshService) -> None:
        """enabled_only=True excludes disabled items."""
        item = service.create_item(name="Piazzolla")
        service.update_item(item_id=item.item_id, enabled=False)
        params = SearchItemsRequest(q="Piazzolla", enabled_only=True)
        result = handlers.search_items(service, params)
        assert all(i.enabled for i in result)

    def test_limit_respected(self, service: TaxomeshService) -> None:
        """limit parameter caps the result count."""
        for i in range(10):
            service.create_item(name=f"Tango {i}")
        params = SearchItemsRequest(q="Tango", limit=3)
        result = handlers.search_items(service, params)
        assert len(result) <= 3

    def test_unknown_category_id_raises(self, service: TaxomeshService) -> None:
        """Non-existent category_id propagates TaxomeshCategoryNotFoundError."""
        params = SearchItemsRequest(q="anything", category_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.search_items(service, params)

    def test_category_scoping_with_recursive(self, service: TaxomeshService) -> None:
        """recursive=True includes items in descendant categories; False excludes them."""
        parent = service.create_category(name="Music")
        child = service.create_category(name="Music Sub")
        service.add_category_parent(child.category_id, parent.category_id)
        item = service.create_item(name="Troilo Bandoneón")
        service.place_item_in_category(item.item_id, child.category_id)

        params_recursive = SearchItemsRequest(q="Troilo", category_id=parent.category_id, recursive=True)
        result_recursive = handlers.search_items(service, params_recursive)
        assert any(i.item_id == item.item_id for i in result_recursive)

        params_direct = SearchItemsRequest(q="Troilo", category_id=parent.category_id, recursive=False)
        result_direct = handlers.search_items(service, params_direct)
        assert all(i.item_id != item.item_id for i in result_direct)

    def test_fuzzy_false_restricts_matching(self, service: TaxomeshService) -> None:
        """fuzzy=False restricts to exact/substring matching — typos are not matched."""
        service.create_item(name="Piazzolla Astor")

        params_exact = SearchItemsRequest(q="Piazzolla", fuzzy=False)
        assert any(i.name == "Piazzolla Astor" for i in handlers.search_items(service, params_exact))

        params_typo = SearchItemsRequest(q="Piazcolla", fuzzy=False)
        assert all(i.name != "Piazzolla Astor" for i in handlers.search_items(service, params_typo))

    def test_whitespace_q_returns_empty(self, service: TaxomeshService) -> None:
        """Whitespace-only query returns an empty list."""
        service.create_item(name="Troilo")
        params = SearchItemsRequest(q="   ")
        assert handlers.search_items(service, params) == []

    def test_invalid_limit_raises_value_error(self, service: TaxomeshService) -> None:
        """limit <= 0 propagates ValueError from service without wrapping."""
        params = SearchItemsRequest(q="tango", limit=0)
        with pytest.raises(ValueError):
            handlers.search_items(service, params)


class TestSearchCategories:
    """Tests for handlers.search_categories."""

    def test_returns_matching_categories(self, service: TaxomeshService) -> None:
        """Categories matching the query are returned as Category instances."""
        service.create_category(name="Jazz")
        service.create_category(name="Rock")
        params = SearchCategoriesRequest(q="Jazz")
        result = handlers.search_categories(service, params)
        assert any(c.name == "Jazz" for c in result)
        assert all(isinstance(c, Category) for c in result)

    def test_blank_q_returns_empty(self, service: TaxomeshService) -> None:
        """Blank query returns an empty list."""
        service.create_category(name="Jazz")
        params = SearchCategoriesRequest(q="")
        result = handlers.search_categories(service, params)
        assert result == []

    def test_enabled_only_true_returns_enabled_categories(self, service: TaxomeshService) -> None:
        """enabled_only=True returns only enabled categories (all categories are enabled by default)."""
        service.create_category(name="Tango")
        params = SearchCategoriesRequest(q="Tango", enabled_only=True)
        result = handlers.search_categories(service, params)
        assert all(c.enabled for c in result)

    def test_limit_respected(self, service: TaxomeshService) -> None:
        """limit parameter caps the result count."""
        for i in range(10):
            service.create_category(name=f"Genre {i}")
        params = SearchCategoriesRequest(q="Genre", limit=2)
        result = handlers.search_categories(service, params)
        assert len(result) <= 2

    def test_unknown_parent_id_raises(self, service: TaxomeshService) -> None:
        """Non-existent parent_id propagates TaxomeshCategoryNotFoundError."""
        params = SearchCategoriesRequest(q="anything", parent_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.search_categories(service, params)

    def test_parent_id_restricts_to_direct_children(self, service: TaxomeshService) -> None:
        """parent_id restricts results to direct children of the given parent."""
        parent = service.create_category(name="Music Genre")
        child = service.create_category(name="Tango Child")
        service.add_category_parent(child.category_id, parent.category_id)
        unrelated = service.create_category(name="Tango Unrelated")

        params = SearchCategoriesRequest(q="Tango", parent_id=parent.category_id)
        result = handlers.search_categories(service, params)
        ids = [c.category_id for c in result]
        assert child.category_id in ids
        assert unrelated.category_id not in ids

    def test_whitespace_q_returns_empty(self, service: TaxomeshService) -> None:
        """Whitespace-only query returns an empty list."""
        service.create_category(name="Tango")
        params = SearchCategoriesRequest(q="   ")
        assert handlers.search_categories(service, params) == []


# ---------------------------------------------------------------------------
# Graph handler
# ---------------------------------------------------------------------------


class TestGetGraph:
    """Tests for handlers.get_graph."""

    def test_returns_taxomesh_graph(self, service: TaxomeshService) -> None:
        """Returns a TaxomeshGraph instance."""
        result = handlers.get_graph(service)
        assert isinstance(result, TaxomeshGraph)

    def test_graph_contains_created_category(self, service: TaxomeshService) -> None:
        """A top-level category appears in graph.roots."""
        service.create_category(name="Root Level")
        result = handlers.get_graph(service)
        names = [node.category.name for node in result.roots]
        assert "Root Level" in names
