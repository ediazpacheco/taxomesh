"""Pydantic request schemas for the taxomesh framework-agnostic API handlers.

These models define the HTTP request contract once, so consuming applications
do not need to define their own input models. All string fields include explicit
max_length constraints per the taxomesh domain naming and validation conventions.
"""

from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

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


class CreateCategoryRequest(BaseModel):
    """Request body for creating a new category."""

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)]
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateCategoryRequest(BaseModel):
    """Request body for partially updating an existing category.

    Follows the single rule: an omitted field carries no instruction and leaves the stored
    value untouched; a present field means "assign exactly this value" and is rejected if that
    value is invalid for the field. Optionality is expressed by an inert default, never by
    widening a field's type — so a non-nullable field rejects an explicit null. ``external_id``
    is the sole field whose value domain includes null, so it alone accepts an explicit null,
    which clears the stored external identifier.
    """

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)] = ""
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None
    enabled: bool = True


class CreateItemRequest(BaseModel):
    """Request body for creating a new item."""

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)]
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateItemRequest(BaseModel):
    """Request body for partially updating an existing item.

    Follows the single rule: an omitted field carries no instruction and leaves the stored
    value untouched; a present field means "assign exactly this value" and is rejected if that
    value is invalid for the field. Optionality is expressed by an inert default, never by
    widening a field's type — so a non-nullable field rejects an explicit null. ``external_id``
    is the sole field whose value domain includes null, so it alone accepts an explicit null,
    which clears the stored external identifier.
    """

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = None
    enabled: bool = True
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateTagRequest(BaseModel):
    """Request body for creating a new tag."""

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)]
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTagRequest(BaseModel):
    """Request body for partially updating an existing tag.

    Follows the single rule: an omitted field carries no instruction; a present field is
    assigned or rejected. ``name`` is non-nullable, so an explicit null is rejected rather
    than silently discarded.
    """

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)] = ""


class AddParentRequest(BaseModel):
    """Request body for adding a parent relationship to a category."""

    parent_id: UUID
    sort_index: int = 0


class PlaceInCategoryRequest(BaseModel):
    """Request body for placing an item in a category."""

    category_id: UUID
    sort_index: int = 0


class SearchItemsRequest(BaseModel):
    """Request parameters for searching items via the HTTP API."""

    q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    category_id: UUID | None = None
    recursive: bool = False
    enabled: bool = True
    fuzzy: bool = True


class SearchCategoriesRequest(BaseModel):
    """Request parameters for searching categories via the HTTP API."""

    q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT
    parent_id: UUID | None = None
    enabled: bool = True
    fuzzy: bool = True
