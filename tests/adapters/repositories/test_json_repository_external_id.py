"""Tests for JsonRepository external_id methods (spec 041)."""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, Item
from taxomesh.exceptions import TaxomeshExternalIdConflictError


@pytest.fixture
def repo(tmp_path: Path) -> JsonRepository:
    return JsonRepository(tmp_path / "test.json")


# ---------------------------------------------------------------------------
# get_item_by_external_id — found
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_found(repo: JsonRepository) -> None:
    item = Item(external_id="test-ext")
    repo.save_item(item)
    result = repo.get_item_by_external_id("test-ext")
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_uuid_coercion(repo: JsonRepository) -> None:
    uid = uuid4()
    item = Item(external_id=uid)  # type: ignore[arg-type]
    repo.save_item(item)
    result = repo.get_item_by_external_id(str(uid))
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_int_coercion(repo: JsonRepository) -> None:
    item = Item(external_id=99)  # type: ignore[arg-type]
    repo.save_item(item)
    result = repo.get_item_by_external_id("99")
    assert result is not None
    assert result.item_id == item.item_id


# ---------------------------------------------------------------------------
# get_item_by_external_id — not found
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_not_found(repo: JsonRepository) -> None:
    result = repo.get_item_by_external_id("no-such-id")
    assert result is None


def test_get_item_by_external_id_not_found_with_other_items(repo: JsonRepository) -> None:
    item = Item(external_id="other-id")
    repo.save_item(item)
    result = repo.get_item_by_external_id("missing-id")
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — found
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_found(repo: JsonRepository) -> None:
    cat = Category(name="Test", external_id="cat-ext")
    repo.save_category(cat)
    result = repo.get_category_by_external_id("cat-ext")
    assert result is not None
    assert result.category_id == cat.category_id


def test_get_category_by_external_id_not_found(repo: JsonRepository) -> None:
    result = repo.get_category_by_external_id("no-such-cat")
    assert result is None


# ---------------------------------------------------------------------------
# save_item — uniqueness enforcement
# ---------------------------------------------------------------------------


def test_save_item_duplicate_external_id_raises(repo: JsonRepository) -> None:
    item_a = Item(external_id="dup-ext")
    repo.save_item(item_a)
    item_b = Item(external_id="dup-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_item(item_b)


def test_save_item_resave_same_item_does_not_raise(repo: JsonRepository) -> None:
    item = Item(external_id="resave-ext")
    repo.save_item(item)
    item.name = "Updated"
    repo.save_item(item)  # Same item_id — must not raise
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_item_none_external_id_does_not_conflict(repo: JsonRepository) -> None:
    item_a = Item(external_id=None)
    item_b = Item(external_id=None)
    repo.save_item(item_a)
    repo.save_item(item_b)  # Both None — must not raise
    assert repo.get_item(item_a.item_id) is not None
    assert repo.get_item(item_b.item_id) is not None


# ---------------------------------------------------------------------------
# save_category — uniqueness enforcement
# ---------------------------------------------------------------------------


def test_save_category_duplicate_external_id_raises(repo: JsonRepository) -> None:
    cat_a = Category(name="A", external_id="dup-cat-ext")
    repo.save_category(cat_a)
    cat_b = Category(name="B", external_id="dup-cat-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_category(cat_b)


def test_save_category_resave_same_category_does_not_raise(repo: JsonRepository) -> None:
    cat = Category(name="Original", external_id="resave-cat-ext")
    repo.save_category(cat)
    cat.name = "Updated"
    repo.save_category(cat)  # Same category_id — must not raise
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_category_none_external_id_does_not_conflict(repo: JsonRepository) -> None:
    cat_a = Category(name="A", external_id=None)
    cat_b = Category(name="B", external_id=None)
    repo.save_category(cat_a)
    repo.save_category(cat_b)  # Both None — must not raise
    assert repo.get_category(cat_a.category_id) is not None
    assert repo.get_category(cat_b.category_id) is not None


# ---------------------------------------------------------------------------
# None round-trip (US4)
# ---------------------------------------------------------------------------


def test_item_none_external_id_round_trip(repo: JsonRepository) -> None:
    item = Item(external_id=None)
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.external_id is None


def test_category_none_external_id_round_trip(repo: JsonRepository) -> None:
    cat = Category(name="Test", external_id=None)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.external_id is None
