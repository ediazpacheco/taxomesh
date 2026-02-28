"""ItemParentLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class ItemParentLink(ModelBase):
    """A relationship between an item and its parent category."""

    item_id: UUID
    category_id: UUID
    sort_index: int = 0
