"""Category domain model."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator

from taxomesh.domain.constants import (
    DEFAULT_CATEGORY_EXTERNAL_ID,
    DEFAULT_DESCRIPTION,
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
)
from taxomesh.domain.models.base import ModelBase


class Category(ModelBase):
    """A taxonomy category that can form a DAG with other categories."""

    category_id: UUID = Field(default_factory=uuid4)
    name: Annotated[str, Field(max_length=MAX_CATEGORY_NAME_LENGTH)]
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)] = DEFAULT_DESCRIPTION
    enabled: bool = True
    external_id: Annotated[str, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)] = DEFAULT_CATEGORY_EXTERNAL_ID
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_none_description(cls, v: object) -> object:
        """Coerce None description to empty string."""
        return "" if v is None else v

    @field_validator("external_id", mode="before")
    @classmethod
    def _coerce_external_id(cls, v: object) -> str:
        """Coerce any external_id value to str."""
        return str(v)
