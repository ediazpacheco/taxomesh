"""Pydantic request schemas for the taxomesh framework-agnostic API handlers.

These models define the HTTP request contract once, so consuming applications
do not need to define their own input models. All string fields include explicit
max_length constraints per the taxomesh domain naming and validation conventions.
"""

from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from taxomesh.domain.constants import (
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
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

    Only non-None fields are applied by the handler.
    """

    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)] | None = None
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)] | None = None
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] | None = None
    metadata: dict[str, Any] | None = None


class CreateItemRequest(BaseModel):
    """Request body for creating a new item."""

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)]
    external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = ""
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateItemRequest(BaseModel):
    """Request body for partially updating an existing item.

    Only non-None fields are applied by the handler.
    """

    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] | None = None
    external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] | None = None
    enabled: bool | None = None
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] | None = None
    metadata: dict[str, Any] | None = None


class CreateTagRequest(BaseModel):
    """Request body for creating a new tag."""

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)]
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTagRequest(BaseModel):
    """Request body for partially updating an existing tag.

    Only non-None fields are applied by the handler.
    """

    name: Annotated[str, Field(max_length=MAX_TAG_NAME_LENGTH)] | None = None


class AddParentRequest(BaseModel):
    """Request body for adding a parent relationship to a category."""

    parent_id: UUID
    sort_index: int = 0


class PlaceInCategoryRequest(BaseModel):
    """Request body for placing an item in a category."""

    category_id: UUID
    sort_index: int = 0
