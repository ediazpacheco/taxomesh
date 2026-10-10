"""Tests for slug field support in TaxomeshService."""

import re
from typing import Any

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshDuplicateSlugError
from tests.service.conftest import CountedService


# Any: a slug given as bytes is passed where the annotation asks for text, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


class TestCategoriesCreateWithSlug:
    def test_categories_create_with_slug_stores_it(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Books", slug="books")
        assert cat.slug == "books"

    def test_categories_create_without_slug_defaults_to_empty(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Music")
        assert cat.slug == ""

    def test_categories_create_duplicate_slug_raises(self, service: TaxomeshService) -> None:
        service.categories.create(name="Books", slug="books")
        message = "Slug 'books' is already used by another category"
        with pytest.raises(TaxomeshDuplicateSlugError, match=re.escape(message)):
            service.categories.create(name="Books2", slug="books")

    def test_categories_create_two_empty_slugs_do_not_conflict(self, service: TaxomeshService) -> None:
        service.categories.create(name="A")
        service.categories.create(name="B")


class TestItemsCreateWithSlug:
    def test_items_create_with_slug_stores_it(self, service: TaxomeshService) -> None:
        item = service.items.create(name="ext-1", external_id="ext-1", slug="my-item")
        assert item.slug == "my-item"

    def test_items_create_without_slug_defaults_to_empty(self, service: TaxomeshService) -> None:
        item = service.items.create(name="ext-1", external_id="ext-1")
        assert item.slug == ""

    def test_items_create_duplicate_slug_raises(self, service: TaxomeshService) -> None:
        service.items.create(name="ext-1", external_id="ext-1", slug="item-slug")
        message = "Slug 'item-slug' is already used by another item"
        with pytest.raises(TaxomeshDuplicateSlugError, match=re.escape(message)):
            service.items.create(name="ext-2", external_id="ext-2", slug="item-slug")

    def test_items_create_two_empty_slugs_do_not_conflict(self, service: TaxomeshService) -> None:
        service.items.create(name="ext-1", external_id="ext-1")
        service.items.create(name="ext-2", external_id="ext-2")


class TestCategoriesUpdateWithSlug:
    def test_categories_update_sets_slug(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Books")
        updated = service.categories.update(category=cat.category_id, slug="books")
        assert updated.slug == "books"

    def test_categories_update_slug_to_itself_does_not_raise(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Books", slug="books")
        updated = service.categories.update(category=cat.category_id, slug="books")
        assert updated.slug == "books"

    def test_categories_update_taking_another_slug_raises(self, service: TaxomeshService) -> None:
        service.categories.create(name="Books", slug="books")
        cat2 = service.categories.create(name="Music", slug="music")
        message = "Slug 'books' is already used by another category"
        with pytest.raises(TaxomeshDuplicateSlugError, match=re.escape(message)):
            service.categories.update(category=cat2.category_id, slug="books")

    def test_categories_update_slug_to_empty_clears_it(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Books", slug="books")
        updated = service.categories.update(category=cat.category_id, slug="")
        assert updated.slug == ""


class TestCategoriesGetBySlug:
    def test_categories_get_by_slug_returns_category(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="Books", slug="books")
        result = service.categories.get_by_slug("books")
        assert result is not None
        assert result.category_id == cat.category_id
        assert result.slug == "books"

    def test_categories_get_by_slug_not_found_returns_none(self, service: TaxomeshService) -> None:
        assert service.categories.get_by_slug("does-not-exist") is None

    def test_categories_get_by_slug_empty_slug_returns_none(self, service: TaxomeshService) -> None:
        """An empty slug is no slug, however many categories carry it.

        Every category created without a slug stores the empty one, and slug uniqueness exempts
        it, so the store holds two here. A lookup that consulted storage would return one of them:
        it did on Django, while the file backends met the hidden root first.
        """
        service.categories.create(name="Books")
        service.categories.create(name="Music")

        assert service.categories.get_by_slug("") is None


class TestItemsGetBySlug:
    def test_items_get_by_slug_returns_item(self, service: TaxomeshService) -> None:
        item = service.items.create(name="Widget", external_id="w-001", slug="widget")
        result = service.items.get_by_slug("widget")
        assert result is not None
        assert result.item_id == item.item_id
        assert result.slug == "widget"

    def test_items_get_by_slug_not_found_returns_none(self, service: TaxomeshService) -> None:
        assert service.items.get_by_slug("does-not-exist") is None

    def test_items_get_by_slug_empty_slug_returns_none(self, service: TaxomeshService) -> None:
        """An empty slug is no slug, however many items carry it.

        Two items are created without a slug, so a lookup that consulted storage would return
        one of them — which one depending on the backend.
        """
        service.items.create(name="Widget", external_id="w-001")
        service.items.create(name="Gadget", external_id="g-001")

        assert service.items.get_by_slug("") is None


class TestAnEmptySlugCostsNoRead:
    """The port takes a non-empty slug, so the empty one is answered before the port is consulted.

    The same shape as an external id of ``None``: a key that cannot match costs no
    storage read. Counted as every read gate counts, one repository call per read.
    """

    def test_category_lookup(self, counting_service: CountedService) -> None:
        counting_service.service.categories.create(name="Books")
        counting_service.cold()

        assert counting_service.service.categories.get_by_slug("") is None
        assert counting_service.reads.total == 0

    def test_item_lookup(self, counting_service: CountedService) -> None:
        counting_service.service.items.create(name="Widget", external_id="w-001")
        counting_service.cold()

        assert counting_service.service.items.get_by_slug("") is None
        assert counting_service.reads.total == 0


class TestItemsUpdateWithSlug:
    def test_items_update_sets_slug(self, service: TaxomeshService) -> None:
        item = service.items.create(name="ext-1", external_id="ext-1")
        updated = service.items.update(item=item.item_id, slug="item-slug")
        assert updated.slug == "item-slug"

    def test_items_update_slug_to_itself_does_not_raise(self, service: TaxomeshService) -> None:
        item = service.items.create(name="ext-1", external_id="ext-1", slug="item-slug")
        updated = service.items.update(item=item.item_id, slug="item-slug")
        assert updated.slug == "item-slug"

    def test_items_update_taking_another_slug_raises(self, service: TaxomeshService) -> None:
        service.items.create(name="ext-1", external_id="ext-1", slug="item-slug")
        item2 = service.items.create(name="ext-2", external_id="ext-2", slug="other-slug")
        message = "Slug 'item-slug' is already used by another item"
        with pytest.raises(TaxomeshDuplicateSlugError, match=re.escape(message)):
            service.items.update(item=item2.item_id, slug="item-slug")

    def test_items_update_slug_to_empty_clears_it(self, service: TaxomeshService) -> None:
        item = service.items.create(name="ext-1", external_id="ext-1", slug="item-slug")
        updated = service.items.update(item=item.item_id, slug="")
        assert updated.slug == ""


class TestASlugIsCheckedAsTheRowHoldsIt:
    """The model reads ``b"music"`` as the text ``"music"``, so the duplicate check reads it so too."""

    def test_categories_create(self, service: TaxomeshService) -> None:
        service.categories.create(name="Music", slug="music")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.categories.create(name="Other", slug=untyped(b"music"))

    def test_items_create(self, service: TaxomeshService) -> None:
        service.items.create(name="Song", slug="song")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.items.create(name="Other", slug=untyped(b"song"))

    def test_categories_update(self, service: TaxomeshService) -> None:
        service.categories.create(name="Music", slug="music")
        other = service.categories.create(name="Other")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.categories.update(other, slug=untyped(b"music"))

    def test_items_update(self, service: TaxomeshService) -> None:
        service.items.create(name="Song", slug="song")
        other = service.items.create(name="Other")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.items.update(other, slug=untyped(b"song"))
