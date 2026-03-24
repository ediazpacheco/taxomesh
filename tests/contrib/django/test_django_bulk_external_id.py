"""Tests for DjangoRepository bulk external-id lookup methods (spec 052)."""

from unittest.mock import patch

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402
from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture
def repo() -> DjangoRepository:
    return DjangoRepository()


# ---------------------------------------------------------------------------
# get_items_by_external_ids (US2)
# ---------------------------------------------------------------------------


def test_items_bulk_lookup_found(repo: DjangoRepository) -> None:
    item_a = Item(external_id="django-bulk-a")
    item_b = Item(external_id="django-bulk-b")
    repo.save_item(item_a)
    repo.save_item(item_b)
    result = repo.get_items_by_external_ids(["django-bulk-a", "django-bulk-b"])
    assert set(result.keys()) == {"django-bulk-a", "django-bulk-b"}
    assert result["django-bulk-a"].item_id == item_a.item_id
    assert result["django-bulk-b"].item_id == item_b.item_id


def test_items_bulk_lookup_missing(repo: DjangoRepository) -> None:
    result = repo.get_items_by_external_ids(["no-such-django-item"])
    assert result == {}


def test_items_bulk_lookup_empty_input(repo: DjangoRepository) -> None:
    result = repo.get_items_by_external_ids([])
    assert result == {}


def test_items_enabled_true(repo: DjangoRepository) -> None:
    enabled_item = Item(external_id="django-enabled-item", enabled=True)
    disabled_item = Item(external_id="django-disabled-item", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["django-enabled-item", "django-disabled-item"], enabled=True)
    assert set(result.keys()) == {"django-enabled-item"}


def test_items_enabled_false(repo: DjangoRepository) -> None:
    enabled_item = Item(external_id="django-enabled-item2", enabled=True)
    disabled_item = Item(external_id="django-disabled-item2", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["django-enabled-item2", "django-disabled-item2"], enabled=False)
    assert set(result.keys()) == {"django-disabled-item2"}


def test_items_enabled_none(repo: DjangoRepository) -> None:
    enabled_item = Item(external_id="django-enabled-item3", enabled=True)
    disabled_item = Item(external_id="django-disabled-item3", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["django-enabled-item3", "django-disabled-item3"], enabled=None)
    assert set(result.keys()) == {"django-enabled-item3", "django-disabled-item3"}


def test_items_database_error_raises_repository_error(repo: DjangoRepository) -> None:
    from django.db import DatabaseError  # noqa: PLC0415

    with patch.object(  # noqa: SIM117
        repo._ItemModel.objects, "using", side_effect=DatabaseError("db down")
    ):
        with pytest.raises(TaxomeshRepositoryError):
            repo.get_items_by_external_ids(["some-id"])


# ---------------------------------------------------------------------------
# get_categories_by_external_ids (US3)
# ---------------------------------------------------------------------------


def test_categories_bulk_lookup_found(repo: DjangoRepository) -> None:
    cat_a = Category(name="DjBulkA", external_id="dj-cat-a")
    cat_b = Category(name="DjBulkB", external_id="dj-cat-b")
    repo.save_category(cat_a)
    repo.save_category(cat_b)
    result = repo.get_categories_by_external_ids(["dj-cat-a", "dj-cat-b"])
    assert set(result.keys()) == {"dj-cat-a", "dj-cat-b"}
    assert result["dj-cat-a"].category_id == cat_a.category_id
    assert result["dj-cat-b"].category_id == cat_b.category_id


def test_categories_bulk_lookup_missing(repo: DjangoRepository) -> None:
    result = repo.get_categories_by_external_ids(["no-such-dj-cat"])
    assert result == {}


def test_categories_enabled_true(repo: DjangoRepository) -> None:
    enabled_cat = Category(name="DjEnabled", external_id="dj-cat-enabled", enabled=True)
    disabled_cat = Category(name="DjDisabled", external_id="dj-cat-disabled", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["dj-cat-enabled", "dj-cat-disabled"], enabled=True)
    assert set(result.keys()) == {"dj-cat-enabled"}


def test_categories_enabled_false(repo: DjangoRepository) -> None:
    enabled_cat = Category(name="DjEnabled2", external_id="dj-cat-enabled2", enabled=True)
    disabled_cat = Category(name="DjDisabled2", external_id="dj-cat-disabled2", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["dj-cat-enabled2", "dj-cat-disabled2"], enabled=False)
    assert set(result.keys()) == {"dj-cat-disabled2"}


def test_categories_enabled_none(repo: DjangoRepository) -> None:
    enabled_cat = Category(name="DjEnabled3", external_id="dj-cat-enabled3", enabled=True)
    disabled_cat = Category(name="DjDisabled3", external_id="dj-cat-disabled3", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["dj-cat-enabled3", "dj-cat-disabled3"], enabled=None)
    assert set(result.keys()) == {"dj-cat-enabled3", "dj-cat-disabled3"}


def test_categories_database_error_raises_repository_error(repo: DjangoRepository) -> None:
    from django.db import DatabaseError  # noqa: PLC0415

    with patch.object(  # noqa: SIM117
        repo._CategoryModel.objects, "using", side_effect=DatabaseError("db down")
    ):
        with pytest.raises(TaxomeshRepositoryError):
            repo.get_categories_by_external_ids(["some-cat-id"])
