"""Tests for slug field support in TaxomeshService."""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshDuplicateSlugError, TaxomeshItemNotFoundError


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


class TestGetCategoryBySlug:
    def test_get_category_by_slug_returns_category(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="Books", slug="books")
        result = service.get_category_by_slug("books")
        assert result.category_id == cat.category_id
        assert result.slug == "books"

    def test_get_category_by_slug_not_found_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.get_category_by_slug("does-not-exist")

    def test_get_category_by_slug_empty_slug_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.get_category_by_slug("")


class TestGetItemBySlug:
    def test_get_item_by_slug_returns_item(self, service: TaxomeshService) -> None:
        item = service.create_item(name="Widget", external_id="w-001", slug="widget")
        result = service.get_item_by_slug("widget")
        assert result.item_id == item.item_id
        assert result.slug == "widget"

    def test_get_item_by_slug_returns_unique_alias_match(self, service: TaxomeshService) -> None:
        item = service.create_item(
            name="Widget",
            external_id="w-001",
            slug="widget",
            metadata={"slug_aliases": ["old-widget"]},
        )
        result = service.get_item_by_slug("old-widget")
        assert result.item_id == item.item_id
        assert result.slug == "widget"

    def test_get_item_by_slug_not_found_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item_by_slug("does-not-exist")

    def test_get_item_by_slug_empty_slug_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item_by_slug("")

    def test_get_item_by_slug_missing_alias_raises(self, service: TaxomeshService) -> None:
        service.create_item(
            name="Widget",
            external_id="w-001",
            slug="widget",
            metadata={"slug_aliases": ["old-widget"]},
        )

        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item_by_slug("other-widget")

    def test_get_item_by_slug_duplicate_alias_raises(self, service: TaxomeshService) -> None:
        service.create_item(
            name="Widget",
            external_id="w-001",
            slug="widget",
            metadata={"slug_aliases": ["old-widget"]},
        )
        service.create_item(
            name="Gadget",
            external_id="g-001",
            slug="gadget",
            metadata={"slug_aliases": ["old-widget"]},
        )

        with pytest.raises(TaxomeshDuplicateSlugError):
            service.get_item_by_slug("old-widget")

    def test_get_item_by_slug_exact_slug_takes_precedence_over_alias(self, service: TaxomeshService) -> None:
        exact = service.create_item(name="Exact", external_id="exact-001", slug="old-widget")
        service.create_item(
            name="Widget",
            external_id="w-001",
            slug="widget",
            metadata={"slug_aliases": ["old-widget"]},
        )

        result = service.get_item_by_slug("old-widget")

        assert result.item_id == exact.item_id

    def test_get_item_by_slug_does_not_resolve_disabled_exact_item(self, service: TaxomeshService) -> None:
        item = service.create_item(name="Widget", external_id="w-001", slug="widget")
        service.update_item(item.item_id, enabled=False)

        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item_by_slug("widget")

    def test_get_item_by_slug_does_not_resolve_disabled_alias_item(self, service: TaxomeshService) -> None:
        item = service.create_item(
            name="Widget",
            external_id="w-001",
            slug="widget",
            metadata={"slug_aliases": ["old-widget"]},
        )
        service.update_item(item.item_id, enabled=False)

        with pytest.raises(TaxomeshItemNotFoundError):
            service.get_item_by_slug("old-widget")


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
