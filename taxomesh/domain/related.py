"""The read model a batch relation read returns."""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from taxomesh.domain.models import Item


@dataclass(frozen=True, slots=True)
class RelatedItems:
    """The items related to one queried item, grouped by relation type.

    One value of the mapping ``service.items.get_many_related`` returns, under the same
    ``item_id`` it carries. Frozen and slotted, because it is a read model and not an entity: a
    standard dataclass and not a Pydantic model, for the same reason as
    :class:`~taxomesh.domain.info.RepositoryInfo`.

    Attributes:
        item_id: The queried item.
        by_type: The related items keyed by relation type, as stored — always lowercase. Each
            group is a tuple, in the order the read resolved it in.

    Example::

        related = service.items.get_many_related([item_a.item_id])[item_a.item_id]
        related.of_type("related_to")  # (item_b,)
        related.relation_types  # ("related_to",)
    """

    item_id: UUID
    by_type: Mapping[str, Sequence[Item]]

    def of_type(self, relation_type: str) -> Sequence[Item]:
        """Return the items related under one relation type.

        Args:
            relation_type: The relation type. Case and surrounding whitespace are ignored, as
                everywhere else a relation type is accepted.

        Returns:
            That type's items in resolution order, empty when there are none of that type.
        """
        return self.by_type.get(relation_type.strip().lower(), ())

    @property
    def relation_types(self) -> Sequence[str]:
        """The relation types present, sorted."""
        return tuple(sorted(self.by_type))

    def __iter__(self) -> Iterator[Item]:
        """Yield each related item once, by relation type and then in resolution order.

        An item related under several types is yielded at its first occurrence only;
        :meth:`of_type` is the per-type view.
        """
        seen: set[UUID] = set()
        for relation_type in self.relation_types:
            for item in self.by_type[relation_type]:
                if item.item_id not in seen:
                    seen.add(item.item_id)
                    yield item

    def __len__(self) -> int:
        """Return the number of distinct related items — what iteration yields."""
        return len({item.item_id for items in self.by_type.values() for item in items})
