"""Tests for YAMLRepository list_categories / list_items enabled filter (spec 046).

Written before implementation (TDD-first).
"""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category, Item


@pytest.fixture()
def repo(tmp_path: Path) -> YAMLRepository:
    return YAMLRepository(tmp_path / "test.yaml")


def _make_category(name: str, enabled: bool = True) -> Category:
    return Category(category_id=uuid4(), name=name, enabled=enabled)


def _make_item(name: str, enabled: bool = True) -> Item:
    return Item(name=name, enabled=enabled)


class TestYAMLListCategoriesEnabled:
    def test_enabled_true_filters_out_disabled(self, repo: YAMLRepository) -> None:
        repo.save_category(_make_category("OnCat", enabled=True))
        repo.save_category(_make_category("OffCat", enabled=False))

        result = repo.list_categories(enabled=True)
        names = {c.name for c in result}
        assert "OnCat" in names
        assert "OffCat" not in names

    def test_enabled_false_filters_to_disabled(self, repo: YAMLRepository) -> None:
        repo.save_category(_make_category("ActiveCat", enabled=True))
        repo.save_category(_make_category("InactiveCat", enabled=False))

        result = repo.list_categories(enabled=False)
        names = {c.name for c in result}
        assert "InactiveCat" in names
        assert "ActiveCat" not in names

    def test_enabled_none_returns_all(self, repo: YAMLRepository) -> None:
        repo.save_category(_make_category("CatA", enabled=True))
        repo.save_category(_make_category("CatB", enabled=False))

        result = repo.list_categories(enabled=None)
        names = {c.name for c in result}
        assert "CatA" in names
        assert "CatB" in names

    def test_enabled_true_is_default(self, repo: YAMLRepository) -> None:
        repo.save_category(_make_category("DefaultOnCat", enabled=True))
        repo.save_category(_make_category("DefaultOffCat", enabled=False))

        result = repo.list_categories()
        names = {c.name for c in result}
        assert "DefaultOnCat" in names
        assert "DefaultOffCat" not in names


class TestYAMLListItemsEnabled:
    def test_enabled_true_filters_out_disabled(self, repo: YAMLRepository) -> None:
        repo.save_item(_make_item("OnItem", enabled=True))
        repo.save_item(_make_item("OffItem", enabled=False))

        result = repo.list_items(enabled=True)
        names = {i.name for i in result}
        assert "OnItem" in names
        assert "OffItem" not in names

    def test_enabled_false_filters_to_disabled(self, repo: YAMLRepository) -> None:
        repo.save_item(_make_item("ActiveItem", enabled=True))
        repo.save_item(_make_item("InactiveItem", enabled=False))

        result = repo.list_items(enabled=False)
        names = {i.name for i in result}
        assert "InactiveItem" in names
        assert "ActiveItem" not in names

    def test_enabled_none_returns_all(self, repo: YAMLRepository) -> None:
        repo.save_item(_make_item("ItemX", enabled=True))
        repo.save_item(_make_item("ItemY", enabled=False))

        result = repo.list_items(enabled=None)
        names = {i.name for i in result}
        assert "ItemX" in names
        assert "ItemY" in names

    def test_enabled_true_is_default(self, repo: YAMLRepository) -> None:
        repo.save_item(_make_item("DefaultOnItem", enabled=True))
        repo.save_item(_make_item("DefaultOffItem", enabled=False))

        result = repo.list_items()
        names = {i.name for i in result}
        assert "DefaultOnItem" in names
        assert "DefaultOffItem" not in names
