"""ItemParentLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class ItemParentLink(ModelBase):
    """A placement: one item in one category. ``place_in`` stores one.

    Attributes:
        item_id: The placed item.
        category_id: The category it is placed in.
        sort_index: The item's position among the category's items, lower first, as ``reorder``
            and ``move`` set it.
    """

    item_id: UUID
    category_id: UUID
    sort_index: int = 0
