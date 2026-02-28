"""Tag domain model."""

from typing import Annotated, Any
from uuid import UUID

from pydantic import Field

from taxomesh.domain.models.base import ModelBase


class Tag(ModelBase):
    """A label that can be assigned to items."""

    tag_id: UUID
    name: Annotated[str, Field(max_length=25)]
    metadata: dict[str, Any] = Field(default_factory=dict)
