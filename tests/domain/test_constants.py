"""Tests for taxomesh.domain.constants — field constraint values."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from taxomesh.domain.constants import (
    DEFAULT_ITEM_EXTERNAL_ID,
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_TAG_NAME_LENGTH,
)
from taxomesh.domain.models import Category, Tag


def test_default_item_external_id_is_none() -> None:
    assert DEFAULT_ITEM_EXTERNAL_ID is None


def test_max_category_name_length_is_256() -> None:
    assert MAX_CATEGORY_NAME_LENGTH == 256


def test_max_tag_name_length_is_25() -> None:
    assert MAX_TAG_NAME_LENGTH == 25


def test_max_description_length_is_100_000() -> None:
    assert MAX_DESCRIPTION_LENGTH == 100_000


def test_max_external_id_str_length_is_256() -> None:
    assert MAX_EXTERNAL_ID_STR_LENGTH == 256


def test_category_name_field_enforces_max_length() -> None:
    with pytest.raises(ValidationError):
        Category(category_id=uuid4(), name="x" * (MAX_CATEGORY_NAME_LENGTH + 1))

    cat = Category(category_id=uuid4(), name="x" * MAX_CATEGORY_NAME_LENGTH)
    assert len(cat.name) == MAX_CATEGORY_NAME_LENGTH


def test_tag_name_field_enforces_max_length() -> None:
    with pytest.raises(ValidationError):
        Tag(tag_id=uuid4(), name="x" * (MAX_TAG_NAME_LENGTH + 1))

    tag = Tag(tag_id=uuid4(), name="x" * MAX_TAG_NAME_LENGTH)
    assert len(tag.name) == MAX_TAG_NAME_LENGTH
