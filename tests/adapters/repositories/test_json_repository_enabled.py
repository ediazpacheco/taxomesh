"""Tests for JsonRepository list_categories / list_items enabled filter (spec 046).

Written before implementation (TDD-first).
"""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, Item


@pytest.fixture()
def repo(tmp_path: Path) -> JsonRepository:
    return JsonRepository(tmp_path / "test.json")


def _make_category(name: str, enabled: bool = True) -> Category:
    cat = Category(category_id=uuid4(), name=name, enabled=enabled)
    return cat


def _make_item(name: str, enabled: bool = True) -> Item:
    return Item(name=name, enabled=enabled)


class TestJsonListCategoriesEnabled:
    def test_enabled_true_filters_out_disabled(self, repo: JsonRepository) -> None:
        cat_on = _make_category("OnCat", enabled=True)
        cat_off = _make_category("OffCat", enabled=False)
        repo.save_category(cat_on)
        repo.save_category(cat_off)

        result = repo.list_categories(enabled=True)
        names = {c.name for c in result}
        assert "OnCat" in names
        assert "OffCat" not in names

    def test_enabled_false_filters_to_disabled(self, repo: JsonRepository) -> None:
        cat_on = _make_category("ActiveCat", enabled=True)
        cat_off = _make_category("InactiveCat", enabled=False)
        repo.save_category(cat_on)
        repo.save_category(cat_off)

        result = repo.list_categories(enabled=False)
        names = {c.name for c in result}
        assert "InactiveCat" in names
        assert "ActiveCat" not in names

    def test_enabled_none_returns_all(self, repo: JsonRepository) -> None:
        cat_on = _make_category("CatA", enabled=True)
        cat_off = _make_category("CatB", enabled=False)
        repo.save_category(cat_on)
        repo.save_category(cat_off)

        result = repo.list_categories(enabled=None)
        names = {c.name for c in result}
        assert "CatA" in names
        assert "CatB" in names

    def test_enabled_true_is_default(self, repo: JsonRepository) -> None:
        cat_on = _make_category("DefaultOnCat", enabled=True)
        cat_off = _make_category("DefaultOffCat", enabled=False)
        repo.save_category(cat_on)
        repo.save_category(cat_off)

        result = repo.list_categories()
        names = {c.name for c in result}
        assert "DefaultOnCat" in names
        assert "DefaultOffCat" not in names

    def test_empty_store_returns_empty(self, repo: JsonRepository) -> None:
        assert repo.list_categories(enabled=True) == []
        assert repo.list_categories(enabled=False) == []
        assert repo.list_categories(enabled=None) == []


class TestJsonListItemsEnabled:
    def test_enabled_true_filters_out_disabled(self, repo: JsonRepository) -> None:
        item_on = _make_item("OnItem", enabled=True)
        item_off = _make_item("OffItem", enabled=False)
        repo.save_item(item_on)
        repo.save_item(item_off)

        result = repo.list_items(enabled=True)
        names = {i.name for i in result}
        assert "OnItem" in names
        assert "OffItem" not in names

    def test_enabled_false_filters_to_disabled(self, repo: JsonRepository) -> None:
        item_on = _make_item("ActiveItem", enabled=True)
        item_off = _make_item("InactiveItem", enabled=False)
        repo.save_item(item_on)
        repo.save_item(item_off)

        result = repo.list_items(enabled=False)
        names = {i.name for i in result}
        assert "InactiveItem" in names
        assert "ActiveItem" not in names

    def test_enabled_none_returns_all(self, repo: JsonRepository) -> None:
        item_on = _make_item("ItemX", enabled=True)
        item_off = _make_item("ItemY", enabled=False)
        repo.save_item(item_on)
        repo.save_item(item_off)

        result = repo.list_items(enabled=None)
        names = {i.name for i in result}
        assert "ItemX" in names
        assert "ItemY" in names

    def test_enabled_true_is_default(self, repo: JsonRepository) -> None:
        item_on = _make_item("DefaultOnItem", enabled=True)
        item_off = _make_item("DefaultOffItem", enabled=False)
        repo.save_item(item_on)
        repo.save_item(item_off)

        result = repo.list_items()
        names = {i.name for i in result}
        assert "DefaultOnItem" in names
        assert "DefaultOffItem" not in names
