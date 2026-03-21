"""Tests for DjangoRepository external_id uniqueness and lookup (spec 041)."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402
from taxomesh.exceptions import TaxomeshExternalIdConflictError  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture
def repo() -> DjangoRepository:
    return DjangoRepository()


# ---------------------------------------------------------------------------
# get_item_by_external_id — found/not-found
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_found(repo: DjangoRepository) -> None:
    item = Item(external_id="django-ext")
    repo.save_item(item)
    result = repo.get_item_by_external_id("django-ext")
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_not_found(repo: DjangoRepository) -> None:
    result = repo.get_item_by_external_id("no-such-id")
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — found/not-found
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_found(repo: DjangoRepository) -> None:
    cat = Category(name="Test", external_id="django-cat-ext")
    repo.save_category(cat)
    result = repo.get_category_by_external_id("django-cat-ext")
    assert result is not None
    assert result.category_id == cat.category_id


def test_get_category_by_external_id_not_found(repo: DjangoRepository) -> None:
    result = repo.get_category_by_external_id("no-such-cat")
    assert result is None


# ---------------------------------------------------------------------------
# save_item — uniqueness enforcement (IntegrityError → TaxomeshExternalIdConflictError)
# ---------------------------------------------------------------------------


def test_save_item_duplicate_external_id_raises(repo: DjangoRepository) -> None:
    item_a = Item(external_id="dj-dup-ext")
    repo.save_item(item_a)
    item_b = Item(external_id="dj-dup-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_item(item_b)


def test_save_item_resave_same_item_does_not_raise(repo: DjangoRepository) -> None:
    item = Item(external_id="dj-resave-ext")
    repo.save_item(item)
    item.name = "Updated"
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_item_none_external_id_does_not_conflict(repo: DjangoRepository) -> None:
    """Multiple NULL external_ids must not trigger unique constraint violation."""
    for _ in range(3):
        item = Item(external_id=None)
        repo.save_item(item)
    count = repo._ItemModel.objects.filter(external_id__isnull=True).count()
    assert count >= 3


# ---------------------------------------------------------------------------
# save_category — uniqueness enforcement
# ---------------------------------------------------------------------------


def test_save_category_duplicate_external_id_raises(repo: DjangoRepository) -> None:
    cat_a = Category(name="A", external_id="dj-dup-cat-ext")
    repo.save_category(cat_a)
    cat_b = Category(name="B", external_id="dj-dup-cat-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_category(cat_b)


def test_save_category_resave_same_category_does_not_raise(repo: DjangoRepository) -> None:
    cat = Category(name="Original", external_id="dj-resave-cat-ext")
    repo.save_category(cat)
    cat.name = "Updated"
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_category_none_external_id_does_not_conflict(repo: DjangoRepository) -> None:
    """Multiple NULL external_ids must not trigger unique constraint violation."""
    for _ in range(3):
        cat = Category(name="NullCat", external_id=None)
        repo.save_category(cat)
    count = repo._CategoryModel.objects.filter(external_id__isnull=True).count()
    assert count >= 3


# ---------------------------------------------------------------------------
# None round-trip (US4)
# ---------------------------------------------------------------------------


def test_item_none_external_id_round_trip(repo: DjangoRepository) -> None:
    item = Item(external_id=None)
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.external_id is None


def test_category_none_external_id_round_trip(repo: DjangoRepository) -> None:
    cat = Category(name="Test", external_id=None)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.external_id is None
