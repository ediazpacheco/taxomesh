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


class CreateCategoryRequest(BaseModel):
    """Request body for creating a new category."""

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)]
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateCategoryRequest(BaseModel):
    """Request body for partially updating an existing category.

    One rule applies: an omitted field carries no instruction and leaves the stored
    value untouched; a present field means "assign exactly this value" and is rejected if that
    value is invalid for the field. Optionality is expressed by an inert default, never by
    widening a field's type — so a non-nullable field rejects an explicit null. The JSON Schema
    publishes no default for a stored field, since omitting it sets nothing. ``external_id``
    is the sole stored field whose value domain includes null, so it alone accepts an explicit
    null, which clears the stored external id. ``expected_version`` is a condition rather
    than a stored field: given, the update is made only if the stored row is at that version;
    omitted or null, no comparison is made.
    """

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH, json_schema_extra=_inert)] = ""
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH, json_schema_extra=_inert)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH, json_schema_extra=_inert)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH, json_schema_extra=_inert)] = None
    enabled: Annotated[bool, Field(json_schema_extra=_inert)] = True
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict, json_schema_extra=_inert)
    expected_version: int | None = None


class CreateItemRequest(BaseModel):
    """Request body for creating a new item."""

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)]
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateItemRequest(BaseModel):
    """Request body for partially updating an existing item.

    One rule applies: an omitted field carries no instruction and leaves the stored
    value untouched; a present field means "assign exactly this value" and is rejected if that
    value is invalid for the field. Optionality is expressed by an inert default, never by
    widening a field's type — so a non-nullable field rejects an explicit null. The JSON Schema
    publishes no default for a stored field, since omitting it sets nothing. ``external_id``
    is the sole stored field whose value domain includes null, so it alone accepts an explicit
    null, which clears the stored external id. ``expected_version`` is a condition rather
    than a stored field: given, the update is made only if the stored row is at that version;
    omitted or null, no comparison is made.
    """

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH, json_schema_extra=_inert)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH, json_schema_extra=_inert)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH, json_schema_extra=_inert)] = None
    enabled: Annotated[bool, Field(json_schema_extra=_inert)] = True
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict, json_schema_extra=_inert)
    expected_version: int | None = None


class CreateTagRequest(BaseModel):
    """Request body for creating a new tag."""

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)]
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTagRequest(BaseModel):
    """Request body for partially updating an existing tag.

    One rule applies: an omitted field carries no instruction; a present field is
    assigned or rejected. Neither field is nullable, so an explicit null is rejected, and not
    ignored. The JSON Schema publishes no default for either, since omitting a
    field sets nothing. As in the item and category updates, a present ``metadata``
    dict **replaces** what was stored.
    """

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH, json_schema_extra=_inert)] = ""
    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    metadata: dict[str, Any] = Field(default_factory=dict, json_schema_extra=_inert)


class AddCategoryParentRequest(BaseModel):
    """Request body for adding a parent to a category."""

    parent_id: UUID
    sort_index: int = 0


class PlaceItemRequest(BaseModel):
    """Request body for placing an item in a category."""

    category_id: UUID
    sort_index: int = 0


class SearchItemsRequest(BaseModel):
    """Request parameters for searching items via the HTTP API.

    ``query`` carries the name ``svc.items.search`` gives it, so the schema and the member spell
    the argument the same way.
    """

    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    category_id: UUID | None = None
    recursive: bool = False
    enabled: bool | None = True
    fuzzy: bool = True


class SearchCategoriesRequest(BaseModel):
    """Request parameters for searching categories via the HTTP API.

    ``query`` carries the name ``svc.categories.search`` gives it, so the schema and the member
    spell the argument the same way.
    """

    query: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    parent_id: UUID | None = None
    enabled: bool | None = True
    fuzzy: bool = True
