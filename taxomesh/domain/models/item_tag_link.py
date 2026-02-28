"""ItemTagLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class ItemTagLink(ModelBase):
    """A relationship between a tag and an item."""

    tag_id: UUID
    item_id: UUID
