"""Cross-backend parity tests for enabled filter on list_categories / list_items (spec 046).

These tests run against all backends via the shared 'service' fixture to verify
consistent filtering semantics.

Written before implementation (TDD-first).
"""

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
