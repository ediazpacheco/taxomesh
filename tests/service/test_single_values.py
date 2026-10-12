"""A lookup asked about one key takes the key itself, as well as a collection of keys.

Each batch lookup — ``get_many``, ``get_many_by_external_id`` and ``get_many_related`` — and the
relation-type filter of the three relation reads take one value as a one-item collection, as
``str.startswith`` takes one prefix or a tuple of them. A string is one value, never the
collection of its letters, and a row is one value, never the collection of its fields. One value
and the one-item collection holding it share a cache entry. ``reorder`` keeps its sequence: one
row is no order.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from tests.service.conftest import CountedService


@dataclass(frozen=True, slots=True)
class World:
    """Rows whose external ids share letters: ``"ab"`` would read as ``"a"`` and ``"b"``."""

    music: Category
    jazz: Category
    song: Item
    tune: Item
    live: Tag


def build(service: TaxomeshService) -> World:
    music = service.categories.create("Music", external_id="ab")
    jazz = service.categories.create("Jazz", external_id="a")
    song = service.items.create("Song", external_id="ab")
    tune = service.items.create("Tune", external_id="a")
    live = service.tags.create("live")
    service.items.relate(song, tune, "covers")
    return World(music=music, jazz=jazz, song=song, tune=tune, live=live)


# Any: these calls pass what the annotations refuse, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


def type_name(value: object) -> str:
    """Name a parametrized case by the type of its value."""
    return type(value).__name__


class TestGetManyTakesOneRow:
    """``get_many(row)`` and ``get_many(uuid)`` answer as ``get_many([row])``."""

    def test_categories(self, service: TaxomeshService) -> None:
        w = build(service)
        for key in (w.music, w.music.category_id):
            assert (
                service.categories.get_many(key)
                == service.categories.get_many([key])
                == {w.music.category_id: w.music}
            )

    def test_items(self, service: TaxomeshService) -> None:
        w = build(service)
        for key in (w.song, w.song.item_id):
            assert service.items.get_many(key) == service.items.get_many([key]) == {w.song.item_id: w.song}

    def test_tags(self, service: TaxomeshService) -> None:
        w = build(service)
        for key in (w.live, w.live.tag_id):
            assert service.tags.get_many(key) == service.tags.get_many([key]) == {w.live.tag_id: w.live}

    def test_get_many_related(self, service: TaxomeshService) -> None:
        w = build(service)
        for key in (w.song, w.song.item_id):
            one = service.items.get_many_related(key)
            assert one == service.items.get_many_related([key])
            assert one[w.song.item_id].of_type("covers") == (w.tune,)


class TestGetManyByExternalIdTakesOneId:
    """One external id is a key, never the collection of its letters or digits."""

    def test_a_string_is_one_id_for_categories(self, service: TaxomeshService) -> None:
        w = build(service)
        assert service.categories.get_many_by_external_id("ab") == {"ab": w.music}

    def test_a_string_is_one_id_for_items(self, service: TaxomeshService) -> None:
        w = build(service)
        assert service.items.get_many_by_external_id("ab") == {"ab": w.song}

    def test_an_integer_is_one_id(self, service: TaxomeshService) -> None:
        category = service.categories.create("Answer", external_id=42)
        item = service.items.create("Answer", external_id=42)
        assert service.categories.get_many_by_external_id(42) == {"42": category}
        assert service.items.get_many_by_external_id(42) == {"42": item}

    def test_none_is_one_id_that_matches_nothing(self, service: TaxomeshService) -> None:
        build(service)
        assert service.categories.get_many_by_external_id(None) == {}
        assert service.items.get_many_by_external_id(None) == {}

    @pytest.mark.parametrize("raw", [b"ab", bytearray(b"ab"), memoryview(b"ab")], ids=type_name)
    def test_bytes_are_the_wrong_type(self, service: TaxomeshService, raw: bytes | bytearray | memoryview) -> None:
        """Bytes of any kind are integers, which would be looked up as ``"97"`` and ``"98"``."""
        build(service)
        with pytest.raises(TypeError):
            service.categories.get_many_by_external_id(untyped(raw))
        with pytest.raises(TypeError):
            service.items.get_many_by_external_id(untyped(raw))


class TestRelationTypesTakeOneType:
    """``relation_types="covers"`` reads as ``["covers"]``."""

    def test_list_relations(self, service: TaxomeshService) -> None:
        w = build(service)
        one = service.items.list_relations(w.song, relation_types="covers")
        assert one == service.items.list_relations(w.song, relation_types=["covers"])
        assert [link.target_item_id for link in one] == [w.tune.item_id]

    def test_list_related(self, service: TaxomeshService) -> None:
        w = build(service)
        assert service.items.list_related(w.song, relation_types="Covers ") == (w.tune,)

    def test_get_many_related(self, service: TaxomeshService) -> None:
        w = build(service)
        found = service.items.get_many_related([w.song], relation_types="covers")
        assert found[w.song.item_id].of_type("covers") == (w.tune,)

    def test_the_empty_string_is_one_type_that_matches_nothing(self, service: TaxomeshService) -> None:
        """``""`` is one type, as ``[""]`` is, not the empty collection that means every type."""
        w = build(service)
        assert service.items.list_relations(w.song, relation_types="") == ()
        assert service.items.list_related(w.song, relation_types="") == ()


class TestOneValueSharesTheCacheEntry:
    """One value and the one-item collection holding it are one cached read."""

    def test_by_external_id(self, counting_service: CountedService) -> None:
        service = counting_service.service
        build(service)
        counting_service.cold()
        service.items.get_many_by_external_id(["ab"])
        counting_service.reads.reset()
        service.items.get_many_by_external_id("ab")
        assert counting_service.reads.total == 0

    def test_relation_types(self, counting_service: CountedService) -> None:
        service = counting_service.service
        w = build(service)
        counting_service.cold()
        service.items.list_relations(w.song, relation_types=["covers"])
        service.items.list_related(w.song, relation_types=["covers"])
        service.items.get_many_related([w.song], relation_types=["covers"])
        counting_service.reads.reset()
        service.items.list_relations(w.song, relation_types="covers")
        service.items.list_related(w.song, relation_types="covers")
        service.items.get_many_related(w.song, relation_types="covers")
        assert counting_service.reads.total == 0


def test_reorder_keeps_its_sequence(service: TaxomeshService) -> None:
    """One row is no order, so ``reorder`` refuses it as the wrong type."""
    w = build(service)
    with pytest.raises(TypeError):
        service.categories.reorder(None, untyped(w.music))
