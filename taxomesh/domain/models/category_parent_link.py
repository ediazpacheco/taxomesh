"""CategoryParentLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class CategoryParentLink(ModelBase):
    """A parent link: one category under one parent. ``add_parent`` stores one.

    Attributes:
        category_id: The child category.
        parent_category_id: The parent category.
        sort_index: The child's position among the parent's children, lower first, as ``reorder``
            and ``move`` set it.
    """

    category_id: UUID
    parent_category_id: UUID
    sort_index: int = 0
