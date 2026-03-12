"""Tests for taxomesh.contrib.api.schemas — Pydantic request model validation."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from taxomesh.contrib.api.schemas import (
    AddParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceInCategoryRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)
from taxomesh.domain.constants import (
    MAX_CATEGORY_NAME_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SLUG_LENGTH,
    MAX_TAG_NAME_LENGTH,
)


class TestCreateCategoryRequest:
    """Tests for CreateCategoryRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only name is required; defaults apply for other fields."""
        req = CreateCategoryRequest(name="Books")
        assert req.name == "Books"
        assert req.description == ""
        assert req.slug == ""
        assert req.metadata == {}

    def test_valid_full(self) -> None:
        """All fields provided are accepted."""
        req = CreateCategoryRequest(name="Books", description="All books", slug="books", metadata={"k": "v"})
        assert req.description == "All books"
        assert req.slug == "books"
        assert req.metadata == {"k": "v"}

    def test_name_too_long_raises(self) -> None:
        """Name exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            CreateCategoryRequest(name="x" * (MAX_CATEGORY_NAME_LENGTH + 1))

    def test_slug_too_long_raises(self) -> None:
        """Slug exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            CreateCategoryRequest(name="ok", slug="s" * (MAX_SLUG_LENGTH + 1))


class TestUpdateCategoryRequest:
    """Tests for UpdateCategoryRequest schema."""

    def test_all_none_is_valid(self) -> None:
        """Partial update with all None fields is accepted."""
        req = UpdateCategoryRequest()
        assert req.name is None
        assert req.description is None
        assert req.slug is None
        assert req.metadata is None

    def test_partial_update(self) -> None:
        """Only provided fields override defaults."""
        req = UpdateCategoryRequest(name="New Name")
        assert req.name == "New Name"
        assert req.description is None

    def test_name_too_long_raises(self) -> None:
        """Name exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            UpdateCategoryRequest(name="x" * (MAX_CATEGORY_NAME_LENGTH + 1))


class TestCreateItemRequest:
    """Tests for CreateItemRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only name is required; defaults apply for other fields."""
        req = CreateItemRequest(name="Item A")
        assert req.name == "Item A"
        assert req.external_id == ""
        assert req.slug == ""
        assert req.metadata == {}

    def test_valid_with_external_id(self) -> None:
        """external_id is accepted as a string."""
        req = CreateItemRequest(name="Item A", external_id="ext-123")
        assert req.external_id == "ext-123"

    def test_name_too_long_raises(self) -> None:
        """Name exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            CreateItemRequest(name="x" * (MAX_ITEM_NAME_LENGTH + 1))


class TestUpdateItemRequest:
    """Tests for UpdateItemRequest schema."""

    def test_all_none_is_valid(self) -> None:
        """All fields may be None for a no-op update."""
        req = UpdateItemRequest()
        assert req.name is None
        assert req.external_id is None
        assert req.enabled is None
        assert req.slug is None
        assert req.metadata is None

    def test_enabled_field(self) -> None:
        """enabled field accepts bool."""
        req = UpdateItemRequest(enabled=False)
        assert req.enabled is False

    def test_external_id_field(self) -> None:
        """external_id field is accepted as optional str."""
        req = UpdateItemRequest(external_id="ext-99")
        assert req.external_id == "ext-99"


class TestCreateTagRequest:
    """Tests for CreateTagRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only name is required; metadata defaults to empty dict."""
        req = CreateTagRequest(name="fiction")
        assert req.name == "fiction"
        assert req.metadata == {}

    def test_name_too_long_raises(self) -> None:
        """Name exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            CreateTagRequest(name="t" * (MAX_TAG_NAME_LENGTH + 1))


class TestUpdateTagRequest:
    """Tests for UpdateTagRequest schema."""

    def test_all_none_is_valid(self) -> None:
        """All fields may be None."""
        req = UpdateTagRequest()
        assert req.name is None

    def test_name_provided(self) -> None:
        """Non-None name is accepted."""
        req = UpdateTagRequest(name="sci-fi")
        assert req.name == "sci-fi"


class TestAddParentRequest:
    """Tests for AddParentRequest schema."""

    def test_valid(self) -> None:
        """parent_id and sort_index are accepted."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = AddParentRequest(parent_id=uid)
        assert req.parent_id == uid
        assert req.sort_index == 0

    def test_custom_sort_index(self) -> None:
        """sort_index can be set explicitly."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = AddParentRequest(parent_id=uid, sort_index=5)
        assert req.sort_index == 5


class TestPlaceInCategoryRequest:
    """Tests for PlaceInCategoryRequest schema."""

    def test_valid(self) -> None:
        """category_id and sort_index are accepted."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = PlaceInCategoryRequest(category_id=uid)
        assert req.category_id == uid
        assert req.sort_index == 0
