"""Tests verifying the models package re-exports all public names."""

from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemTagLink,
    ModelBase,
    Tag,
)


def test_all_public_names_are_importable() -> None:
    """All public model classes are importable from taxomesh.domain.models."""
    assert isinstance(ModelBase, type)
    assert isinstance(Item, type)
    assert isinstance(Category, type)
    assert isinstance(Tag, type)
    assert isinstance(CategoryParentLink, type)
    assert isinstance(ItemParentLink, type)
    assert isinstance(ItemTagLink, type)
