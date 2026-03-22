"""Item domain model."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from taxomesh.domain.constants import (
    AUDIT_EPOCH,
    DEFAULT_ITEM_EXTERNAL_ID,
    DEFAULT_VERSION,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SLUG_LENGTH,
)
from taxomesh.domain.models.base import ModelBase, _build_str_repr


class Item(ModelBase):
    """A generic item that can be categorized and tagged."""

    item_id: UUID = Field(default_factory=uuid4)
    name: Annotated[str, Field(max_length=MAX_ITEM_NAME_LENGTH)] = ""
    external_id: Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = DEFAULT_ITEM_EXTERNAL_ID
    slug: Annotated[str, Field(max_length=MAX_SLUG_LENGTH)] = ""
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default=AUDIT_EPOCH)
    updated_at: datetime = Field(default=AUDIT_EPOCH)
    version: Annotated[int, Field(ge=0)] = DEFAULT_VERSION

    @field_validator("external_id", mode="before")
    @classmethod
    def _coerce_external_id(cls, v: object) -> str | None:
        """Coerce any external_id value to str; None stays None."""
        if v is None:
            return None
        return str(v)

    def __str__(self) -> str:
        return _build_str_repr("🏷️", self.name, self.item_id, self.slug, self.external_id)
