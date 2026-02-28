"""Item domain model."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from taxomesh.domain.models.base import ModelBase
from taxomesh.domain.types import ExternalId


class Item(ModelBase):
    """A generic item that can be categorized and tagged."""

    item_id: UUID = Field(default_factory=uuid4)
    external_id: ExternalId
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
