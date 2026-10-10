"""Tests for service-level enabled filter on categories.roots, items.list,
categories.list(item=…), items.search, and categories.search.
"""

from taxomesh.application.service import TaxomeshService

# ---------------------------------------------------------------------------
# categories.roots enabled filter
# ---------------------------------------------------------------------------


class TestCategoriesListEnabledFilter:
    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        service.categories.create(name="EnabledCat")
        cat_off = service.categories.create(name="DisabledCat")
        service.categories.update(cat_off.category_id, enabled=False)

        result = service.categories.roots(enabled=True)
        names = {c.name for c in result}
        assert "EnabledCat" in names
        assert "DisabledCat" not in names

    def test_enabled_false_returns_only_disabled(self, service: TaxomeshService) -> None:
        service.categories.create(name="ActiveCat")
        cat_off = service.categories.create(name="InactiveCat")
        service.categories.update(cat_off.category_id, enabled=False)

        result = service.categories.roots(enabled=False)
        names = {c.name for c in result}
        assert "InactiveCat" in names
        assert "ActiveCat" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.categories.create(name="CatA")
        cat_off = service.categories.create(name="CatB")
        service.categories.update(cat_off.category_id, enabled=False)

        result = service.categories.roots(enabled=None)
        names = {c.name for c in result}
        assert "CatA" in names
        assert "CatB" in names

    def test_enabled_true_is_default(self, service: TaxomeshService) -> None:
        service.categories.create(name="DefaultOn")
        cat_off = service.categories.create(name="DefaultOff")
        service.categories.update(cat_off.category_id, enabled=False)

        result = service.categories.roots()
        names = {c.name for c in result}
        assert "DefaultOn" in names
        assert "DefaultOff" not in names


# ---------------------------------------------------------------------------
# items.list enabled filter
# ---------------------------------------------------------------------------


class TestItemsListEnabledFilter:
    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        service.items.create(name="EnabledItem")
        item_off = service.items.create(name="DisabledItem")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list(enabled=True)
        names = {i.name for i in result}
        assert "EnabledItem" in names
        assert "DisabledItem" not in names

    def test_enabled_false_returns_only_disabled(self, service: TaxomeshService) -> None:
        service.items.create(name="ActiveItem")
        item_off = service.items.create(name="InactiveItem")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list(enabled=False)
        names = {i.name for i in result}
        assert "InactiveItem" in names
        assert "ActiveItem" not in names

    def test_enabled_none_returns_all(self, service: TaxomeshService) -> None:
        service.items.create(name="ItemX")
        item_off = service.items.create(name="ItemY")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list(enabled=None)
        names = {i.name for i in result}
        assert "ItemX" in names
        assert "ItemY" in names

    def test_enabled_true_is_default(self, service: TaxomeshService) -> None:
        service.items.create(name="DefaultActiveItem")
        item_off = service.items.create(name="DefaultInactiveItem")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list()
        names = {i.name for i in result}
        assert "DefaultActiveItem" in names
        assert "DefaultInactiveItem" not in names


# ---------------------------------------------------------------------------
# categories.list(item=…) enabled filter
# ---------------------------------------------------------------------------


class TestCategoriesListItemIdEnabledFilter:
    def test_enabled_none_returns_all_categories(self, service: TaxomeshService) -> None:
        cat_on = service.categories.create(name="OnCat")
        cat_off = service.categories.create(name="OffCat")
        service.categories.update(cat_off.category_id, enabled=False)

        item = service.items.create(name="MyItem")
        service.items.place_in(item.item_id, cat_on.category_id)
        service.items.place_in(item.item_id, cat_off.category_id)

        result = service.categories.list(item=item.item_id, enabled=None)
        names = {c.name for c in result}
        assert "OnCat" in names
        assert "OffCat" in names

    def test_enabled_true_returns_only_enabled(self, service: TaxomeshService) -> None:
        cat_on = service.categories.create(name="CatVisible")
        cat_off = service.categories.create(name="CatHidden")
        service.categories.update(cat_off.category_id, enabled=False)

        item = service.items.create(name="AnItem")
        service.items.place_in(item.item_id, cat_on.category_id)
        service.items.place_in(item.item_id, cat_off.category_id)

        result = service.categories.list(item=item.item_id, enabled=True)
        names = {c.name for c in result}
        assert "CatVisible" in names
        assert "CatHidden" not in names


# ---------------------------------------------------------------------------
# items.search enabled filter
# ---------------------------------------------------------------------------


class TestItemsSearchEnabledFilter:
    def test_items_search_enabled_true_excludes_disabled(self, service: TaxomeshService) -> None:
        service.items.create(name="Visible Widget")
        item_off = service.items.create(name="Hidden Widget")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.search("Widget", enabled=True)
        names = {i.name for i in result}
        assert "Visible Widget" in names
        assert "Hidden Widget" not in names

    def test_items_search_enabled_false_includes_disabled(self, service: TaxomeshService) -> None:
        service.items.create(name="Open Gadget")
        item_off = service.items.create(name="Closed Gadget")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.search("Gadget", enabled=False)
        names = {i.name for i in result}
        assert "Closed Gadget" in names
        assert "Open Gadget" not in names


# ---------------------------------------------------------------------------
# categories.search enabled filter
# ---------------------------------------------------------------------------


class TestCategoriesSearchEnabledFilter:
    def test_categories_search_enabled_true_excludes_disabled(self, service: TaxomeshService) -> None:
        service.categories.create(name="PublicSection")
        cat_off = service.categories.create(name="PrivateSection")
        service.categories.update(cat_off.category_id, enabled=False)

        result = service.categories.search("Section", enabled=True)
        names = {c.name for c in result}
        assert "PublicSection" in names
        assert "PrivateSection" not in names


# ---------------------------------------------------------------------------
# graph enabled filter
# ---------------------------------------------------------------------------


class TestGraphEnabledFilter:
    def test_default_excludes_disabled_category(self, service: TaxomeshService) -> None:
        service.categories.create(name="VisibleCat")
        hidden = service.categories.create(name="HiddenCat")
        service.categories.update(hidden.category_id, enabled=False)

        graph = service.graph()
        names = {n.category.name for n in graph.roots}
        assert "VisibleCat" in names
        assert "HiddenCat" not in names

    def test_default_excludes_disabled_items(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="SomeCat")
        service.items.create(name="ActiveItem")
        inactive = service.items.create(name="InactiveItem")
        service.items.update(inactive.item_id, enabled=False)
        service.items.place_in(inactive.item_id, cat.category_id)

        graph = service.graph()
        all_items = [item for node in graph.roots for item in node.items]
        names = {i.name for i in all_items}
        assert "InactiveItem" not in names

    def test_enabled_none_includes_disabled_category(self, service: TaxomeshService) -> None:
        service.categories.create(name="ActiveCat")
        hidden = service.categories.create(name="DisabledCat")
        service.categories.update(hidden.category_id, enabled=False)

        graph = service.graph(enabled=None)
        names = {n.category.name for n in graph.roots}
        assert "ActiveCat" in names
        assert "DisabledCat" in names

    def test_enabled_none_includes_disabled_items(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="SomeCat")
        inactive = service.items.create(name="SleepingItem")
        service.items.update(inactive.item_id, enabled=False)
        service.items.place_in(inactive.item_id, cat.category_id)

        graph = service.graph(enabled=None)
        all_items = [item for node in graph.roots for item in node.items]
        names = {i.name for i in all_items}
        assert "SleepingItem" in names
