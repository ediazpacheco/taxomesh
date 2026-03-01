"""Item domain model."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from taxomesh.domain.constants import MAX_EXTERNAL_ID_STR_LENGTH
from taxomesh.domain.models.base import ModelBase


class Item(ModelBase):
    """A generic item that can be categorized and tagged."""

    item_id: UUID = Field(default_factory=uuid4)
    external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)]
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("external_id", mode="before")
    @classmethod
    def _coerce_external_id(cls, v: object) -> str:
        """Coerce any external_id value to str."""
        return str(v)
