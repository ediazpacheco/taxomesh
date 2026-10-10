"""ItemRelationLink domain model."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from taxomesh.domain.constants import RELATION_TYPE_MAX_LENGTH
from taxomesh.domain.models.base import ModelBase
from taxomesh.domain.types import FrozenDict, Metadata
from taxomesh.exceptions import TaxomeshRelationError


class ItemRelationLink(ModelBase):
    """A relation: a directed, typed link from a source item to a target item.

    The triple ``(source_item_id, target_item_id, relation_type)`` is the key of a relation: two
    links with the same triple are the same link. The model strips ``relation_type`` and puts it in
    lowercase, so the caller can give it in any case.

    Attributes:
        source_item_id: The item the relation goes from.
        target_item_id: The item the relation goes to; never the source.
        relation_type: Your own label for the relation, at most ``RELATION_TYPE_MAX_LENGTH``
            characters, stored stripped and in lowercase.
        sort_index: The relation's position among the item's relations, lower first.
        metadata: Plain JSON, frozen all the way down.
    """

    source_item_id: UUID
    target_item_id: UUID
    relation_type: Annotated[str, Field(max_length=RELATION_TYPE_MAX_LENGTH)]
    sort_index: int = 0
    metadata: Metadata = Field(default_factory=FrozenDict)

    @field_validator("relation_type", mode="before")
    @classmethod
    def _normalise_relation_type(cls, v: object) -> str:
        """Strip the relation type and put it in lowercase, before the field is validated.

        Args:
            v: The value given for the field.

        Returns:
            The stripped text, in lowercase.

        Raises:
            TypeError: If the value is not a string.
            TaxomeshRelationError: If the string is empty after stripping whitespace.
        """
        if not isinstance(v, str):
            raise TypeError(f"relation_type must be a str, not {type(v).__name__}")
        normalised = v.strip().lower()
        if not normalised:
            raise TaxomeshRelationError("relation_type must not be empty or whitespace-only")
        return normalised

    @model_validator(mode="after")
    def _reject_self_relation(self) -> "ItemRelationLink":
        """Refuse a relation from an item to itself.

        Returns:
            This link, when it is valid.

        Raises:
            TaxomeshRelationError: If source_item_id == target_item_id.
        """
        if self.source_item_id == self.target_item_id:
            raise TaxomeshRelationError(
                "An item cannot be related to itself: source_item_id and target_item_id are both "
                f"{self.source_item_id}"
            )
        return self
