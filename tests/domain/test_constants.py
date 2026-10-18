"""Tests for taxomesh.domain.constants — field constraint values."""

from collections.abc import Callable
from uuid import uuid4

import pytest
from pydantic import ValidationError

from taxomesh.domain.constants import (
    DEFAULT_ITEM_EXTERNAL_ID,
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SLUG_LENGTH,
    MAX_TAG_NAME_LENGTH,
    RELATION_TYPE_MAX_LENGTH,
)
from taxomesh.domain.models import Category, Item, ItemRelationLink, Tag


def test_an_item_with_no_external_id_holds_the_default() -> None:
    assert Item(name="x").external_id is DEFAULT_ITEM_EXTERNAL_ID is None


@pytest.mark.parametrize(
    ("build", "documented"),
    [
        (lambda n: Category(category_id=uuid4(), name="x" * n), 256),
        (lambda n: Tag(tag_id=uuid4(), name="x" * n), 25),
        (lambda n: Category(category_id=uuid4(), name="c", description="x" * n), 100_000),
        (lambda n: Item(name="i", external_id="x" * n), 256),
        (lambda n: Category(category_id=uuid4(), name="c", external_id="x" * n), 256),
        (lambda n: Item(name="x" * n), 256),
        (lambda n: Category(category_id=uuid4(), name="c", slug="x" * n), 256),
        (lambda n: Item(name="i", slug="x" * n), 256),
        (lambda n: ItemRelationLink(source_item_id=uuid4(), target_item_id=uuid4(), relation_type="x" * n), 256),
    ],
    ids=[
        "category name",
        "tag name",
        "description",
        "item external id",
        "category external id",
        "item name",
        "category slug",
        "item slug",
        "relation type",
    ],
)
def test_a_field_holds_its_documented_length_and_no_more(build: Callable[[int], object], documented: int) -> None:
    """The limits the API reference states: ``MAX_CATEGORY_NAME_LENGTH`` and the others it names."""
    build(documented)
    with pytest.raises(ValidationError):
        build(documented + 1)


def test_the_constants_are_the_limits_the_models_apply() -> None:
    assert (
        MAX_CATEGORY_NAME_LENGTH,
        MAX_TAG_NAME_LENGTH,
        MAX_DESCRIPTION_LENGTH,
        MAX_EXTERNAL_ID_STR_LENGTH,
        MAX_ITEM_NAME_LENGTH,
        MAX_SLUG_LENGTH,
        RELATION_TYPE_MAX_LENGTH,
    ) == (256, 25, 100_000, 256, 256, 256, 256)
