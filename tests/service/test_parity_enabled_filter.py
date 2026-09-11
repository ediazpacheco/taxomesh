"""Cross-backend parity tests for enabled filter on list_categories / list_items (spec 046).

These tests run against all backends via the shared 'service' fixture to verify
consistent filtering semantics.

Written before implementation (TDD-first).
"""

from uuid import UUID

from taxomesh.application.service import TaxomeshService
from taxomesh.utils.memoize import clear_all_caches


class TestParityListCategoriesEnabled:
    def test_enabled_true_returns_only_enabled_across_backends(self, service: TaxomeshService) -> None:
        service.create_category(name="ParityEnabled")
        cat_off = service.create_category(name="ParityDisabled")
        cat_off_obj = service.repository.get_category(cat_off.category_id)
        assert cat_off_obj is not None
        cat_off_obj.enabled = False
        service.repository.save_category(cat_off_obj)
        clear_all_caches()

        result = service.list_categories(enabled=True)
        names = {c.name for c in result}
        assert "ParityEnabled" in names
        assert "ParityDisabled" not in names

    def test_enabled_none_returns_both_across_backends(self, service: TaxomeshService) -> None:
        service.create_category(name="ParityAll1")
        cat_off = service.create_category(name="ParityAll2")
        cat_off_obj = service.repository.get_category(cat_off.category_id)
        assert cat_off_obj is not None
        cat_off_obj.enabled = False
        service.repository.save_category(cat_off_obj)
        clear_all_caches()

        result = service.list_categories(enabled=None)
        names = {c.name for c in result}
        assert "ParityAll1" in names
        assert "ParityAll2" in names


class TestParityListItemsEnabled:
    def test_enabled_true_returns_only_enabled_across_backends(self, service: TaxomeshService) -> None:
        service.create_item(name="ParityItemEnabled")
        item_off = service.create_item(name="ParityItemDisabled")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items(enabled=True)
        names = {i.name for i in result}
        assert "ParityItemEnabled" in names
        assert "ParityItemDisabled" not in names

    def test_enabled_none_returns_both_across_backends(self, service: TaxomeshService) -> None:
        service.create_item(name="ParityAllItem1")
        item_off = service.create_item(name="ParityAllItem2")
        service.update_item(item_off.item_id, enabled=False)

        result = service.list_items(enabled=None)
        names = {i.name for i in result}
        assert "ParityAllItem1" in names
        assert "ParityAllItem2" in names


class TestParityListItemsByCategoryEnabled:
    """Spec 060: the enabled filter must behave identically once resolution is batched.

    The batch resolve is deliberately requested UNFILTERED and the enabled filter
    applied afterwards (FR-011). Pushing the filter into the resolve would make a
    disabled endpoint absent from the returned map — indistinguishable from a
    deleted one, which FR-012 turns into a raise. These tests are what catches
    that mistake.
    """

    @staticmethod
    def _category_with_one_enabled_and_one_disabled(service: TaxomeshService) -> tuple[str, str, UUID]:
        category = service.create_category(name="PlacementEnabledParity")
        live = service.create_item(name="PlacementLive")
        dark = service.create_item(name="PlacementDark")
        service.place_item_in_category(live.item_id, category.category_id, sort_index=0)
        service.place_item_in_category(dark.item_id, category.category_id, sort_index=1)
        service.update_item(dark.item_id, enabled=False)
        clear_all_caches()
        return "PlacementLive", "PlacementDark", category.category_id

    def test_enabled_true_excludes_the_disabled_placement(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.list_items(category_id=category_id)}

        assert live in names
        assert dark not in names

    def test_enabled_false_returns_only_the_disabled_placement(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.list_items(category_id=category_id, enabled=False)}

        assert names == {dark}

    def test_enabled_none_returns_both(self, service: TaxomeshService) -> None:
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        names = {item.name for item in service.list_items(category_id=category_id, enabled=None)}

        assert names == {live, dark}

    def test_disabled_placement_is_filtered_not_treated_as_missing(self, service: TaxomeshService) -> None:
        """A disabled endpoint must never raise — that is what pushing the filter down would cause."""
        live, dark, category_id = self._category_with_one_enabled_and_one_disabled(service)

        result = service.list_items(category_id=category_id)

        assert [item.name for item in result] == [live]


class TestParityListCategoriesByParentEnabled:
    """Spec 060: the enabled filter on the children path, once resolution is batched."""

    def test_disabled_child_is_filtered_not_missing(self, service: TaxomeshService) -> None:
        parent = service.create_category(name="ParentEnabledParity")
        live = service.create_category(name="ChildLive")
        dark = service.create_category(name="ChildDark")
        service.add_category_parent(live.category_id, parent.category_id, sort_index=0)
        service.add_category_parent(dark.category_id, parent.category_id, sort_index=1)
        dark_row = service.repository.get_category(dark.category_id)
        assert dark_row is not None
        dark_row.enabled = False
        service.repository.save_category(dark_row)
        clear_all_caches()

        result = service.list_categories(parent_id=parent.category_id)

        assert [c.name for c in result] == ["ChildLive"]
