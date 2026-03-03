"""Item domain model."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from taxomesh.domain.constants import (
    DEFAULT_ITEM_EXTERNAL_ID,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SLUG_LENGTH,
)
from taxomesh.domain.models.base import ModelBase


class Item(ModelBase):
    """A generic item that can be categorized and tagged."""

    item_id: UUID = Field(default_factory=uuid4)
    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] = ""
    external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = DEFAULT_ITEM_EXTERNAL_ID
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("external_id", mode="before")
    @classmethod
    def _coerce_external_id(cls, v: object) -> str:
        """Coerce any external_id value to str; None is treated as the default sentinel."""
        if v is None:
            return DEFAULT_ITEM_EXTERNAL_ID
        return str(v)

    def __str__(self) -> str:
        slug_part = f"s: {self.slug} - " if self.slug else ""
        return f"🏷️ {self.name} ({slug_part}id: {self.item_id})"
