"""Tests for contrib API handlers include_disabled param and search enabled param (spec 046).

Written before implementation (TDD-first).
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.schemas import SearchCategoriesRequest, SearchItemsRequest


class TestListCategoriesIncludeDisabled:
    def test_default_excludes_disabled(self, service: TaxomeshService) -> None:
        service.create_category(name="PublicCat")
        cat_off = service.create_category(name="PrivateCat")
        cat_off_obj = service.repository.get_category(cat_off.category_id)
        assert cat_off_obj is not None
        cat_off_obj.enabled = False
        service.repository.save_category(cat_off_obj)

        result = handlers.list_categories(service)
        names = {c.name for c in result}
        assert "PublicCat" in names
        assert "PrivateCat" not in names

    def test_include_disabled_true_returns_all(self, service: TaxomeshService) -> None:
        service.create_category(name="PublicCat2")
        cat_off = service.create_category(name="PrivateCat2")
        cat_off_obj = service.repository.get_category(cat_off.category_id)
        assert cat_off_obj is not None
        cat_off_obj.enabled = False
        service.repository.save_category(cat_off_obj)

        result = handlers.list_categories(service, include_disabled=True)
        names = {c.name for c in result}
        assert "PublicCat2" in names
        assert "PrivateCat2" in names


class TestListItemsIncludeDisabled:
    def test_default_excludes_disabled(self, service: TaxomeshService) -> None:
        service.create_item(name="PublicItem")
        item_off = service.create_item(name="PrivateItem")
        service.update_item(item_off.item_id, enabled=False)

        result = handlers.list_items(service)
        names = {i.name for i in result}
        assert "PublicItem" in names
        assert "PrivateItem" not in names

    def test_include_disabled_true_returns_all(self, service: TaxomeshService) -> None:
        service.create_item(name="PublicItem2")
        item_off = service.create_item(name="PrivateItem2")
        service.update_item(item_off.item_id, enabled=False)

        result = handlers.list_items(service, include_disabled=True)
        names = {i.name for i in result}
        assert "PublicItem2" in names
        assert "PrivateItem2" in names


class TestSearchItemsEnabledParam:
    def test_search_items_request_uses_enabled_field(self) -> None:
        req = SearchItemsRequest(q="test", enabled=False)
        assert req.enabled is False

    def test_search_items_handler_passes_enabled_param(self, service: TaxomeshService) -> None:
        service.create_item(name="VisibleWidget")
        item_off = service.create_item(name="HiddenWidget")
        service.update_item(item_off.item_id, enabled=False)

        params = SearchItemsRequest(q="Widget", enabled=True)
        result = handlers.search_items(service, params)
        names = {i.name for i in result}
        assert "VisibleWidget" in names
        assert "HiddenWidget" not in names


class TestSearchCategoriesEnabledParam:
    def test_search_categories_request_uses_enabled_field(self) -> None:
        req = SearchCategoriesRequest(q="test", enabled=True)
        assert req.enabled is True

    def test_search_categories_handler_passes_enabled_param(self, service: TaxomeshService) -> None:
        service.create_category(name="VisibleSection")
        cat_off = service.create_category(name="HiddenSection")
        cat_off_obj = service.repository.get_category(cat_off.category_id)
        assert cat_off_obj is not None
        cat_off_obj.enabled = False
        service.repository.save_category(cat_off_obj)

        params = SearchCategoriesRequest(q="Section", enabled=True)
        result = handlers.search_categories(service, params)
        names = {c.name for c in result}
        assert "VisibleSection" in names
        assert "HiddenSection" not in names
