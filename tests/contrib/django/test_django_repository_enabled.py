"""Tests for DjangoRepository list_categories / list_items enabled filter (spec 046).

Written before implementation (TDD-first).
"""

from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel, ItemModel  # noqa: E402

pytestmark = pytest.mark.django_db


class TestDjangoListCategoriesEnabled:
    def test_enabled_true_filters_out_disabled(self) -> None:
        CategoryModel.objects.create(category_id=uuid4(), name="OnCat", enabled=True)
        CategoryModel.objects.create(category_id=uuid4(), name="OffCat", enabled=False)

        result = DjangoRepository().list_categories(enabled=True)
        names = {c.name for c in result}
        assert "OnCat" in names
        assert "OffCat" not in names

    def test_enabled_false_filters_to_disabled(self) -> None:
        CategoryModel.objects.create(category_id=uuid4(), name="ActiveCat", enabled=True)
        CategoryModel.objects.create(category_id=uuid4(), name="InactiveCat", enabled=False)

        result = DjangoRepository().list_categories(enabled=False)
        names = {c.name for c in result}
        assert "InactiveCat" in names
        assert "ActiveCat" not in names

    def test_enabled_none_returns_all(self) -> None:
        CategoryModel.objects.create(category_id=uuid4(), name="CatA", enabled=True)
        CategoryModel.objects.create(category_id=uuid4(), name="CatB", enabled=False)

        result = DjangoRepository().list_categories(enabled=None)
        names = {c.name for c in result}
        assert "CatA" in names
        assert "CatB" in names

    def test_enabled_true_is_default(self) -> None:
        CategoryModel.objects.create(category_id=uuid4(), name="DefaultOnCat", enabled=True)
        CategoryModel.objects.create(category_id=uuid4(), name="DefaultOffCat", enabled=False)

        result = DjangoRepository().list_categories()
        names = {c.name for c in result}
        assert "DefaultOnCat" in names
        assert "DefaultOffCat" not in names


class TestDjangoListItemsEnabled:
    def test_enabled_true_filters_out_disabled(self) -> None:
        ItemModel.objects.create(item_id=uuid4(), name="OnItem", enabled=True)
        ItemModel.objects.create(item_id=uuid4(), name="OffItem", enabled=False)

        result = DjangoRepository().list_items(enabled=True)
        names = {i.name for i in result}
        assert "OnItem" in names
        assert "OffItem" not in names

    def test_enabled_false_filters_to_disabled(self) -> None:
        ItemModel.objects.create(item_id=uuid4(), name="ActiveItem", enabled=True)
        ItemModel.objects.create(item_id=uuid4(), name="InactiveItem", enabled=False)

        result = DjangoRepository().list_items(enabled=False)
        names = {i.name for i in result}
        assert "InactiveItem" in names
        assert "ActiveItem" not in names

    def test_enabled_none_returns_all(self) -> None:
        ItemModel.objects.create(item_id=uuid4(), name="ItemX", enabled=True)
        ItemModel.objects.create(item_id=uuid4(), name="ItemY", enabled=False)

        result = DjangoRepository().list_items(enabled=None)
        names = {i.name for i in result}
        assert "ItemX" in names
        assert "ItemY" in names

    def test_enabled_true_is_default(self) -> None:
        ItemModel.objects.create(item_id=uuid4(), name="DefaultOnItem", enabled=True)
        ItemModel.objects.create(item_id=uuid4(), name="DefaultOffItem", enabled=False)

        result = DjangoRepository().list_items()
        names = {i.name for i in result}
        assert "DefaultOnItem" in names
        assert "DefaultOffItem" not in names
