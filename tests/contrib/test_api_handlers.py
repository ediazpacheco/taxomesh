"""Tests for taxomesh.contrib.api.handlers — delegation to TaxomeshService."""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import get_args
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.errors import to_tuple
from taxomesh.contrib.api.schemas import (
    AddCategoryParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceItemRequest,
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
    TaxomeshExternalIdConflictError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshVersionConflictError,
)

# ---------------------------------------------------------------------------
# Category handlers
# ---------------------------------------------------------------------------


class TestCategoriesList:
    """Tests for handlers.categories_list: what ``svc.categories.list()`` answers."""

    def test_returns_the_members_tuple(self, service: TaxomeshService) -> None:
        """The handler hands back the member's own sequence, a tuple, as every listing is."""
        result = handlers.categories_list(service)
        assert isinstance(result, tuple)

    def test_includes_created_category(self, service: TaxomeshService) -> None:
        """A created category appears in the listing."""
        service.categories.create(name="Fiction")
        result = handlers.categories_list(service)
        assert any(c.name == "Fiction" for c in result)

    def test_lists_every_category_not_only_the_top_level(self, service: TaxomeshService) -> None:
        """A category with a parent is listed too: no filter means every category."""
        parent = service.categories.create(name="Parent")
        child = service.categories.create(name="Child")
        service.categories.add_parent(child, parent)
        assert {c.name for c in handlers.categories_list(service)} == {"Parent", "Child"}

    def test_parent_id_lists_the_children(self, service: TaxomeshService) -> None:
        """``parent_id`` selects that parent's children, as the member's ``parent`` does."""
        parent = service.categories.create(name="Parent")
        child = service.categories.create(name="Child")
        service.categories.add_parent(child, parent)
        assert [c.name for c in handlers.categories_list(service, parent_id=parent.category_id)] == ["Child"]

    def test_item_id_lists_the_categories_holding_the_item(self, service: TaxomeshService) -> None:
        """``item_id`` selects the categories the item is placed in, as the member's ``item`` does."""
        holding = service.categories.create(name="Holding")
        service.categories.create(name="Other")
        item = service.items.create(name="Thing")
        service.items.place_in(item, holding)
        assert [c.name for c in handlers.categories_list(service, item_id=item.item_id)] == ["Holding"]

    def test_unknown_item_id_raises(self, service: TaxomeshService) -> None:
        """A filter naming no stored item is a wrong address, as it is on the member."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.categories_list(service, item_id=uuid4())


class TestCategoriesRoots:
    """Tests for handlers.categories_roots: the top level."""

    def test_lists_the_top_level_only(self, service: TaxomeshService) -> None:
        """A category with a parent is not at the top level."""
        parent = service.categories.create(name="Parent")
        child = service.categories.create(name="Child")
        service.categories.add_parent(child, parent)
        assert [c.name for c in handlers.categories_roots(service)] == ["Parent"]

    def test_enabled_filters_as_the_member_does(self, service: TaxomeshService) -> None:
        """``enabled`` defaults to True, and None answers every top-level category."""
        service.categories.create(name="On")
        off = service.categories.create(name="Off")
        service.categories.update(off, enabled=False)
        assert {c.name for c in handlers.categories_roots(service)} == {"On"}
        assert {c.name for c in handlers.categories_roots(service, enabled=None)} == {"On", "Off"}

    def test_returns_the_members_tuple(self, service: TaxomeshService) -> None:
        """The handler hands back what ``roots()`` returns."""
        assert handlers.categories_roots(service) == service.categories.roots()


class TestCategoriesGet:
    """Tests for handlers.categories_get."""

    def test_returns_category(self, service: TaxomeshService) -> None:
        """Returns the matching Category by id."""
        cat = service.categories.create(name="Science")
        result = handlers.categories_get(service, cat.category_id)
        assert isinstance(result, Category)
        assert result.category_id == cat.category_id

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unknown id is a miss, answered with None as ``categories.get`` answers it."""
        assert handlers.categories_get(service, uuid4()) is None

    def test_the_root_is_a_miss(self, service: TaxomeshService) -> None:
        """The implicit root is not a row of the container."""
        assert handlers.categories_get(service, service._root_id) is None


class TestCategoriesGetBySlug:
    """Tests for handlers.categories_get_by_slug."""

    def test_returns_category(self, service: TaxomeshService) -> None:
        """Returns the matching Category by slug."""
        service.categories.create(name="History", slug="history")
        result = handlers.categories_get_by_slug(service, "history")
        assert result is not None
        assert result.slug == "history"

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unknown slug is a miss, answered with None."""
        assert handlers.categories_get_by_slug(service, "no-such-slug") is None

    def test_empty_slug_is_a_miss(self, service: TaxomeshService) -> None:
        """An empty slug names no category, not one stored without a slug."""
        service.categories.create(name="Unslugged")
        assert handlers.categories_get_by_slug(service, "") is None


class TestCategoriesGetByExternalId:
    """Tests for handlers.categories_get_by_external_id."""

    def test_returns_matching_category(self, service: TaxomeshService) -> None:
        """Returns the category with the given external_id."""
        service.categories.create(name="X", external_id="ext-7")
        result = handlers.categories_get_by_external_id(service, "ext-7")
        assert result is not None
        assert result.external_id == "ext-7"

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unmatched external_id is a miss, answered with None."""
        assert handlers.categories_get_by_external_id(service, "ghost") is None


class TestCategoriesCreate:
    """Tests for handlers.categories_create."""

    def test_creates_and_returns_category(self, service: TaxomeshService) -> None:
        """Returns a Category with the provided fields."""
        body = CreateCategoryRequest(name="Travel", description="Trip stuff", slug="travel")
        result = handlers.categories_create(service, body=body)
        assert isinstance(result, Category)
        assert result.name == "Travel"
        assert result.description == "Trip stuff"
        assert result.slug == "travel"

    def test_category_persisted(self, service: TaxomeshService) -> None:
        """The created category can be retrieved by id afterwards."""
        body = CreateCategoryRequest(name="Art")
        result = handlers.categories_create(service, body=body)
        fetched = service.categories[result.category_id]
        assert fetched.name == "Art"

    def test_stores_the_external_id(self, service: TaxomeshService) -> None:
        """``external_id`` reaches ``categories.create``, as it does on the item request."""
        result = handlers.categories_create(service, body=CreateCategoryRequest(name="Art", external_id="ext-art"))
        assert result.external_id == "ext-art"
        assert service.categories.get_by_external_id("ext-art") == result


class TestCategoriesUpdate:
    """Tests for handlers.categories_update."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        cat = service.categories.create(name="Old")
        body = UpdateCategoryRequest(name="New")
        result = handlers.categories_update(service, cat.category_id, body=body)
        assert result.name == "New"

    def test_none_fields_unchanged(self, service: TaxomeshService) -> None:
        """Fields left as None are not modified."""
        cat = service.categories.create(name="Keep", description="desc")
        body = UpdateCategoryRequest()
        result = handlers.categories_update(service, cat.category_id, body=body)
        assert result.name == "Keep"
        assert result.description == "desc"

    def test_sets_external_id(self, service: TaxomeshService) -> None:
        """A supplied external_id string is stored."""
        cat = service.categories.create(name="Cat")
        result = handlers.categories_update(
            service, cat.category_id, body=UpdateCategoryRequest(external_id="ext-cat")
        )
        assert result.external_id == "ext-cat"

    def test_omitted_external_id_is_unchanged(self, service: TaxomeshService) -> None:
        """An omitted external_id is preserved during an unrelated update."""
        cat = service.categories.create(name="Cat")
        handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(external_id="ext-cat"))
        result = handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(name="Renamed"))
        assert result.name == "Renamed"
        assert result.external_id == "ext-cat"

    def test_explicit_null_clears_external_id(self, service: TaxomeshService) -> None:
        """An explicitly null external_id clears the stored value."""
        cat = service.categories.create(name="Cat")
        handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(external_id="ext-cat"))
        result = handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(external_id=None))
        assert result.external_id is None

    def test_sets_enabled(self, service: TaxomeshService) -> None:
        """A supplied enabled state is stored."""
        cat = service.categories.create(name="Cat")
        result = handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(enabled=False))
        assert result.enabled is False


class TestUpdateExternalIdConflict:
    """An external-id collision through a public handler
    surfaces as 409, identically to the slug conflict. Uses a JSON-backed service because the
    conflict is enforced by real storage adapters (the in-memory test fixture does not enforce)."""

    def _json_service(self, tmp_path: Path) -> TaxomeshService:
        return TaxomeshService(repository=JsonRepository(tmp_path / "conflict.json"))

    def test_category_external_id_conflict_maps_to_409(self, tmp_path: Path) -> None:
        """Updating a category to an external_id held by another category conflicts → 409."""
        service = self._json_service(tmp_path)
        service.categories.create(name="A", external_id="shared")
        target = service.categories.create(name="B")
        with pytest.raises(TaxomeshExternalIdConflictError) as exc_info:
            handlers.categories_update(service, target.category_id, body=UpdateCategoryRequest(external_id="shared"))
        status, _ = to_tuple(exc_info.value)
        assert status == 409

    def test_item_external_id_conflict_maps_to_409(self, tmp_path: Path) -> None:
        """Updating an item to an external_id held by another item conflicts → 409."""
        service = self._json_service(tmp_path)
        service.items.create(name="A", external_id="shared")
        target = service.items.create(name="B")
        with pytest.raises(TaxomeshExternalIdConflictError) as exc_info:
            handlers.items_update(service, target.item_id, body=UpdateItemRequest(external_id="shared"))
        status, _ = to_tuple(exc_info.value)
        assert status == 409


class TestUpdateExpectedVersion:
    """The two update requests carry ``expected_version``, and their handlers pass it on."""

    def test_the_update_requests_leave_it_to_none(self) -> None:
        """Omitted, it makes no comparison, as in the Python API."""
        assert UpdateCategoryRequest().expected_version is None
        assert UpdateItemRequest().expected_version is None

    def test_a_category_update_at_a_stale_version_maps_to_409(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="A")
        handlers.categories_update(service, cat.category_id, body=UpdateCategoryRequest(name="B", expected_version=0))
        with pytest.raises(TaxomeshVersionConflictError) as exc_info:
            handlers.categories_update(
                service, cat.category_id, body=UpdateCategoryRequest(name="C", expected_version=0)
            )
        status, _ = to_tuple(exc_info.value)
        assert status == 409
        assert service.categories[cat.category_id].name == "B"

    def test_an_item_update_at_a_stale_version_maps_to_409(self, service: TaxomeshService) -> None:
        item = service.items.create(name="A")
        handlers.items_update(service, item.item_id, body=UpdateItemRequest(name="B", expected_version=0))
        with pytest.raises(TaxomeshVersionConflictError) as exc_info:
            handlers.items_update(service, item.item_id, body=UpdateItemRequest(name="C", expected_version=0))
        status, _ = to_tuple(exc_info.value)
        assert status == 409
        assert service.items[item.item_id].name == "B"


class TestCategoriesDelete:
    """Tests for handlers.categories_delete."""

    def test_deletes_category(self, service: TaxomeshService) -> None:
        """Category is removed after deletion."""
        cat = service.categories.create(name="Temp")
        handlers.categories_delete(service, cat.category_id)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories[cat.category_id]

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshCategoryNotFoundError."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.categories_delete(service, uuid4())


class TestRootAddressedWritesMapTo404:
    """The root id is not-found through the handlers, so it surfaces as 404.

    These three raised TaxomeshRootCategoryError before 062, which matches no branch in
    errors.to_tuple and therefore landed on the redacted 500 fallback. Both halves change: the
    status, and the body, which now carries the caller-actionable message instead of the generic
    server-error detail.
    """

    def test_categories_update_maps_to_404(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError) as exc_info:
            handlers.categories_update(service, service._root_id, body=UpdateCategoryRequest(name="x"))
        status, body = to_tuple(exc_info.value)
        assert status == 404
        assert str(service._root_id) in body["detail"]

    def test_categories_delete_maps_to_404(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError) as exc_info:
            handlers.categories_delete(service, service._root_id)
        status, body = to_tuple(exc_info.value)
        assert status == 404
        assert str(service._root_id) in body["detail"]

    def test_categories_add_parent_maps_to_404(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Alpha")
        body_in = AddCategoryParentRequest(parent_id=cat.category_id, sort_index=0)
        with pytest.raises(TaxomeshCategoryNotFoundError) as exc_info:
            handlers.categories_add_parent(service, service._root_id, body=body_in)
        status, body = to_tuple(exc_info.value)
        assert status == 404
        assert str(service._root_id) in body["detail"]


# ---------------------------------------------------------------------------
# Item handlers
# ---------------------------------------------------------------------------


class TestItemsList:
    """Tests for handlers.items_list: what ``svc.items.list()`` answers."""

    def test_returns_the_members_tuple(self, service: TaxomeshService) -> None:
        """The handler hands back the member's own sequence, a tuple."""
        result = handlers.items_list(service)
        assert isinstance(result, tuple)

    def test_includes_created_item(self, service: TaxomeshService) -> None:
        """A created item appears in the listing."""
        service.items.create(name="Widget")
        result = handlers.items_list(service)
        assert any(i.name == "Widget" for i in result)

    def test_tag_id_lists_the_tagged_items(self, service: TaxomeshService) -> None:
        """``tag_id`` selects the items carrying the tag, as the member's ``tag`` does."""
        tagged = service.items.create(name="Tagged")
        service.items.create(name="Plain")
        live = service.tags.create(name="live")
        service.items.tag(tagged, live)
        assert [i.name for i in handlers.items_list(service, tag_id=live.tag_id)] == ["Tagged"]

    def test_tag_id_composes_with_category_id(self, service: TaxomeshService) -> None:
        """Both filters keep the category's items that carry the tag."""
        shelf = service.categories.create(name="Shelf")
        inside = service.items.create(name="Inside")
        outside = service.items.create(name="Outside")
        live = service.tags.create(name="live")
        service.items.place_in(inside, shelf)
        service.items.tag(inside, live)
        service.items.tag(outside, live)
        found = handlers.items_list(service, category_id=shelf.category_id, tag_id=live.tag_id)
        assert [i.name for i in found] == ["Inside"]

    def test_recursive_reaches_the_descendants(self, service: TaxomeshService) -> None:
        """``recursive`` takes the category's descendants in, as the member's does."""
        parent = service.categories.create(name="Parent")
        child = service.categories.create(name="Child")
        service.categories.add_parent(child, parent)
        deep = service.items.create(name="Deep")
        service.items.place_in(deep, child)
        assert handlers.items_list(service, category_id=parent.category_id) == ()
        found = handlers.items_list(service, category_id=parent.category_id, recursive=True)
        assert [i.name for i in found] == ["Deep"]

    def test_unknown_tag_id_raises(self, service: TaxomeshService) -> None:
        """A filter naming no stored tag is a wrong address, as it is on the member."""
        with pytest.raises(TaxomeshTagNotFoundError):
            handlers.items_list(service, tag_id=uuid4())


class TestItemsGet:
    """Tests for handlers.items_get."""

    def test_returns_item(self, service: TaxomeshService) -> None:
        """Returns the matching Item by id."""
        item = service.items.create(name="Gadget")
        result = handlers.items_get(service, item.item_id)
        assert isinstance(result, Item)
        assert result.item_id == item.item_id

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unknown id is a miss, answered with None as ``items.get`` answers it."""
        assert handlers.items_get(service, uuid4()) is None


class TestItemsGetBySlug:
    """Tests for handlers.items_get_by_slug."""

    def test_returns_item(self, service: TaxomeshService) -> None:
        """Returns the matching Item by slug."""
        service.items.create(name="Gadget", slug="gadget")
        result = handlers.items_get_by_slug(service, "gadget")
        assert result is not None
        assert result.slug == "gadget"

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unknown slug is a miss, answered with None."""
        assert handlers.items_get_by_slug(service, "no-such-slug") is None

    def test_empty_slug_is_a_miss(self, service: TaxomeshService) -> None:
        """An empty slug names no item, not the first one stored without a slug."""
        service.items.create(name="Unslugged")
        assert handlers.items_get_by_slug(service, "") is None


class TestItemsGetByExternalId:
    """Tests for handlers.items_get_by_external_id."""

    def test_returns_matching_item(self, service: TaxomeshService) -> None:
        """Returns the item with the given external_id."""
        service.items.create(name="X", external_id="ext-99")
        result = handlers.items_get_by_external_id(service, "ext-99")
        assert result is not None
        assert result.external_id == "ext-99"

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unmatched external_id is a miss, answered with None."""
        assert handlers.items_get_by_external_id(service, "ghost") is None


class TestItemsCreate:
    """Tests for handlers.items_create."""

    def test_creates_and_returns_item(self, service: TaxomeshService) -> None:
        """Returns an Item with the provided fields."""
        body = CreateItemRequest(name="Widget", external_id="w1", slug="widget")
        result = handlers.items_create(service, body=body)
        assert isinstance(result, Item)
        assert result.name == "Widget"
        assert result.external_id == "w1"

    def test_item_persisted(self, service: TaxomeshService) -> None:
        """The created item can be retrieved by id afterwards."""
        body = CreateItemRequest(name="Gadget")
        result = handlers.items_create(service, body=body)
        fetched = service.items[result.item_id]
        assert fetched.name == "Gadget"


class TestItemsUpdate:
    """Tests for handlers.items_update."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        item = service.items.create(name="Old Item")
        body = UpdateItemRequest(name="New Item")
        result = handlers.items_update(service, item.item_id, body=body)
        assert result.name == "New Item"

    def test_updates_enabled(self, service: TaxomeshService) -> None:
        """enabled field is updated when provided."""
        item = service.items.create(name="Active")
        body = UpdateItemRequest(enabled=False)
        result = handlers.items_update(service, item.item_id, body=body)
        assert result.enabled is False

    def test_omitted_external_id_is_unchanged(self, service: TaxomeshService) -> None:
        """An omitted external_id is preserved during an unrelated update."""
        item = service.items.create(name="Item", external_id="ext-original")
        body = UpdateItemRequest(name="Renamed Item")
        result = handlers.items_update(service, item.item_id, body=body)
        assert result.external_id == "ext-original"

    def test_updates_external_id_to_explicit_value(self, service: TaxomeshService) -> None:
        """external_id is updated when an explicit value is provided."""
        item = service.items.create(name="Item")
        body = UpdateItemRequest(external_id="ext-42")
        result = handlers.items_update(service, item.item_id, body=body)
        assert result.external_id == "ext-42"

    def test_explicit_none_clears_external_id(self, service: TaxomeshService) -> None:
        """An explicitly null external_id clears the stored value."""
        item = service.items.create(name="Item", external_id="ext-original")
        body = UpdateItemRequest(external_id=None)
        result = handlers.items_update(service, item.item_id, body=body)
        assert result.external_id is None


class TestItemsDelete:
    """Tests for handlers.items_delete."""

    def test_deletes_item(self, service: TaxomeshService) -> None:
        """Item is removed after deletion."""
        item = service.items.create(name="Gone")
        handlers.items_delete(service, item.item_id)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items[item.item_id]

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshItemNotFoundError."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.items_delete(service, uuid4())


# ---------------------------------------------------------------------------
# Tag handlers
# ---------------------------------------------------------------------------


class TestTagsList:
    """Tests for handlers.tags_list: what ``svc.tags.list()`` answers."""

    def test_returns_the_members_tuple(self, service: TaxomeshService) -> None:
        """The handler hands back the member's own sequence, a tuple."""
        result = handlers.tags_list(service)
        assert isinstance(result, tuple)

    def test_includes_created_tag(self, service: TaxomeshService) -> None:
        """A created tag appears in the listing."""
        service.tags.create(name="sci-fi")
        result = handlers.tags_list(service)
        assert any(t.name == "sci-fi" for t in result)

    def test_item_id_lists_the_items_tags(self, service: TaxomeshService) -> None:
        """``item_id`` selects the tags the item carries, as the member's ``item`` does."""
        item = service.items.create(name="Thing")
        live = service.tags.create(name="live")
        service.tags.create(name="studio")
        service.items.tag(item, live)
        assert [t.name for t in handlers.tags_list(service, item_id=item.item_id)] == ["live"]

    def test_unknown_item_id_raises(self, service: TaxomeshService) -> None:
        """A filter naming no stored item is a wrong address, as it is on the member."""
        with pytest.raises(TaxomeshItemNotFoundError):
            handlers.tags_list(service, item_id=uuid4())


class TestTagsGet:
    """Tests for handlers.tags_get."""

    def test_returns_tag(self, service: TaxomeshService) -> None:
        """Returns the matching Tag by id."""
        live = service.tags.create(name="live")
        assert handlers.tags_get(service, live.tag_id) == live

    def test_miss_returns_none(self, service: TaxomeshService) -> None:
        """An unknown id is a miss, answered with None as ``tags.get`` answers it."""
        assert handlers.tags_get(service, uuid4()) is None


class TestTagsCreate:
    """Tests for handlers.tags_create."""

    def test_creates_and_returns_tag(self, service: TaxomeshService) -> None:
        """Returns a Tag with the provided fields."""
        body = CreateTagRequest(name="fantasy")
        result = handlers.tags_create(service, body=body)
        assert isinstance(result, Tag)
        assert result.name == "fantasy"


class TestTagsUpdate:
    """Tests for handlers.tags_update."""

    def test_updates_name(self, service: TaxomeshService) -> None:
        """Name field is updated when provided."""
        tag = service.tags.create(name="old-tag")
        body = UpdateTagRequest(name="new-tag")
        result = handlers.tags_update(service, tag.tag_id, body=body)
        assert result.name == "new-tag"

    def test_updates_metadata(self, service: TaxomeshService) -> None:
        """metadata is forwarded, so a tag's metadata can be changed over HTTP."""
        tag = service.tags.create(name="genre", metadata={"era": "1940s"})
        body = UpdateTagRequest(metadata={"era": "1950s"})
        result = handlers.tags_update(service, tag.tag_id, body=body)
        assert result.metadata == {"era": "1950s"}

    def test_omitted_metadata_is_left_alone(self, service: TaxomeshService) -> None:
        """An omitted metadata carries no instruction, exactly as for items and categories."""
        tag = service.tags.create(name="genre", metadata={"era": "1940s"})
        result = handlers.tags_update(service, tag.tag_id, body=UpdateTagRequest(name="renamed"))
        assert result.name == "renamed"
        assert result.metadata == {"era": "1940s"}

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshTagNotFoundError."""
        with pytest.raises(TaxomeshTagNotFoundError):
            handlers.tags_update(service, uuid4(), body=UpdateTagRequest(name="x"))


class TestTagsDelete:
    """Tests for handlers.tags_delete."""

    def test_deletes_tag(self, service: TaxomeshService) -> None:
        """Tag is removed after deletion, and tags.list does not include it."""
        tag = service.tags.create(name="temp-tag")
        handlers.tags_delete(service, tag.tag_id)
        remaining = service.tags.list()
        assert all(t.tag_id != tag.tag_id for t in remaining)

    def test_not_found_raises(self, service: TaxomeshService) -> None:
        """Non-existent id raises TaxomeshTagNotFoundError."""
        with pytest.raises(TaxomeshTagNotFoundError):
            handlers.tags_delete(service, uuid4())


# ---------------------------------------------------------------------------
# Relationship handlers
# ---------------------------------------------------------------------------


class TestCategoriesAddParent:
    """Tests for handlers.categories_add_parent."""

    def test_returns_link(self, service: TaxomeshService) -> None:
        """Returns a CategoryParentLink for the new relationship."""
        parent = service.categories.create(name="Parent")
        child = service.categories.create(name="Child")
        body = AddCategoryParentRequest(parent_id=parent.category_id, sort_index=1)
        result = handlers.categories_add_parent(service, child.category_id, body=body)
        assert isinstance(result, CategoryParentLink)
        assert result.parent_category_id == parent.category_id
        assert result.sort_index == 1


class TestCategoriesRemoveParent:
    """Tests for handlers.categories_remove_parent."""

    def test_removes_parent(self, service: TaxomeshService) -> None:
        """Parent relationship is removed without error."""
        parent = service.categories.create(name="P")
        child = service.categories.create(name="C")
        service.categories.add_parent(child.category_id, parent.category_id)
        handlers.categories_remove_parent(service, child.category_id, parent_id=parent.category_id)
        # No exception means success; we simply verify it doesn't raise.


class TestItemsPlaceIn:
    """Tests for handlers.items_place_in."""

    def test_returns_link(self, service: TaxomeshService) -> None:
        """Returns an ItemParentLink for the placement."""
        cat = service.categories.create(name="Shelf")
        item = service.items.create(name="Book")
        body = PlaceItemRequest(category_id=cat.category_id, sort_index=2)
        result = handlers.items_place_in(service, item.item_id, body=body)
        assert isinstance(result, ItemParentLink)
        assert result.category_id == cat.category_id
        assert result.sort_index == 2


class TestItemsRemoveFrom:
    """Tests for handlers.items_remove_from."""

    def test_removes_placement(self, service: TaxomeshService) -> None:
        """Item placement is removed without error."""
        cat = service.categories.create(name="Bin")
        item = service.items.create(name="Junk")
        service.items.place_in(item.item_id, cat.category_id)
        handlers.items_remove_from(service, item.item_id, category_id=cat.category_id)
        items_in_cat = service.items.list(category=cat.category_id)
        assert item.item_id not in [i.item_id for i in items_in_cat]


class TestItemsTag:
    """Tests for handlers.items_tag."""

    def test_assigns_tag(self, service: TaxomeshService) -> None:
        """Tag is assigned to item without error (idempotent)."""
        tag = service.tags.create(name="hot")
        item = service.items.create(name="Product")
        handlers.items_tag(service, item.item_id, tag_id=tag.tag_id)
        # Second call is idempotent — no error.
        handlers.items_tag(service, item.item_id, tag_id=tag.tag_id)


class TestItemsUntag:
    """Tests for handlers.items_untag."""

    def test_removes_tag(self, service: TaxomeshService) -> None:
        """Tag association is removed without error."""
        tag = service.tags.create(name="cool")
        item = service.items.create(name="Thing")
        service.items.tag(item.item_id, tag.tag_id)
        handlers.items_untag(service, item.item_id, tag_id=tag.tag_id)
        # No exception = success.


# ---------------------------------------------------------------------------
# Search handlers
# ---------------------------------------------------------------------------


class TestItemsSearch:
    """Tests for handlers.items_search."""

    def test_returns_matching_items(self, service: TaxomeshService) -> None:
        """Items matching the query are returned as Item instances."""
        service.items.create(name="Anibal Troilo")
        service.items.create(name="Carlos Gardel")
        params = SearchItemsRequest(query="Troilo")
        result = handlers.items_search(service, params=params)
        assert any(i.name == "Anibal Troilo" for i in result)
        assert all(isinstance(i, Item) for i in result)

    def test_blank_query_returns_empty(self, service: TaxomeshService) -> None:
        """Blank query returns an empty tuple."""
        service.items.create(name="Troilo")
        params = SearchItemsRequest(query="")
        result = handlers.items_search(service, params=params)
        assert result == ()

    def test_enabled_true_excludes_disabled(self, service: TaxomeshService) -> None:
        """enabled=True excludes disabled items."""
        item = service.items.create(name="Piazzolla")
        service.items.update(item=item.item_id, enabled=False)
        params = SearchItemsRequest(query="Piazzolla", enabled=True)
        result = handlers.items_search(service, params=params)
        assert all(i.enabled for i in result)

    def test_limit_respected(self, service: TaxomeshService) -> None:
        """limit parameter caps the result count."""
        for i in range(10):
            service.items.create(name=f"Tango {i}")
        params = SearchItemsRequest(query="Tango", limit=3)
        result = handlers.items_search(service, params=params)
        assert len(result) <= 3

    def test_unknown_category_id_raises(self, service: TaxomeshService) -> None:
        """Non-existent category_id propagates TaxomeshCategoryNotFoundError."""
        params = SearchItemsRequest(query="anything", category_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.items_search(service, params=params)

    def test_unknown_category_id_raises_under_a_blank_query(self, service: TaxomeshService) -> None:
        """A blank query checks its filter too, so the edge answers 404 rather than 200 ``[]``."""
        params = SearchItemsRequest(query="   ", category_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.items_search(service, params=params)

    def test_category_scoping_with_recursive(self, service: TaxomeshService) -> None:
        """recursive=True includes items in descendant categories; False excludes them."""
        parent = service.categories.create(name="Music")
        child = service.categories.create(name="Music Sub")
        service.categories.add_parent(child.category_id, parent.category_id)
        item = service.items.create(name="Troilo Bandoneón")
        service.items.place_in(item.item_id, child.category_id)

        params_recursive = SearchItemsRequest(query="Troilo", category_id=parent.category_id, recursive=True)
        result_recursive = handlers.items_search(service, params=params_recursive)
        assert any(i.item_id == item.item_id for i in result_recursive)

        params_direct = SearchItemsRequest(query="Troilo", category_id=parent.category_id, recursive=False)
        result_direct = handlers.items_search(service, params=params_direct)
        assert all(i.item_id != item.item_id for i in result_direct)

    def test_fuzzy_false_restricts_matching(self, service: TaxomeshService) -> None:
        """fuzzy=False restricts to exact/substring matching — typos are not matched."""
        service.items.create(name="Piazzolla Astor")

        params_exact = SearchItemsRequest(query="Piazzolla", fuzzy=False)
        assert any(i.name == "Piazzolla Astor" for i in handlers.items_search(service, params=params_exact))

        params_typo = SearchItemsRequest(query="Piazcolla", fuzzy=False)
        assert all(i.name != "Piazzolla Astor" for i in handlers.items_search(service, params=params_typo))

    def test_whitespace_query_returns_empty(self, service: TaxomeshService) -> None:
        """Whitespace-only query returns an empty tuple."""
        service.items.create(name="Troilo")
        params = SearchItemsRequest(query="   ")
        assert handlers.items_search(service, params=params) == ()

    def test_invalid_limit_raises_value_error(self, service: TaxomeshService) -> None:
        """limit <= 0 propagates ValueError from service without wrapping."""
        params = SearchItemsRequest(query="tango", limit=0)
        with pytest.raises(ValueError):
            handlers.items_search(service, params=params)


class TestCategoriesSearch:
    """Tests for handlers.categories_search."""

    def test_returns_matching_categories(self, service: TaxomeshService) -> None:
        """Categories matching the query are returned as Category instances."""
        service.categories.create(name="Jazz")
        service.categories.create(name="Rock")
        params = SearchCategoriesRequest(query="Jazz")
        result = handlers.categories_search(service, params=params)
        assert any(c.name == "Jazz" for c in result)
        assert all(isinstance(c, Category) for c in result)

    def test_blank_query_returns_empty(self, service: TaxomeshService) -> None:
        """Blank query returns an empty tuple."""
        service.categories.create(name="Jazz")
        params = SearchCategoriesRequest(query="")
        result = handlers.categories_search(service, params=params)
        assert result == ()

    def test_enabled_true_returns_enabled_categories(self, service: TaxomeshService) -> None:
        """enabled=True returns only enabled categories (all categories are enabled by default)."""
        service.categories.create(name="Tango")
        params = SearchCategoriesRequest(query="Tango", enabled=True)
        result = handlers.categories_search(service, params=params)
        assert all(c.enabled for c in result)

    def test_limit_respected(self, service: TaxomeshService) -> None:
        """limit parameter caps the result count."""
        for i in range(10):
            service.categories.create(name=f"Genre {i}")
        params = SearchCategoriesRequest(query="Genre", limit=2)
        result = handlers.categories_search(service, params=params)
        assert len(result) <= 2

    def test_unknown_parent_id_raises(self, service: TaxomeshService) -> None:
        """Non-existent parent_id propagates TaxomeshCategoryNotFoundError."""
        params = SearchCategoriesRequest(query="anything", parent_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.categories_search(service, params=params)

    def test_unknown_parent_id_raises_under_a_blank_query(self, service: TaxomeshService) -> None:
        """A blank query checks its filter too, so the edge answers 404 rather than 200 ``[]``."""
        params = SearchCategoriesRequest(query="", parent_id=uuid4())
        with pytest.raises(TaxomeshCategoryNotFoundError):
            handlers.categories_search(service, params=params)

    def test_parent_id_restricts_to_direct_children(self, service: TaxomeshService) -> None:
        """parent_id restricts results to direct children of the given parent."""
        parent = service.categories.create(name="Music Genre")
        child = service.categories.create(name="Tango Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        unrelated = service.categories.create(name="Tango Unrelated")

        params = SearchCategoriesRequest(query="Tango", parent_id=parent.category_id)
        result = handlers.categories_search(service, params=params)
        ids = [c.category_id for c in result]
        assert child.category_id in ids
        assert unrelated.category_id not in ids

    def test_whitespace_query_returns_empty(self, service: TaxomeshService) -> None:
        """Whitespace-only query returns an empty tuple."""
        service.categories.create(name="Tango")
        params = SearchCategoriesRequest(query="   ")
        assert handlers.categories_search(service, params=params) == ()


# ---------------------------------------------------------------------------
# Graph handler
# ---------------------------------------------------------------------------


class TestGraph:
    """Tests for handlers.graph."""

    def test_returns_taxomesh_graph(self, service: TaxomeshService) -> None:
        """Returns a TaxomeshGraph instance."""
        result = handlers.graph(service)
        assert isinstance(result, TaxomeshGraph)

    def test_graph_contains_created_category(self, service: TaxomeshService) -> None:
        """A top-level category appears in graph.roots."""
        service.categories.create(name="Root Level")
        result = handlers.graph(service)
        names = [node.category.name for node in result.roots]
        assert "Root Level" in names


# ---------------------------------------------------------------------------
# The naming law
# ---------------------------------------------------------------------------

_NAMESPACES: dict[str, type] = {
    "categories": CategoryCollection,
    "items": ItemCollection,
    "tags": TagCollection,
}

_HANDLERS: dict[str, Callable[..., object]] = {
    name: member
    for name, member in inspect.getmembers(handlers, inspect.isfunction)
    if member.__module__ == handlers.__name__ and not name.startswith("_")
}


def _member_of(handler_name: str) -> tuple[type, str]:
    """Split a handler's name into the collection class and the member it names."""
    namespace, _, member = handler_name.partition("_")
    return _NAMESPACES[namespace], member


class TestHandlerNames:
    """Each handler is named ``<namespace>_<member>`` after the member it calls, or ``graph``."""

    @pytest.mark.parametrize("name", sorted(_HANDLERS))
    def test_names_a_member_of_its_namespace(self, name: str) -> None:
        """The part after the namespace is a public member of that namespace's collection."""
        if name == "graph":
            assert callable(TaxomeshService.graph)
            return
        assert name.partition("_")[0] in _NAMESPACES, f"{name} starts with no namespace"
        collection, member = _member_of(name)
        assert callable(getattr(collection, member, None)), f"{collection.__name__} has no member {member!r}"

    def test_the_handler_set(self) -> None:
        """Every member that had a handler keeps one, and the three new reads join them."""
        assert set(_HANDLERS) == {
            "categories_list",
            "categories_roots",
            "categories_get",
            "categories_get_by_slug",
            "categories_get_by_external_id",
            "categories_create",
            "categories_update",
            "categories_delete",
            "categories_add_parent",
            "categories_remove_parent",
            "categories_search",
            "items_list",
            "items_get",
            "items_get_by_slug",
            "items_get_by_external_id",
            "items_create",
            "items_update",
            "items_delete",
            "items_place_in",
            "items_remove_from",
            "items_tag",
            "items_untag",
            "items_search",
            "tags_list",
            "tags_get",
            "tags_create",
            "tags_update",
            "tags_delete",
            "graph",
        }

    @pytest.mark.parametrize("name", sorted(n for n in _HANDLERS if n.split("_", 1)[-1].startswith("get")))
    def test_a_lookup_answers_none_as_its_member_does(self, name: str) -> None:
        """A lookup handler's return annotation admits ``None``: a miss is not an error."""
        returns = inspect.signature(_HANDLERS[name], eval_str=True).return_annotation
        assert type(None) in get_args(returns), f"{name} returns {returns}, which cannot be None"
