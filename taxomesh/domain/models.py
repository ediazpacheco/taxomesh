from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from taxomesh.domain.types import ExternalId


class ModelBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=True)


class Item(ModelBase):
    item_id: UUID = Field(default_factory=uuid4)
    external_id: ExternalId
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)  # arbitrary user-supplied key-value pairs


class Category(ModelBase):
    category_id: UUID
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)  # arbitrary user-supplied key-value pairs

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_none_description(cls, v: object) -> object:
        return v or ""


class Tag(ModelBase):
    tag_id: UUID
    name: Annotated[str, Field(max_length=25)]
    metadata: dict[str, Any] = Field(default_factory=dict)  # arbitrary user-supplied key-value pairs


class CategoryParentLink(ModelBase):
    category_id: UUID
    parent_category_id: UUID
    sort_index: int = 0


class ItemParentLink(ModelBase):
    item_id: UUID  # references Item.item_id (internal UUID primary key)
    category_id: UUID
    sort_index: int = 0


class ItemTagLink(ModelBase):
    tag_id: UUID
    item_id: UUID  # references Item.item_id (internal UUID primary key)
