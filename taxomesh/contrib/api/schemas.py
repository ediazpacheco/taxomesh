"""The pydantic request schemas of the HTTP handlers.

The schemas define the HTTP requests once, so an application does not define its own input
models. Every ``str`` field declares a ``max_length``, from the constants of the domain.
"""

from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import JsonDict

from taxomesh.application.search import DEFAULT_SEARCH_LIMIT
from taxomesh.domain.constants import (
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SEARCH_QUERY_LENGTH,
    MAX_SLUG_LENGTH,
    MAX_TAG_NAME_LENGTH,
)


def _inert(schema: JsonDict) -> None:
    """Publish no default for an update field: an omitted field keeps the stored value.

    The Python default of the field only lets a request omit it. A handler passes on only the
    fields that the caller set, so the default never reaches storage. A schema that published the
    default would show it as a value that an empty body sets.
    """
    schema.pop("default", None)


_Slug = Annotated[str, Field(max_length=MAX_SLUG_LENGTH)]
_ExternalId = Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)]
_Description = Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)]
# Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
_JsonObject = dict[str, Any]


class CreateCategoryRequest(BaseModel):
    """Request body for creating a new category."""

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)]
    description: _Description = ""
    slug: _Slug = ""
    external_id: _ExternalId = None
    metadata: _JsonObject = Field(default_factory=dict)


class UpdateCategoryRequest(BaseModel):
    """Request body for partially updating an existing category.

    One rule applies. An omitted field carries no instruction, and the stored value stays as it
    is. A present field means "assign exactly this value". The request fails if that value is
    invalid for the field.

    A field is optional through an inert default, never through a wider type. So a non-nullable
    field rejects an explicit null. The JSON Schema publishes no default for a stored field,
    because omitting the field sets nothing. ``external_id`` is the only stored field whose value
    can be null. So it alone accepts an explicit null, which clears the stored external id.

    ``expected_version`` is a condition, and not a stored field. When the request gives it, the
    update succeeds only if the stored row is at that version. When the request omits it or gives
    null, the update makes no comparison.
    """

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH, json_schema_extra=_inert)] = ""
    description: Annotated[_Description, Field(json_schema_extra=_inert)] = ""
    slug: Annotated[_Slug, Field(json_schema_extra=_inert)] = ""
    external_id: Annotated[_ExternalId, Field(json_schema_extra=_inert)] = None
    enabled: Annotated[bool, Field(json_schema_extra=_inert)] = True
    metadata: _JsonObject = Field(default_factory=dict, json_schema_extra=_inert)
    expected_version: int | None = None


class CreateItemRequest(BaseModel):
    """Request body for creating a new item."""

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)]
    slug: _Slug = ""
    external_id: _ExternalId = None
    metadata: _JsonObject = Field(default_factory=dict)


class UpdateItemRequest(BaseModel):
    """Request body for partially updating an existing item.

    One rule applies. An omitted field carries no instruction, and the stored value stays as it
    is. A present field means "assign exactly this value". The request fails if that value is
    invalid for the field.

    A field is optional through an inert default, never through a wider type. So a non-nullable
    field rejects an explicit null. The JSON Schema publishes no default for a stored field,
    because omitting the field sets nothing. ``external_id`` is the only stored field whose value
    can be null. So it alone accepts an explicit null, which clears the stored external id.

    ``expected_version`` is a condition, and not a stored field. When the request gives it, the
    update succeeds only if the stored row is at that version. When the request omits it or gives
    null, the update makes no comparison.
    """

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH, json_schema_extra=_inert)] = ""
    slug: Annotated[_Slug, Field(json_schema_extra=_inert)] = ""
    external_id: Annotated[_ExternalId, Field(json_schema_extra=_inert)] = None
    enabled: Annotated[bool, Field(json_schema_extra=_inert)] = True
    metadata: _JsonObject = Field(default_factory=dict, json_schema_extra=_inert)
    expected_version: int | None = None


class CreateTagRequest(BaseModel):
    """Request body for creating a new tag."""

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)]
    metadata: _JsonObject = Field(default_factory=dict)


class UpdateTagRequest(BaseModel):
    """Request body for partially updating an existing tag.

    One rule applies. An omitted field carries no instruction. The update assigns the value of a
    present field, or the request fails. Neither field is nullable, so the schema rejects an
    explicit null, and does not ignore it. The JSON Schema publishes no default for either,
    because omitting a field sets nothing. As in the item and category updates, a present
    ``metadata`` dict **replaces** what was stored.
    """

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH, json_schema_extra=_inert)] = ""
    metadata: _JsonObject = Field(default_factory=dict, json_schema_extra=_inert)


class AddCategoryParentRequest(BaseModel):
    """Request body for adding a parent to a category. With no ``sort_index``, the child goes last."""

    parent_id: UUID
    sort_index: int | None = None


class PlaceItemRequest(BaseModel):
    """Request body for placing an item in a category. With no ``sort_index``, the item goes last."""

    category_id: UUID
    sort_index: int | None = None


class SearchItemsRequest(BaseModel):
    """Request parameters for searching items through the HTTP API.

    ``query`` has the name that ``svc.items.search`` gives it, so the schema and the member spell
    the argument the same way.
    """

    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    category_id: UUID | None = None
    recursive: bool = False
    enabled: bool | None = True
    fuzzy: bool = True


class SearchCategoriesRequest(BaseModel):
    """Request parameters for searching categories through the HTTP API.

    ``query`` has the name that ``svc.categories.search`` gives it, so the schema and the member
    spell the argument the same way.
    """

    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    parent_id: UUID | None = None
    enabled: bool | None = True
    fuzzy: bool = True
