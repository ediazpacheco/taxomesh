"""ItemTagLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class ItemTagLink(ModelBase):
    """A tag link: one tag on one item. ``items.tag`` stores one.

    Attributes:
        tag_id: The tag.
        item_id: The tagged item.
    """

    tag_id: UUID
    item_id: UUID
