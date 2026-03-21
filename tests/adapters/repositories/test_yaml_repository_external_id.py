"""Tests for YAMLRepository external_id methods (spec 041)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML is not installed")

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402
from taxomesh.exceptions import TaxomeshExternalIdConflictError  # noqa: E402


@pytest.fixture
def repo(tmp_path: Path) -> YAMLRepository:
    return YAMLRepository(tmp_path / "test.yaml")


# ---------------------------------------------------------------------------
# get_item_by_external_id — found/not-found
# ---------------------------------------------------------------------------


def test_get_item_by_external_id_found(repo: YAMLRepository) -> None:
    item = Item(external_id="yaml-ext")
    repo.save_item(item)
    result = repo.get_item_by_external_id("yaml-ext")
    assert result is not None
    assert result.item_id == item.item_id


def test_get_item_by_external_id_not_found(repo: YAMLRepository) -> None:
    result = repo.get_item_by_external_id("no-such-id")
    assert result is None


# ---------------------------------------------------------------------------
# get_category_by_external_id — found/not-found
# ---------------------------------------------------------------------------


def test_get_category_by_external_id_found(repo: YAMLRepository) -> None:
    cat = Category(name="Test", external_id="yaml-cat-ext")
    repo.save_category(cat)
    result = repo.get_category_by_external_id("yaml-cat-ext")
    assert result is not None
    assert result.category_id == cat.category_id


def test_get_category_by_external_id_not_found(repo: YAMLRepository) -> None:
    result = repo.get_category_by_external_id("no-such-cat")
    assert result is None


# ---------------------------------------------------------------------------
# save_item — uniqueness enforcement
# ---------------------------------------------------------------------------


def test_save_item_duplicate_external_id_raises(repo: YAMLRepository) -> None:
    item_a = Item(external_id="yaml-dup-ext")
    repo.save_item(item_a)
    item_b = Item(external_id="yaml-dup-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_item(item_b)


def test_save_item_resave_same_item_does_not_raise(repo: YAMLRepository) -> None:
    item = Item(external_id="yaml-resave-ext")
    repo.save_item(item)
    item.name = "Updated"
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_item_none_external_id_does_not_conflict(repo: YAMLRepository) -> None:
    item_a = Item(external_id=None)
    item_b = Item(external_id=None)
    repo.save_item(item_a)
    repo.save_item(item_b)
    assert repo.get_item(item_a.item_id) is not None
    assert repo.get_item(item_b.item_id) is not None


# ---------------------------------------------------------------------------
# save_category — uniqueness enforcement
# ---------------------------------------------------------------------------


def test_save_category_duplicate_external_id_raises(repo: YAMLRepository) -> None:
    cat_a = Category(name="A", external_id="yaml-dup-cat-ext")
    repo.save_category(cat_a)
    cat_b = Category(name="B", external_id="yaml-dup-cat-ext")
    with pytest.raises(TaxomeshExternalIdConflictError):
        repo.save_category(cat_b)


def test_save_category_resave_same_category_does_not_raise(repo: YAMLRepository) -> None:
    cat = Category(name="Original", external_id="yaml-resave-cat-ext")
    repo.save_category(cat)
    cat.name = "Updated"
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.name == "Updated"


def test_save_category_none_external_id_does_not_conflict(repo: YAMLRepository) -> None:
    cat_a = Category(name="A", external_id=None)
    cat_b = Category(name="B", external_id=None)
    repo.save_category(cat_a)
    repo.save_category(cat_b)
    assert repo.get_category(cat_a.category_id) is not None
    assert repo.get_category(cat_b.category_id) is not None


# ---------------------------------------------------------------------------
# None round-trip (US4)
# ---------------------------------------------------------------------------


def test_item_none_external_id_round_trip(repo: YAMLRepository) -> None:
    item = Item(external_id=None)
    repo.save_item(item)
    result = repo.get_item(item.item_id)
    assert result is not None
    assert result.external_id is None


def test_category_none_external_id_round_trip(repo: YAMLRepository) -> None:
    cat = Category(name="Test", external_id=None)
    repo.save_category(cat)
    result = repo.get_category(cat.category_id)
    assert result is not None
    assert result.external_id is None
