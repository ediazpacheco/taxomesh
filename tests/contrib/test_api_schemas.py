"""Tests for taxomesh.contrib.api.schemas — Pydantic request model validation."""

from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from taxomesh.contrib.api.schemas import (
    AddCategoryParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceItemRequest,
    SearchCategoriesRequest,
    SearchItemsRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)
from taxomesh.domain.constants import (
    MAX_CATEGORY_NAME_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
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

    def test_external_id_defaults_to_none(self) -> None:
        """``external_id`` is optional, as it is on ``categories.create``."""
        assert CreateCategoryRequest(name="Books").external_id is None

    def test_external_id_field(self) -> None:
        """A given external_id is carried, as on the item request."""
        assert CreateCategoryRequest(name="Books", external_id="ext-books").external_id == "ext-books"

    def test_external_id_too_long_raises(self) -> None:
        """external_id exceeding its max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            CreateCategoryRequest(name="Books", external_id="e" * (MAX_EXTERNAL_ID_STR_LENGTH + 1))

    @pytest.mark.parametrize("field", ["name", "description", "slug", "metadata"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """The creation schema already conforms to the single rule — null is rejected here.

        Locks the conformance in so a creation field can never later be widened to X | None merely
        to express that it may be omitted.
        """
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {"name": "ok", field: None}
        with pytest.raises(ValidationError):
            CreateCategoryRequest(**kwargs)


class TestUpdateCategoryRequest:
    """Tests for UpdateCategoryRequest schema — same single rule as items, including the
    external_id and enabled fields."""

    def test_all_fields_omittable(self) -> None:
        """Every field may be omitted; an empty request carries no instruction."""
        req = UpdateCategoryRequest()
        assert req.model_fields_set == set()
        assert req.model_dump(exclude_unset=True) == {}

    def test_partial_update_records_only_set_fields(self) -> None:
        """Only fields the caller set are recorded; an unmentioned field stays absent, not defaulted."""
        req = UpdateCategoryRequest(name="New Name")
        assert req.name == "New Name"
        assert req.model_fields_set == {"name"}
        assert "description" not in req.model_fields_set

    def test_name_too_long_raises(self) -> None:
        """Name exceeding max_length triggers a ValidationError."""
        with pytest.raises(ValidationError):
            UpdateCategoryRequest(name="x" * (MAX_CATEGORY_NAME_LENGTH + 1))

    @pytest.mark.parametrize("field", ["name", "description", "slug", "metadata", "enabled"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """A non-nullable field rejects an explicit null, including the new enabled field."""
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {field: None}
        with pytest.raises(ValidationError):
            UpdateCategoryRequest(**kwargs)

    def test_external_id_field(self) -> None:
        """external_id is exposed and accepts a string."""
        req = UpdateCategoryRequest(external_id="ext-cat")
        assert req.external_id == "ext-cat"
        assert "external_id" in req.model_fields_set

    def test_explicit_null_external_id_is_valid(self) -> None:
        """external_id is the sole nullable field: an explicit null is accepted as 'clear'."""
        req = UpdateCategoryRequest(external_id=None)
        assert req.external_id is None
        assert "external_id" in req.model_fields_set

    def test_enabled_field(self) -> None:
        """enabled is exposed and accepts a bool."""
        req = UpdateCategoryRequest(enabled=False)
        assert req.enabled is False
        assert "enabled" in req.model_fields_set


class TestCreateItemRequest:
    """Tests for CreateItemRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only name is required; defaults apply for other fields."""
        req = CreateItemRequest(name="Item A")
        assert req.name == "Item A"
        assert req.external_id is None
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

    @pytest.mark.parametrize("field", ["name", "slug", "metadata"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """The creation schema rejects null on non-nullable fields."""
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {"name": "ok", field: None}
        with pytest.raises(ValidationError):
            CreateItemRequest(**kwargs)

    def test_explicit_null_external_id_is_accepted(self) -> None:
        """external_id is nullable, so an explicit null is accepted (means absent)."""
        req = CreateItemRequest(name="ok", external_id=None)
        assert req.external_id is None


class TestUpdateItemRequest:
    """Tests for UpdateItemRequest schema — the single rule: omitted = no instruction,
    present = assign-or-reject, only external_id accepts null (it is the sole nullable field)."""

    def test_all_fields_omittable(self) -> None:
        """Every field may be omitted; an empty request carries no instruction.

        Presence — not a default value — is what carries meaning. ``model_fields_set`` is empty
        and ``model_dump(exclude_unset=True)`` yields nothing to delegate, so a no-op update
        touches no stored field.
        """
        req = UpdateItemRequest()
        assert req.model_fields_set == set()
        assert req.model_dump(exclude_unset=True) == {}

    def test_enabled_field(self) -> None:
        """enabled field accepts bool."""
        req = UpdateItemRequest(enabled=False)
        assert req.enabled is False

    def test_external_id_field(self) -> None:
        """external_id field is accepted as optional str."""
        req = UpdateItemRequest(external_id="ext-99")
        assert req.external_id == "ext-99"

    @pytest.mark.parametrize("field", ["name", "slug", "enabled", "metadata"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """A non-nullable field rejects an explicit null — it is not accepted and discarded."""
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {field: None}
        with pytest.raises(ValidationError):
            UpdateItemRequest(**kwargs)

    def test_explicit_null_external_id_is_valid(self) -> None:
        """external_id is the sole nullable field: an explicit null is accepted as 'clear'."""
        req = UpdateItemRequest(external_id=None)
        assert req.external_id is None
        assert "external_id" in req.model_fields_set

    def test_present_valid_value_is_assigned(self) -> None:
        """A present valid value is recorded as set, so it is delegated."""
        req = UpdateItemRequest(name="Renamed", slug="renamed")
        assert req.name == "Renamed"
        assert req.slug == "renamed"
        assert req.model_fields_set == {"name", "slug"}


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

    @pytest.mark.parametrize("field", ["name", "metadata"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """The creation schema rejects null on non-nullable fields."""
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {"name": "ok", field: None}
        with pytest.raises(ValidationError):
            CreateTagRequest(**kwargs)


class TestUpdateTagRequest:
    """Tests for UpdateTagRequest schema."""

    def test_name_omittable(self) -> None:
        """name may be omitted; an empty request carries no instruction."""
        req = UpdateTagRequest()
        assert req.model_fields_set == set()
        assert req.model_dump(exclude_unset=True) == {}

    def test_name_provided(self) -> None:
        """Non-None name is accepted."""
        req = UpdateTagRequest(name="sci-fi")
        assert req.name == "sci-fi"

    def test_metadata_provided(self) -> None:
        """metadata reaches parity with CreateTagRequest: the field exists and accepts a dict."""
        req = UpdateTagRequest(metadata={"k": "v"})
        assert req.metadata == {"k": "v"}
        assert "metadata" in req.model_fields_set

    @pytest.mark.parametrize("field", ["name", "metadata"])
    def test_explicit_null_on_non_nullable_field_is_rejected(self, field: str) -> None:
        """Neither field is nullable: an explicit null is rejected, not discarded."""
        # Any: splatted into the schema, so the one mapping must fit every field it probes
        kwargs: dict[str, Any] = {field: None}
        with pytest.raises(ValidationError):
            UpdateTagRequest(**kwargs)


class TestAddCategoryParentRequest:
    """Tests for AddCategoryParentRequest schema."""

    def test_valid(self) -> None:
        """parent_id and sort_index are accepted."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = AddCategoryParentRequest(parent_id=uid)
        assert req.parent_id == uid
        assert req.sort_index == 0

    def test_custom_sort_index(self) -> None:
        """sort_index can be set explicitly."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = AddCategoryParentRequest(parent_id=uid, sort_index=5)
        assert req.sort_index == 5


class TestPlaceItemRequest:
    """Tests for PlaceItemRequest schema."""

    def test_valid(self) -> None:
        """category_id and sort_index are accepted."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = PlaceItemRequest(category_id=uid)
        assert req.category_id == uid
        assert req.sort_index == 0


class TestSearchItemsRequest:
    """Tests for SearchItemsRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only query is required; defaults apply for all other fields."""
        req = SearchItemsRequest(query="troilo")
        assert req.query == "troilo"
        assert req.limit == 20
        assert req.category_id is None
        assert req.recursive is False
        assert req.enabled is True
        assert req.fuzzy is True

    def test_query_too_long_raises(self) -> None:
        """query exceeding MAX_SEARCH_QUERY_LENGTH triggers a ValidationError."""
        with pytest.raises(ValidationError):
            SearchItemsRequest(query="x" * (MAX_SEARCH_QUERY_LENGTH + 1))

    def test_category_id_accepts_uuid(self) -> None:
        """category_id accepts a valid UUID."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = SearchItemsRequest(query="troilo", category_id=uid)
        assert req.category_id == uid

    def test_category_id_accepts_none(self) -> None:
        """category_id accepts None explicitly."""
        req = SearchItemsRequest(query="troilo", category_id=None)
        assert req.category_id is None

    def test_custom_limit(self) -> None:
        """limit field is accepted as an int."""
        req = SearchItemsRequest(query="troilo", limit=5)
        assert req.limit == 5

    def test_enabled_accepts_none(self) -> None:
        """The third state is expressible from the HTTP edge: None means every match.

        A plain ``bool`` would reject it, and "all" could not be asked for over HTTP though the
        collection accepts it.
        """
        req = SearchItemsRequest(query="troilo", enabled=None)
        assert req.enabled is None


class TestSearchCategoriesRequest:
    """Tests for SearchCategoriesRequest schema."""

    def test_valid_minimal(self) -> None:
        """Only query is required; defaults apply for all other fields."""
        req = SearchCategoriesRequest(query="jazz")
        assert req.query == "jazz"
        assert req.limit == 20
        assert req.parent_id is None
        assert req.enabled is True
        assert req.fuzzy is True

    def test_query_too_long_raises(self) -> None:
        """query exceeding MAX_SEARCH_QUERY_LENGTH triggers a ValidationError."""
        with pytest.raises(ValidationError):
            SearchCategoriesRequest(query="x" * (MAX_SEARCH_QUERY_LENGTH + 1))

    def test_parent_id_accepts_uuid(self) -> None:
        """parent_id accepts a valid UUID."""
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = SearchCategoriesRequest(query="jazz", parent_id=uid)
        assert req.parent_id == uid

    def test_parent_id_accepts_none(self) -> None:
        """parent_id accepts None explicitly."""
        req = SearchCategoriesRequest(query="jazz", parent_id=None)
        assert req.parent_id is None

    def test_custom_limit(self) -> None:
        """limit field is accepted as an int."""
        req = SearchCategoriesRequest(query="jazz", limit=3)
        assert req.limit == 3

    def test_enabled_accepts_none(self) -> None:
        """The third state is expressible from the HTTP edge: None means every match."""
        req = SearchCategoriesRequest(query="jazz", enabled=None)
        assert req.enabled is None


UPDATE_SCHEMAS: list[type[BaseModel]] = [UpdateCategoryRequest, UpdateItemRequest, UpdateTagRequest]


class TestUpdateSchemasPublishNoDefault:
    """An update field's default is inert: omitted, the field is left as it is stored.

    So the JSON Schema publishes no default for it, and a reader of the schema does not see
    ``enabled`` defaulting to ``true``. ``expected_version`` is a condition rather than a stored
    field, and its ``null`` default, which makes no comparison, is a real value.
    """

    @pytest.mark.parametrize("schema", UPDATE_SCHEMAS, ids=[s.__name__ for s in UPDATE_SCHEMAS])
    def test_no_stored_field_publishes_a_default(self, schema: type[BaseModel]) -> None:
        properties = schema.model_json_schema()["properties"]
        published = {name for name, spec in properties.items() if "default" in spec and name != "expected_version"}
        assert published == set()

    @pytest.mark.parametrize("schema", [UpdateCategoryRequest, UpdateItemRequest])
    def test_expected_version_publishes_its_null_default(self, schema: type[BaseModel]) -> None:
        assert schema.model_json_schema()["properties"]["expected_version"]["default"] is None

    @pytest.mark.parametrize("schema", UPDATE_SCHEMAS, ids=[s.__name__ for s in UPDATE_SCHEMAS])
    def test_an_empty_body_sets_nothing(self, schema: type[BaseModel]) -> None:
        assert schema.model_validate({}).model_fields_set == set()
