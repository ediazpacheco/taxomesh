"""The batch relation read model.

``get_many_related`` answers a mapping keyed by the queried item. Each value is a
:class:`RelatedItems`, a frozen, slotted read model grouping that item's related items by
relation type.

Three behaviours these tests pin, because the class's shape does not show them:

* ``of_type`` normalises its argument, as every other relation-type input already does, so a
  caller never needs to know that relation types are stored lowercase.
* Iterating yields each related item **once**, even when it is related under several types.
  The per-type view is ``of_type``.
* Calls that differ only in identifier order, duplicates, or relation-type case and whitespace
  read **one** cache entry, on every backend.
"""

import dataclasses
import inspect
from collections.abc import Callable, Collection
from uuid import uuid4

import pytest

from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item
from taxomesh.domain.related import RelatedItems
from tests.service.conftest import CountedService

ALPHA = "alpha"
BETA = "beta"


def _sample() -> tuple[RelatedItems, Item, Item, Item]:
    """A view where ``item_b`` is related under both types, built with the types out of order."""
    item_a, item_b, item_c = Item(name="A"), Item(name="B"), Item(name="C")
    related = RelatedItems(item_id=uuid4(), by_type={BETA: [item_b, item_c], ALPHA: [item_b, item_a]})
    return related, item_a, item_b, item_c


class TestItIsAReadModel:
    """Immutable and slotted, as every read model is."""

    def test_a_field_cannot_be_reassigned(self) -> None:
        """Frozen: the caller holds a snapshot, and a write to it would persist nowhere."""
        related, *_ = _sample()

        with pytest.raises(dataclasses.FrozenInstanceError):
            related.item_id = uuid4()  # type: ignore[misc]

    def test_it_is_slotted(self) -> None:
        """Slotted, asserted structurally — see ``tests/domain/test_info_models.py`` for why."""
        related, *_ = _sample()

        assert RelatedItems.__slots__ == ("item_id", "by_type")
        assert not hasattr(related, "__dict__")


class TestReadingIt:
    """What a caller can ask of one queried item's related items."""

    def test_of_type_returns_that_types_items_in_order(self) -> None:
        """One relation type's items, in the order the read resolved them."""
        related, item_a, item_b, _ = _sample()

        assert related.of_type(ALPHA) == [item_b, item_a]

    def test_of_type_normalises_the_relation_type(self) -> None:
        """Case and surrounding whitespace do not matter, as for ``relate`` and ``unrelate``."""
        related, item_a, item_b, _ = _sample()

        assert related.of_type(" Alpha ") == [item_b, item_a]

    def test_of_type_answers_empty_for_an_absent_type(self) -> None:
        """An absent type is an empty answer, not an error — this is not a subscript."""
        related, *_ = _sample()

        assert related.of_type("gamma") == ()

    def test_relation_types_are_sorted(self) -> None:
        """Sorted whatever order the groups were built in, so the order is deterministic."""
        related, *_ = _sample()

        assert related.relation_types == (ALPHA, BETA)

    def test_iterating_yields_each_item_once(self) -> None:
        """Types in ``relation_types`` order, each group in its own order, first occurrence wins."""
        related, item_a, item_b, item_c = _sample()

        assert list(related) == [item_b, item_a, item_c]

    def test_length_counts_distinct_items(self) -> None:
        """``len`` agrees with iteration: an item related under two types counts once."""
        related, *_ = _sample()

        assert len(related) == 3


class TestTheCollectionReturnsIt:
    """``svc.items.get_many_related`` maps each queried item to its ``RelatedItems``."""

    def test_each_value_describes_its_key(self, service: TaxomeshService) -> None:
        """The mapping is keyed by the queried item, and each value carries that same id."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        item_c = service.items.create("C")
        service.items.relate(item_a.item_id, item_b.item_id, ALPHA)
        service.items.relate(item_a.item_id, item_c.item_id, BETA)

        found = service.items.get_many_related([item_a.item_id])

        assert found == {
            item_a.item_id: RelatedItems(item_id=item_a.item_id, by_type={ALPHA: (item_b,), BETA: (item_c,)})
        }

    def test_an_item_related_under_two_types_is_one_related_item(self, service: TaxomeshService) -> None:
        """Both types are listed, and the item behind them is counted once."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        service.items.relate(item_a.item_id, item_b.item_id, BETA)
        service.items.relate(item_a.item_id, item_b.item_id, ALPHA)

        related = service.items.get_many_related([item_a.item_id])[item_a.item_id]

        assert related.relation_types == (ALPHA, BETA)
        assert list(related) == [item_b]
        assert len(related) == 1

    def test_it_carries_what_the_flat_read_returns(self, service: TaxomeshService) -> None:
        """Parity with ``list_related``, one type at a time, over ``"both"``, the richest direction."""
        item_a = service.items.create("A")
        item_b = service.items.create("B")
        item_c = service.items.create("C")
        service.items.relate(item_a.item_id, item_b.item_id, ALPHA)
        service.items.relate(item_c.item_id, item_a.item_id, BETA)

        related = service.items.get_many_related([item_a.item_id], direction="both")[item_a.item_id]

        assert related.relation_types == (ALPHA, BETA)
        assert dict(related.by_type) == {
            relation_type: service.items.list_related(item_a.item_id, relation_types=[relation_type], direction="both")
            for relation_type in related.relation_types
        }

    def test_an_item_without_relations_is_absent(self, service: TaxomeshService) -> None:
        """No relations means no key, never a ``RelatedItems`` with nothing in it."""
        item_a = service.items.create("A")

        assert service.items.get_many_related([item_a.item_id]) == {}
        assert service.items.get_many_related([]) == {}


class TestOneCacheEntry:
    """Spellings differing only in id order, duplicates or relation-type case share the memoized read."""

    def test_either_read_serves_the_other(self, counting_service: CountedService) -> None:
        """Warmed by one spelling, the other costs zero reads, both ways — a hit asserted, not a value."""
        svc = counting_service.service
        item_a = svc.items.create("A")
        item_b = svc.items.create("B")
        svc.items.relate(item_a.item_id, item_b.item_id, ALPHA)
        ids = [item_a.item_id, item_b.item_id]
        respelled = [item_b.item_id, item_a.item_id, item_a.item_id]

        counting_service.cold()
        svc.items.get_many_related(ids, relation_types=[ALPHA])
        assert counting_service.reads.total > 0
        counting_service.reads.reset()
        svc.items.get_many_related(respelled, relation_types=[" Alpha "])
        assert counting_service.reads.total == 0

        counting_service.cold()
        svc.items.get_many_related(respelled, relation_types=[" Alpha "])
        assert counting_service.reads.total > 0
        counting_service.reads.reset()
        svc.items.get_many_related(ids, relation_types=[ALPHA])
        assert counting_service.reads.total == 0


# The three relation reads, each answering with the names on the far end of item A's relations.
type TypedRead = Callable[[TaxomeshService, Item, Collection[str] | None], list[str]]


def _names_via_list_relations(service: TaxomeshService, item: Item, types: Collection[str] | None) -> list[str]:
    targets = [link.target_item_id for link in service.items.list_relations(item, relation_types=types)]
    return [service.items[target].name for target in targets]


def _names_via_list_related(service: TaxomeshService, item: Item, types: Collection[str] | None) -> list[str]:
    return [related.name for related in service.items.list_related(item, relation_types=types)]


def _names_via_get_many_related(service: TaxomeshService, item: Item, types: Collection[str] | None) -> list[str]:
    found = service.items.get_many_related([item], relation_types=types).get(item.item_id)
    return [] if found is None else [related.name for related in found]


TYPED_READS: list[tuple[str, TypedRead]] = [
    ("list_relations", _names_via_list_relations),
    ("list_related", _names_via_list_related),
    ("get_many_related", _names_via_get_many_related),
]


@pytest.mark.parametrize(("name", "read"), TYPED_READS, ids=[name for name, _ in TYPED_READS])
class TestRelationTypes:
    """All three relation reads filter by type through ``relation_types``, and only through it."""

    @staticmethod
    def _source(service: TaxomeshService) -> Item:
        """Item A, related to B as alpha, to C as beta and to D as gamma, in that order."""
        source = service.items.create("A")
        for index, (name, relation_type) in enumerate([("B", ALPHA), ("C", BETA), ("D", "gamma")]):
            service.items.relate(source, service.items.create(name), relation_type, sort_index=index)
        return source

    def test_several_types_stripped_and_lowercased(self, service: TaxomeshService, name: str, read: TypedRead) -> None:
        source = self._source(service)

        assert sorted(read(service, source, [" Alpha ", "BETA"])) == ["B", "C"]

    def test_none_or_an_empty_collection_means_every_type(
        self, service: TaxomeshService, name: str, read: TypedRead
    ) -> None:
        source = self._source(service)

        assert sorted(read(service, source, None)) == ["B", "C", "D"]
        assert sorted(read(service, source, [])) == ["B", "C", "D"]

    def test_a_type_no_relation_carries_selects_nothing(
        self, service: TaxomeshService, name: str, read: TypedRead
    ) -> None:
        source = self._source(service)

        assert read(service, source, ["delta"]) == []


@pytest.mark.parametrize(
    "member", [ItemCollection.list_relations, ItemCollection.list_related, ItemCollection.get_many_related]
)
def test_no_relation_read_takes_a_single_type(member: Callable[..., object]) -> None:
    """``relation_types`` is the one filter; ``relate`` and ``unrelate`` keep the singular, naming one type."""
    parameters = inspect.signature(member).parameters

    assert "relation_type" not in parameters
    assert parameters["relation_types"].default is None


@pytest.mark.parametrize(
    "read",
    [
        lambda s, item, types: s.items.list_relations(item, relation_types=types),
        lambda s, item, types: s.items.list_related(item, relation_types=types),
    ],
    ids=["list_relations", "list_related"],
)
def test_spellings_of_one_filter_share_one_cache_entry(
    counting_service: CountedService, read: Callable[[TaxomeshService, Item, list[str]], object]
) -> None:
    """Types differing only in case, whitespace, order or repetition are one cache entry."""
    svc = counting_service.service
    item_a = svc.items.create("A")
    svc.items.relate(item_a, svc.items.create("B"), ALPHA)
    svc.items.relate(item_a, svc.items.create("C"), BETA)

    counting_service.cold()
    read(svc, item_a, [ALPHA, BETA])
    assert counting_service.reads.total > 0
    counting_service.reads.reset()
    read(svc, item_a, [" Beta ", "ALPHA", "alpha"])
    assert counting_service.reads.total == 0
