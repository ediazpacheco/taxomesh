"""An update may be conditional on the version the caller read, on all four backends.

``categories.update`` and ``items.update`` take ``expected_version``. When it is given and the
stored row is at another version, the update raises ``TaxomeshVersionConflictError`` and stores
nothing; ``None`` makes no comparison. Storage makes the comparison in the same step as the
write, so two writers holding one version cannot both succeed.
``tests/contrib/django/test_django_version_check.py`` shows that step on Django.
"""

from uuid import uuid4

import pytest

from taxomesh import TaxomeshVersionConflictError
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item
from taxomesh.exceptions import TaxomeshError, TaxomeshNotFoundError, TaxomeshValidationError


class TestACategoryUpdate:
    """``categories.update(…, expected_version=…)``."""

    def test_a_matching_version_updates(self, service: TaxomeshService) -> None:
        created = service.categories.create("Tango")
        updated = service.categories.update(created.category_id, name="Milonga", expected_version=0)
        assert (updated.name, updated.version) == ("Milonga", 1)
        again = service.categories.update(created.category_id, name="Vals", expected_version=updated.version)
        assert (again.name, again.version) == ("Vals", 2)

    def test_a_stale_version_raises_and_changes_nothing(self, service: TaxomeshService) -> None:
        created = service.categories.create("Tango")
        service.categories.update(created.category_id, name="Milonga")
        with pytest.raises(TaxomeshVersionConflictError):
            service.categories.update(created.category_id, name="Vals", expected_version=created.version)
        stored = service.categories[created.category_id]
        assert (stored.name, stored.version) == ("Milonga", 1)
        service.categories.create("Unrelated")
        stored = service.categories[created.category_id]
        assert (stored.name, stored.version) == ("Milonga", 1)

    def test_none_makes_no_comparison(self, service: TaxomeshService) -> None:
        created = service.categories.create("Tango")
        service.categories.update(created.category_id, name="Milonga")
        updated = service.categories.update(created.category_id, name="Vals", expected_version=None)
        assert (updated.name, updated.version) == ("Vals", 2)

    def test_two_writers_holding_one_version_cannot_both_succeed(self, service: TaxomeshService) -> None:
        created = service.categories.create("Tango")
        service.categories.update(created.category_id, name="Milonga", expected_version=created.version)
        with pytest.raises(TaxomeshVersionConflictError):
            service.categories.update(created.category_id, name="Vals", expected_version=created.version)
        assert service.categories[created.category_id].name == "Milonga"


class TestAnItemUpdate:
    """``items.update(…, expected_version=…)``."""

    def test_a_matching_version_updates(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        updated = service.items.update(created.item_id, name="Mina", expected_version=0)
        assert (updated.name, updated.version) == ("Mina", 1)

    def test_a_stale_version_raises_and_changes_nothing(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        service.items.update(created.item_id, name="Mina")
        with pytest.raises(TaxomeshVersionConflictError):
            service.items.update(created.item_id, enabled=False, expected_version=created.version)
        stored = service.items[created.item_id]
        assert (stored.name, stored.enabled, stored.version) == ("Mina", True, 1)
        service.items.create("Unrelated")
        stored = service.items[created.item_id]
        assert (stored.name, stored.enabled, stored.version) == ("Mina", True, 1)

    def test_none_makes_no_comparison(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        service.items.update(created.item_id, name="Mina")
        updated = service.items.update(created.item_id, name="Paica", expected_version=None)
        assert (updated.name, updated.version) == ("Paica", 2)

    def test_two_writers_holding_one_version_cannot_both_succeed(self, service: TaxomeshService) -> None:
        created = service.items.create("Percanta")
        service.items.update(created.item_id, name="Mina", expected_version=created.version)
        with pytest.raises(TaxomeshVersionConflictError):
            service.items.update(created.item_id, name="Paica", expected_version=created.version)
        assert service.items[created.item_id].name == "Mina"


class TestTheSave:
    """The repository makes the comparison itself, so a stale read above it cannot slip through."""

    def test_a_category_save_with_a_stale_version_raises_and_stores_nothing(self, service: TaxomeshService) -> None:
        row = Category(category_id=uuid4(), name="Tango")
        service.repository.save_category(row)
        service.repository.save_category(row.model_copy(update={"name": "Milonga"}), expected_version=0)
        with pytest.raises(TaxomeshVersionConflictError):
            service.repository.save_category(row.model_copy(update={"name": "Vals"}), expected_version=0)
        stored = service.repository.find_category(row.category_id)
        assert stored is not None
        assert (stored.name, stored.version) == ("Milonga", 1)

    def test_an_item_save_with_a_stale_version_raises_and_stores_nothing(self, service: TaxomeshService) -> None:
        row = Item(item_id=uuid4(), name="Percanta")
        service.repository.save_item(row)
        service.repository.save_item(row.model_copy(update={"name": "Mina"}), expected_version=0)
        with pytest.raises(TaxomeshVersionConflictError):
            service.repository.save_item(row.model_copy(update={"name": "Paica"}), expected_version=0)
        stored = service.repository.find_item(row.item_id)
        assert stored is not None
        assert (stored.name, stored.version) == ("Mina", 1)

    def test_an_expected_version_for_a_row_not_stored_is_a_conflict(self, service: TaxomeshService) -> None:
        """No stored row is at the expected version, so nothing is inserted."""
        category = Category(category_id=uuid4(), name="Tango")
        item = Item(item_id=uuid4(), name="Percanta")
        with pytest.raises(TaxomeshVersionConflictError):
            service.repository.save_category(category, expected_version=0)
        with pytest.raises(TaxomeshVersionConflictError):
            service.repository.save_item(item, expected_version=0)
        assert service.repository.find_category(category.category_id) is None
        assert service.repository.find_item(item.item_id) is None


class TestTheNumber:
    """A version is a whole number from 0: a negative one is refused, and ``True`` is 1."""

    def test_a_negative_version_is_refused_and_stores_nothing(self, service: TaxomeshService) -> None:
        category = service.categories.create("Tango")
        item = service.items.create("Percanta")

        with pytest.raises(TaxomeshValidationError, match="^expected_version "):
            service.categories.update(category, name="Milonga", expected_version=-1)
        with pytest.raises(TaxomeshValidationError, match="^expected_version "):
            service.items.update(item, name="Mina", expected_version=-1)

        assert (service.repository.find_category(category.category_id) or category).name == "Tango"
        assert (service.repository.find_item(item.item_id) or item).name == "Percanta"

    def test_true_is_version_one(self, service: TaxomeshService) -> None:
        category = service.categories.update(service.categories.create("Tango"), name="Milonga")
        item = service.items.update(service.items.create("Percanta"), name="Mina")

        assert service.categories.update(category, name="Vals", expected_version=True).version == 2
        assert service.items.update(item, name="Flor", expected_version=True).version == 2


class TestTheError:
    """A conflict is its own kind of failure: the request was valid, and the stored row moved."""

    def test_it_is_a_taxomesh_error_and_neither_a_validation_nor_a_not_found_error(self) -> None:
        assert issubclass(TaxomeshVersionConflictError, TaxomeshError)
        assert not issubclass(TaxomeshVersionConflictError, TaxomeshValidationError)
        assert not issubclass(TaxomeshVersionConflictError, TaxomeshNotFoundError)
        assert not issubclass(TaxomeshVersionConflictError, ValueError)
        assert not issubclass(TaxomeshVersionConflictError, KeyError)
