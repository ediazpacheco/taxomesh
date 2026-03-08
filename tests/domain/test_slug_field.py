"""Tests for the slug field on Item and Category domain models."""

import pytest
from pydantic import ValidationError

from taxomesh.domain.models import Category, Item


class TestItemSlugDefault:
    def test_slug_defaults_to_empty_string(self) -> None:
        item = Item(external_id="ext-1")
        assert item.slug == ""

    def test_slug_can_be_set_at_construction(self) -> None:
        item = Item(external_id="ext-1", slug="my-item")
        assert item.slug == "my-item"


class TestCategorySlugDefault:
    def test_slug_defaults_to_empty_string(self) -> None:
        cat = Category(name="Books")
        assert cat.slug == ""

    def test_slug_can_be_set_at_construction(self) -> None:
        cat = Category(name="Books", slug="books")
        assert cat.slug == "books"


class TestItemStr:
    def test_str_without_slug(self) -> None:
        item = Item(name="My Item", external_id="ext-1")
        result = str(item)
        assert result == f"🏷️ My Item (id: {item.item_id} - ext_id: ext-1)"

    def test_str_with_slug(self) -> None:
        item = Item(name="My Item", external_id="ext-1", slug="my-item")
        result = str(item)
        assert result == f"🏷️ My Item (slug: my-item - id: {item.item_id} - ext_id: ext-1)"

    def test_str_slug_prefix_is_just_slug_space(self) -> None:
        item = Item(name="Item Two", external_id="ext-2", slug="slug-val")
        result = str(item)
        assert "slug: slug-val" in result

    def test_str_without_slug_starts_with_icon(self) -> None:
        item = Item(name="Item Three", external_id="ext-3")
        result = str(item)
        assert result.startswith("🏷️")


class TestCategoryStr:
    def test_str_without_slug(self) -> None:
        cat = Category(name="Gear")
        assert str(cat) == f"📂 Gear (id: {cat.category_id})"

    def test_str_without_slug_with_external_id(self) -> None:
        cat = Category(name="Gear", external_id="gear-001")
        assert str(cat) == f"📂 Gear (id: {cat.category_id} - ext_id: gear-001)"

    def test_str_with_slug(self) -> None:
        cat = Category(name="Gear", slug="gear")
        assert str(cat) == f"📂 Gear (slug: gear - id: {cat.category_id})"

    def test_str_with_slug_and_external_id(self) -> None:
        cat = Category(name="Gear", slug="gear", external_id="gear-001")
        assert str(cat) == f"📂 Gear (slug: gear - id: {cat.category_id} - ext_id: gear-001)"


class TestSlugMaxLength:
    def test_item_slug_at_max_length_is_valid(self) -> None:
        item = Item(external_id="x", slug="a" * 256)
        assert len(item.slug) == 256

    def test_item_slug_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Item(external_id="x", slug="a" * 257)

    def test_category_slug_at_max_length_is_valid(self) -> None:
        cat = Category(name="X", slug="a" * 256)
        assert len(cat.slug) == 256

    def test_category_slug_over_max_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            Category(name="X", slug="a" * 257)
