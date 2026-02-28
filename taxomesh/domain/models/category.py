"""Category domain model."""

from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, field_validator

from taxomesh.domain.models.base import ModelBase
from taxomesh.domain.types import ExternalId


class Category(ModelBase):
    """A taxonomy category that can form a DAG with other categories."""

    category_id: UUID
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""
    enabled: bool = True
    external_id: ExternalId = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_none_description(cls, v: object) -> object:
        """Coerce None description to empty string."""
        return "" if v is None else v
