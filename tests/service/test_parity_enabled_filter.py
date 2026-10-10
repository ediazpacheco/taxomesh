"""Cross-backend parity tests for enabled filter on categories.roots / items.list.

These tests run against all backends via the shared 'service' fixture to verify
consistent filtering semantics.
"""

from uuid import UUID

from taxomesh.application.service import TaxomeshService


class TestParityCategoriesListEnabled:
    def test_enabled_true_returns_only_enabled_across_backends(self, service: TaxomeshService) -> None:
        service.categories.create(name="ParityEnabled")
        cat_off = service.categories.create(name="ParityDisabled")
        cat_off_obj = service.repository.find_category(cat_off.category_id)
        assert cat_off_obj is not None
        service.repository.save_category(cat_off_obj.model_copy(update={"enabled": False}))
        service._cache.clear()

        result = service.categories.roots(enabled=True)
        names = {c.name for c in result}
        assert "ParityEnabled" in names
        assert "ParityDisabled" not in names

    def test_enabled_none_returns_both_across_backends(self, service: TaxomeshService) -> None:
        service.categories.create(name="ParityAll1")
        cat_off = service.categories.create(name="ParityAll2")
        cat_off_obj = service.repository.find_category(cat_off.category_id)
        assert cat_off_obj is not None
        service.repository.save_category(cat_off_obj.model_copy(update={"enabled": False}))
        service._cache.clear()

        result = service.categories.roots(enabled=None)
        names = {c.name for c in result}
        assert "ParityAll1" in names
        assert "ParityAll2" in names


class TestParityItemsListEnabled:
    def test_enabled_true_returns_only_enabled_across_backends(self, service: TaxomeshService) -> None:
        service.items.create(name="ParityItemEnabled")
        item_off = service.items.create(name="ParityItemDisabled")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list(enabled=True)
        names = {i.name for i in result}
        assert "ParityItemEnabled" in names
        assert "ParityItemDisabled" not in names

    def test_enabled_none_returns_both_across_backends(self, service: TaxomeshService) -> None:
        service.items.create(name="ParityAllItem1")
        item_off = service.items.create(name="ParityAllItem2")
        service.items.update(item_off.item_id, enabled=False)

        result = service.items.list(enabled=None)
        names = {i.name for i in result}
        assert "ParityAllItem1" in names
        assert "ParityAllItem2" in names


class TestParityItemsListByCategoryEnabled:
    """The enabled filter must behave identically once resolution is batched.

    The batch resolve is deliberately requested UNFILTERED and the enabled filter
    applied afterwards. Pushing the filter into the resolve would make a
    disabled endpoint absent from the returned map — indistinguishable from a
    deleted one, which raises. These tests are what catches
    that mistake.
    """

    @staticmethod
    def _category_with_one_enabled_and_one_disabled(service: TaxomeshService) -> tuple[str, str, UUID]:
        category = service.categories.create(name="PlacementEnabledParity")
        live = service.items.create(name="PlacementLive")
        dark = service.items.create(name="PlacementDark")
        service.items.place_in(live.item_id, category.category_id, sort_index=0)
        service.items.place_in(dark.item_id, category.category_id, sort_index=1)
        service.items.update(dark.item_id, enabled=False)
        service._cache.clear()
        return "PlacementLive", "PlacementDark", category.category_id

    def test_enabled_true_excludes_the_disabled_placement(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.items.list(category=category_id)}

        assert live in names
        assert dark not in names

    def test_enabled_false_returns_only_the_disabled_placement(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.items.list(category=category_id, enabled=False)}

        assert names == {dark}

    def test_enabled_none_returns_both(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.items.list(category=category_id, enabled=None)}

        assert names == {live, dark}

    def test_disabled_placement_is_filtered_not_treated_as_missing(self, service: TaxomeshService) -> None:
        """A disabled endpoint must never raise — that is what pushing the filter down would cause."""
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        result = service.items.list(category=category_id)

        assert [item.name for item in result] == [live]


class TestParityCategoriesListByParentEnabled:
    """The enabled filter on the children path, once resolution is batched."""

    def test_disabled_child_is_filtered_not_missing(self, service: TaxomeshService) -> None:
        parent = service.categories.create(name="ParentEnabledParity")
        live = service.categories.create(name="ChildLive")
        dark = service.categories.create(name="ChildDark")
        service.categories.add_parent(live.category_id, parent.category_id, sort_index=0)
        service.categories.add_parent(dark.category_id, parent.category_id, sort_index=1)
        dark_row = service.repository.find_category(dark.category_id)
        assert dark_row is not None
        service.repository.save_category(dark_row.model_copy(update={"enabled": False}))
        service._cache.clear()

        result = service.categories.list(parent=parent.category_id)

        assert [c.name for c in result] == ["ChildLive"]
