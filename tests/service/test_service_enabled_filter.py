"""Tests for service-level enabled filter on list_categories, list_items,
list_categories_by_item, search_items, and search_categories (spec 046).

Written before implementation (TDD-first).
"""

import pytest

from taxomesh.application.service import TaxomeshService

# ---------------------------------------------------------------------------
# list_categories enabled filter
# ---------------------------------------------------------------------------


class TestListCategoriesEnabledFilter:
    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        service.create_category(name="EnabledCat")
        cat_off = service.create_category(name="DisabledCat")
        service.update_category(cat_off.category_id, enabled=False)

        result = service.list_categories(enabled=True)
        names = {c.name for c in result}
        assert "EnabledCat" in names
        assert "DisabledCat" not in names

    def test_enabled_false_returns_only_disabled(self, service: TaxomeshService) -> None:
        service.create_category(name="ActiveCat")
        cat_off = service.create_category(name="InactiveCat")
        service.update_category(cat_off.category_id, enabled=False)

        result = service.list_categories(enabled=False)
        names = {c.name for c in result}
        assert "InactiveCat" in names
        assert "ActiveCat" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.create_category(name="CatA")
        cat_off = service.create_category(name="CatB")
        service.update_category(cat_off.category_id, enabled=False)

        result = service.list_categories(enabled=None)
        names = {c.name for c in result}
        assert "CatA" in names
        assert "CatB" in names

    def test_enabled_true_is_default(self, service: TaxomeshService) -> None:
        service.create_category(name="DefaultOn")
        cat_off = service.create_category(name="DefaultOff")
        service.update_category(cat_off.category_id, enabled=False)

        result = service.list_categories()
        names = {c.name for c in result}
        assert "DefaultOn" in names
        assert "DefaultOff" not in names


# ---------------------------------------------------------------------------
# list_items enabled filter
# ---------------------------------------------------------------------------


class TestListItemsEnabledFilter:
    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        service.create_item(name="EnabledItem")
        item_off = service.create_item(name="DisabledItem")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items(enabled=True)
        names = {i.name for i in result}
        assert "EnabledItem" in names
        assert "DisabledItem" not in names

    def test_enabled_false_returns_only_disabled(self, service: TaxomeshService) -> None:
        service.create_item(name="ActiveItem")
        item_off = service.create_item(name="InactiveItem")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items(enabled=False)
        names = {i.name for i in result}
        assert "InactiveItem" in names
        assert "ActiveItem" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.create_item(name="ItemX")
        item_off = service.create_item(name="ItemY")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items(enabled=None)
        names = {i.name for i in result}
        assert "ItemX" in names
        assert "ItemY" in names

    def test_enabled_true_is_default(self, service: TaxomeshService) -> None:
        service.create_item(name="DefaultActiveItem")
        item_off = service.create_item(name="DefaultInactiveItem")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items()
        names = {i.name for i in result}
        assert "DefaultActiveItem" in names
        assert "DefaultInactiveItem" not in names


# ---------------------------------------------------------------------------
# list_categories_by_item enabled filter
# ---------------------------------------------------------------------------


class TestListCategoriesByItemEnabledFilter:
    def test_enabled_none_returns_all_categories(self, service: TaxomeshService) -> None:
        cat_on = service.create_category(name="OnCat")
        cat_off = service.create_category(name="OffCat")
        service.update_category(cat_off.category_id, enabled=False)

        item = service.create_item(name="MyItem")
        service.place_item_in_category(item.item_id, cat_on.category_id)
        service.place_item_in_category(item.item_id, cat_off.category_id)

        result = service.list_categories_by_item(item.item_id, enabled=None)
        names = {c.name for c in result}
        assert "OnCat" in names
        assert "OffCat" in names

    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        cat_on = service.create_category(name="CatVisible")
        cat_off = service.create_category(name="CatHidden")
        service.update_category(cat_off.category_id, enabled=False)

        item = service.create_item(name="AnItem")
        service.place_item_in_category(item.item_id, cat_on.category_id)
        service.place_item_in_category(item.item_id, cat_off.category_id)

        result = service.list_categories_by_item(item.item_id, enabled=True)
        names = {c.name for c in result}
        assert "CatVisible" in names
        assert "CatHidden" not in names


# ---------------------------------------------------------------------------
# search_items enabled filter
# ---------------------------------------------------------------------------


class TestSearchItemsEnabledFilter:
    def test_search_items_enabled_true_excludes_disabled(self, service: TaxomeshService) -> None:
        service.create_item(name="Visible Widget")
        item_off = service.create_item(name="Hidden Widget")
        service.update_item(item_off.item_id, enabled=False)

        result = service.search_items("Widget", enabled=True)
        names = {i.name for i in result}
        assert "Visible Widget" in names
        assert "Hidden Widget" not in names

    def test_search_items_enabled_false_includes_disabled(self, service: TaxomeshService) -> None:
        service.create_item(name="Open Gadget")
        item_off = service.create_item(name="Closed Gadget")
        service.update_item(item_off.item_id, enabled=False)

        result = service.search_items("Gadget", enabled=False)
        names = {i.name for i in result}
        assert "Closed Gadget" in names
        assert "Open Gadget" not in names


# ---------------------------------------------------------------------------
# search_categories enabled filter
# ---------------------------------------------------------------------------


class TestSearchCategoriesEnabledFilter:
    def test_search_categories_enabled_true_excludes_disabled(self, service: TaxomeshService) -> None:
        service.create_category(name="PublicSection")
        cat_off = service.create_category(name="PrivateSection")
        service.update_category(cat_off.category_id, enabled=False)

        result = service.search_categories("Section", enabled=True)
        names = {c.name for c in result}
        assert "PublicSection" in names
        assert "PrivateSection" not in names


# ---------------------------------------------------------------------------
# get_graph enabled filter (T019)
# ---------------------------------------------------------------------------


class TestGetGraphEnabledFilter:
    def test_default_excludes_disabled_category(self, service: TaxomeshService) -> None:
        service.create_category(name="VisibleCat")
        hidden = service.create_category(name="HiddenCat")
        service.update_category(hidden.category_id, enabled=False)

        graph = service.get_graph()
        names = {n.category.name for n in graph.roots}
        assert "VisibleCat" in names
        assert "HiddenCat" not in names

    def test_default_excludes_disabled_items(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="SomeCat")
        service.create_item(name="ActiveItem")
        inactive = service.create_item(name="InactiveItem")
        service.update_item(inactive.item_id, enabled=False)
        service.place_item_in_category(inactive.item_id, cat.category_id)

        graph = service.get_graph()
        all_items = [item for node in graph.roots for item in node.items]
        names = {i.name for i in all_items}
        assert "InactiveItem" not in names

    def test_enabled_none_includes_disabled_category(self, service: TaxomeshService) -> None:
        service.create_category(name="ActiveCat")
        hidden = service.create_category(name="DisabledCat")
        service.update_category(hidden.category_id, enabled=False)

        graph = service.get_graph(enabled=None)
        names = {n.category.name for n in graph.roots}
        assert "ActiveCat" in names
        assert "DisabledCat" in names

    def test_enabled_none_includes_disabled_items(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="SomeCat")
        inactive = service.create_item(name="SleepingItem")
        service.update_item(inactive.item_id, enabled=False)
        service.place_item_in_category(inactive.item_id, cat.category_id)

        graph = service.get_graph(enabled=None)
        all_items = [item for node in graph.roots for item in node.items]
        names = {i.name for i in all_items}
        assert "SleepingItem" in names


# ---------------------------------------------------------------------------
# Backward compatibility: enabled_only kwarg must raise TypeError (T018)
# ---------------------------------------------------------------------------


class TestEnabledOnlyRemovedKwarg:
    def test_search_items_rejects_enabled_only_kwarg(self, service: TaxomeshService) -> None:
        with pytest.raises(TypeError):
            service.search_items("query", enabled_only=True)  # type: ignore[call-arg]

    def test_search_categories_rejects_enabled_only_kwarg(self, service: TaxomeshService) -> None:
        with pytest.raises(TypeError):
            service.search_categories("query", enabled_only=True)  # type: ignore[call-arg]
