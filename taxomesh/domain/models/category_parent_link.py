"""CategoryParentLink domain model."""

from uuid import UUID

from taxomesh.domain.models.base import ModelBase


class CategoryParentLink(ModelBase):
    """A relationship between a category and its parent category."""

    category_id: UUID
    parent_category_id: UUID
    sort_index: int = 0
