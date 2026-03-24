"""Tests for YAMLRepository bulk external-id lookup methods (spec 052)."""

from pathlib import Path

import pytest

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category, Item


@pytest.fixture
def repo(tmp_path: Path) -> YAMLRepository:
    return YAMLRepository(tmp_path / "test.yaml")


# ---------------------------------------------------------------------------
# get_items_by_external_ids — basic (US1)
# ---------------------------------------------------------------------------


def test_items_all_ids_found(repo: YAMLRepository) -> None:
    item_a = Item(external_id="ext-a")
    item_b = Item(external_id="ext-b")
    repo.save_item(item_a)
    repo.save_item(item_b)
    result = repo.get_items_by_external_ids(["ext-a", "ext-b"])
    assert set(result.keys()) == {"ext-a", "ext-b"}
    assert result["ext-a"].item_id == item_a.item_id
    assert result["ext-b"].item_id == item_b.item_id


def test_items_some_ids_missing(repo: YAMLRepository) -> None:
    item = Item(external_id="ext-a")
    repo.save_item(item)
    result = repo.get_items_by_external_ids(["ext-a", "ext-missing"])
    assert set(result.keys()) == {"ext-a"}
    assert result["ext-a"].item_id == item.item_id


def test_items_all_ids_missing(repo: YAMLRepository) -> None:
    result = repo.get_items_by_external_ids(["no-such", "also-missing"])
    assert result == {}


def test_items_duplicate_ids(repo: YAMLRepository) -> None:
    item = Item(external_id="ext-dup")
    repo.save_item(item)
    result = repo.get_items_by_external_ids(["ext-dup", "ext-dup"])
    assert set(result.keys()) == {"ext-dup"}
    assert result["ext-dup"].item_id == item.item_id


def test_items_blank_ids_ignored(repo: YAMLRepository) -> None:
    item = Item(external_id="ext-real")
    repo.save_item(item)
    result = repo.get_items_by_external_ids(["ext-real", "", "   "])
    assert "ext-real" in result
    assert "" not in result
    assert "   " not in result


def test_items_empty_input(repo: YAMLRepository) -> None:
    result = repo.get_items_by_external_ids([])
    assert result == {}


# ---------------------------------------------------------------------------
# get_items_by_external_ids — enabled filter (US2)
# ---------------------------------------------------------------------------


def test_items_enabled_true(repo: YAMLRepository) -> None:
    enabled_item = Item(external_id="ext-enabled", enabled=True)
    disabled_item = Item(external_id="ext-disabled", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["ext-enabled", "ext-disabled"], enabled=True)
    assert set(result.keys()) == {"ext-enabled"}


def test_items_enabled_false(repo: YAMLRepository) -> None:
    enabled_item = Item(external_id="ext-enabled", enabled=True)
    disabled_item = Item(external_id="ext-disabled", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["ext-enabled", "ext-disabled"], enabled=False)
    assert set(result.keys()) == {"ext-disabled"}


def test_items_enabled_none(repo: YAMLRepository) -> None:
    enabled_item = Item(external_id="ext-enabled", enabled=True)
    disabled_item = Item(external_id="ext-disabled", enabled=False)
    repo.save_item(enabled_item)
    repo.save_item(disabled_item)
    result = repo.get_items_by_external_ids(["ext-enabled", "ext-disabled"], enabled=None)
    assert set(result.keys()) == {"ext-enabled", "ext-disabled"}


# ---------------------------------------------------------------------------
# get_categories_by_external_ids — basic (US3)
# ---------------------------------------------------------------------------


def test_categories_all_ids_found(repo: YAMLRepository) -> None:
    cat_a = Category(name="Alpha", external_id="cat-a")
    cat_b = Category(name="Beta", external_id="cat-b")
    repo.save_category(cat_a)
    repo.save_category(cat_b)
    result = repo.get_categories_by_external_ids(["cat-a", "cat-b"])
    assert set(result.keys()) == {"cat-a", "cat-b"}
    assert result["cat-a"].category_id == cat_a.category_id
    assert result["cat-b"].category_id == cat_b.category_id


def test_categories_some_ids_missing(repo: YAMLRepository) -> None:
    cat = Category(name="Alpha", external_id="cat-a")
    repo.save_category(cat)
    result = repo.get_categories_by_external_ids(["cat-a", "cat-missing"])
    assert set(result.keys()) == {"cat-a"}


def test_categories_all_ids_missing(repo: YAMLRepository) -> None:
    result = repo.get_categories_by_external_ids(["no-such", "also-missing"])
    assert result == {}


def test_categories_duplicate_ids(repo: YAMLRepository) -> None:
    cat = Category(name="Alpha", external_id="cat-dup")
    repo.save_category(cat)
    result = repo.get_categories_by_external_ids(["cat-dup", "cat-dup"])
    assert set(result.keys()) == {"cat-dup"}


def test_categories_blank_ids_ignored(repo: YAMLRepository) -> None:
    cat = Category(name="Alpha", external_id="cat-real")
    repo.save_category(cat)
    result = repo.get_categories_by_external_ids(["cat-real", "", "   "])
    assert "cat-real" in result
    assert "" not in result
    assert "   " not in result


def test_categories_empty_input(repo: YAMLRepository) -> None:
    result = repo.get_categories_by_external_ids([])
    assert result == {}


def test_categories_enabled_true(repo: YAMLRepository) -> None:
    enabled_cat = Category(name="Enabled", external_id="cat-enabled", enabled=True)
    disabled_cat = Category(name="Disabled", external_id="cat-disabled", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["cat-enabled", "cat-disabled"], enabled=True)
    assert set(result.keys()) == {"cat-enabled"}


def test_categories_enabled_false(repo: YAMLRepository) -> None:
    enabled_cat = Category(name="Enabled", external_id="cat-enabled", enabled=True)
    disabled_cat = Category(name="Disabled", external_id="cat-disabled", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["cat-enabled", "cat-disabled"], enabled=False)
    assert set(result.keys()) == {"cat-disabled"}


def test_categories_enabled_none(repo: YAMLRepository) -> None:
    enabled_cat = Category(name="Enabled", external_id="cat-enabled", enabled=True)
    disabled_cat = Category(name="Disabled", external_id="cat-disabled", enabled=False)
    repo.save_category(enabled_cat)
    repo.save_category(disabled_cat)
    result = repo.get_categories_by_external_ids(["cat-enabled", "cat-disabled"], enabled=None)
    assert set(result.keys()) == {"cat-enabled", "cat-disabled"}
