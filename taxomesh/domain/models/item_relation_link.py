"""ItemRelationLink domain model."""

from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from taxomesh.domain.constants import RELATION_TYPE_MAX_LENGTH
from taxomesh.domain.models.base import ModelBase
from taxomesh.exceptions import TaxomeshRelationError


class ItemRelationLink(ModelBase):
    """A directed, typed relation from one item to another.

    The triple ``(source_item_id, target_item_id, relation_type)`` is the
    natural composite key — two links with the same triple are the same record.
    ``relation_type`` is always stored in lowercase; callers may supply any
    casing and it will be normalised transparently.
    """

    source_item_id: UUID
    target_item_id: UUID
    relation_type: Annotated[str, Field(max_length=RELATION_TYPE_MAX_LENGTH)]
    sort_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_type", mode="before")
    @classmethod
    def _normalise_relation_type(cls, v: object) -> str:
        """Strip whitespace and lowercase the relation type before validation.

        Args:
            v: Raw value passed to the field.

        Returns:
            Normalised lowercase string.

        Raises:
            TaxomeshRelationError: If the value is not a non-empty string after
                stripping whitespace.
        """
        if not isinstance(v, str):
            raise TaxomeshRelationError(f"relation_type must be a string, got {type(v).__name__}")
        normalised = v.strip().lower()
        if not normalised:
            raise TaxomeshRelationError("relation_type must not be empty or whitespace-only")
        return normalised

    @model_validator(mode="after")
    def _reject_self_relation(self) -> "ItemRelationLink":
        """Reject relations where source and target are the same item.

        Returns:
            This instance if valid.

        Raises:
            TaxomeshRelationError: If source_item_id == target_item_id.
        """
        if self.source_item_id == self.target_item_id:
            raise TaxomeshRelationError(
                f"self-relation not allowed: source_item_id and target_item_id are both {self.source_item_id}"
            )
        return self
