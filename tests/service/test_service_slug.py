"""Tests for slug field support in TaxomeshService."""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshDuplicateSlugError


class TestCreateCategoryWithSlug:
    def test_create_category_with_slug_stores_it(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Books", slug="books")
        assert cat.slug == "books"

    def test_create_category_without_slug_defaults_to_empty(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Music")
        assert cat.slug == ""

    def test_create_category_duplicate_slug_raises(self, service: TaxomeshService) -> None:
        service.create_category(name="Books", slug="books")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.create_category(name="Books2", slug="books")

    def test_create_category_two_empty_slugs_do_not_conflict(self, service: TaxomeshService) -> None:
        service.create_category(name="A")
        service.create_category(name="B")


class TestCreateItemWithSlug:
    def test_create_item_with_slug_stores_it(self, service: TaxomeshService) -> None:
        item = service.create_item(name="ext-1", external_id="ext-1", slug="my-item")
        assert item.slug == "my-item"

    def test_create_item_without_slug_defaults_to_empty(self, service: TaxomeshService) -> None:
        item = service.create_item(name="ext-1", external_id="ext-1")
        assert item.slug == ""

    def test_create_item_duplicate_slug_raises(self, service: TaxomeshService) -> None:
        service.create_item(name="ext-1", external_id="ext-1", slug="item-slug")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.create_item(name="ext-2", external_id="ext-2", slug="item-slug")

    def test_create_item_two_empty_slugs_do_not_conflict(self, service: TaxomeshService) -> None:
        service.create_item(name="ext-1", external_id="ext-1")
        service.create_item(name="ext-2", external_id="ext-2")


class TestUpdateCategoryWithSlug:
    def test_update_category_sets_slug(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Books")
        updated = service.update_category(category_id=cat.category_id, slug="books")
        assert updated.slug == "books"

    def test_update_category_slug_to_itself_does_not_raise(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Books", slug="books")
        updated = service.update_category(category_id=cat.category_id, slug="books")
        assert updated.slug == "books"

    def test_update_category_taking_another_slug_raises(self, service: TaxomeshService) -> None:
        service.create_category(name="Books", slug="books")
        cat2 = service.create_category(name="Music", slug="music")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.update_category(category_id=cat2.category_id, slug="books")

    def test_update_category_slug_to_empty_clears_it(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Books", slug="books")
        updated = service.update_category(category_id=cat.category_id, slug="")
        assert updated.slug == ""


class TestUpdateItemWithSlug:
    def test_update_item_sets_slug(self, service: TaxomeshService) -> None:
        item = service.create_item(name="ext-1", external_id="ext-1")
        updated = service.update_item(item_id=item.item_id, slug="item-slug")
        assert updated.slug == "item-slug"

    def test_update_item_slug_to_itself_does_not_raise(self, service: TaxomeshService) -> None:
        item = service.create_item(name="ext-1", external_id="ext-1", slug="item-slug")
        updated = service.update_item(item_id=item.item_id, slug="item-slug")
        assert updated.slug == "item-slug"

    def test_update_item_taking_another_slug_raises(self, service: TaxomeshService) -> None:
        service.create_item(name="ext-1", external_id="ext-1", slug="item-slug")
        item2 = service.create_item(name="ext-2", external_id="ext-2", slug="other-slug")
        with pytest.raises(TaxomeshDuplicateSlugError):
            service.update_item(item_id=item2.item_id, slug="item-slug")

    def test_update_item_slug_to_empty_clears_it(self, service: TaxomeshService) -> None:
        item = service.create_item(name="ext-1", external_id="ext-1", slug="item-slug")
        updated = service.update_item(item_id=item.item_id, slug="")
        assert updated.slug == ""
