"""A subject or a filter naming a row that is not stored raises that row's not-found error.

Every member that takes one checks it, the relation reads and ``unrelate`` included. The keys a
``get*`` member is asked about are not subjects: their absence is a miss, so
``get_many_related([unknown])`` answers ``{}``.

The check costs a read only where no link proves the row stored: a stored link names only stored
rows. A relation read of an item with no relations reads the item once, and not at all once its row
is cached; a relation read that finds a link, and an ``unrelate`` that removes one, read nothing
more.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshTagNotFoundError,
)
from tests.service.conftest import CountedService


@dataclass(frozen=True, slots=True)
class Rows:
    """Stored rows to pair with an unknown identifier."""

    music: Category
    jazz: Category
    song: Item
    tune: Item
    live: Tag


def build(service: TaxomeshService) -> Rows:
    """Store Jazz under Music, Song placed in Jazz and tagged, and an unplaced Tune."""
    music = service.categories.create("Music")
    jazz = service.categories.create("Jazz")
    service.categories.add_parent(jazz.category_id, music.category_id)
    song = service.items.create("Song")
    tune = service.items.create("Tune")
    service.items.place_in(song.item_id, jazz.category_id)
    live = service.tags.create("live")
    service.items.tag(song.item_id, live.tag_id)
    return Rows(music=music, jazz=jazz, song=song, tune=tune, live=live)


type Call = Callable[[TaxomeshService, Rows, UUID], object]

CATEGORY: type[TaxomeshNotFoundError] = TaxomeshCategoryNotFoundError
ITEM: type[TaxomeshNotFoundError] = TaxomeshItemNotFoundError
TAG: type[TaxomeshNotFoundError] = TaxomeshTagNotFoundError

CALLS: list[tuple[str, Call, type[TaxomeshNotFoundError]]] = [
    ("categories[x]", lambda s, r, x: s.categories[x], CATEGORY),
    ("categories.delete(x)", lambda s, r, x: s.categories.delete(x), CATEGORY),
    ("categories.update(x)", lambda s, r, x: s.categories.update(x, name="Bop"), CATEGORY),
    ("categories.list(parent=x)", lambda s, r, x: s.categories.list(parent=x), CATEGORY),
    ("categories.list(item=x)", lambda s, r, x: s.categories.list(item=x), ITEM),
    ("categories.search(parent=x)", lambda s, r, x: s.categories.search("jazz", parent=x), CATEGORY),
    ("categories.search('', parent=x)", lambda s, r, x: s.categories.search(" ", parent=x), CATEGORY),
    ("categories.add_parent(x, parent)", lambda s, r, x: s.categories.add_parent(x, r.music), CATEGORY),
    ("categories.add_parent(category, x)", lambda s, r, x: s.categories.add_parent(r.jazz, x), CATEGORY),
    ("categories.remove_parent(x, parent)", lambda s, r, x: s.categories.remove_parent(x, r.music), CATEGORY),
    ("categories.remove_parent(category, x)", lambda s, r, x: s.categories.remove_parent(r.jazz, x), CATEGORY),
    ("categories.move(x)", lambda s, r, x: s.categories.move(x, from_parent=None, to_parent=r.music), CATEGORY),
    (
        "categories.move(from_parent=x)",
        lambda s, r, x: s.categories.move(r.jazz, from_parent=x, to_parent=r.music),
        CATEGORY,
    ),
    (
        "categories.move(to_parent=x)",
        lambda s, r, x: s.categories.move(r.jazz, from_parent=None, to_parent=x),
        CATEGORY,
    ),
    ("categories.reorder(x)", lambda s, r, x: s.categories.reorder(x, []), CATEGORY),
    ("graph(root=x)", lambda s, r, x: s.graph(root=x), CATEGORY),
    ("items[x]", lambda s, r, x: s.items[x], ITEM),
    ("items.delete(x)", lambda s, r, x: s.items.delete(x), ITEM),
    ("items.update(x)", lambda s, r, x: s.items.update(x, name="Air"), ITEM),
    ("items.list(category=x)", lambda s, r, x: s.items.list(category=x), CATEGORY),
    ("items.list(recursive)", lambda s, r, x: s.items.list(category=x, recursive=True), CATEGORY),
    ("items.list(tag=x)", lambda s, r, x: s.items.list(tag=x), TAG),
    ("items.search(category=x)", lambda s, r, x: s.items.search("song", category=x), CATEGORY),
    ("items.place_in(x, category)", lambda s, r, x: s.items.place_in(x, r.jazz), ITEM),
    ("items.place_in(item, x)", lambda s, r, x: s.items.place_in(r.song, x), CATEGORY),
    ("items.remove_from(x, category)", lambda s, r, x: s.items.remove_from(x, r.jazz), ITEM),
    ("items.remove_from(item, x)", lambda s, r, x: s.items.remove_from(r.song, x), CATEGORY),
    ("items.move(x)", lambda s, r, x: s.items.move(x, from_category=r.jazz, to_category=r.music), ITEM),
    (
        "items.move(from_category=x)",
        lambda s, r, x: s.items.move(r.song, from_category=x, to_category=r.music),
        CATEGORY,
    ),
    ("items.move(to_category=x)", lambda s, r, x: s.items.move(r.song, from_category=r.jazz, to_category=x), CATEGORY),
    ("items.reorder(x)", lambda s, r, x: s.items.reorder(x, []), CATEGORY),
    ("items.tag(x, tag)", lambda s, r, x: s.items.tag(x, r.live), ITEM),
    ("items.tag(item, x)", lambda s, r, x: s.items.tag(r.tune, x), TAG),
    ("items.untag(x, tag)", lambda s, r, x: s.items.untag(x, r.live), ITEM),
    ("items.untag(item, x)", lambda s, r, x: s.items.untag(r.song, x), TAG),
    ("items.relate(x, target)", lambda s, r, x: s.items.relate(x, r.tune, "covers"), ITEM),
    ("items.relate(source, x)", lambda s, r, x: s.items.relate(r.song, x, "covers"), ITEM),
    ("items.unrelate(x, target)", lambda s, r, x: s.items.unrelate(x, r.tune, "covers"), ITEM),
    ("items.unrelate(source, x)", lambda s, r, x: s.items.unrelate(r.song, x, "covers"), ITEM),
    ("items.list_relations(x)", lambda s, r, x: s.items.list_relations(x), ITEM),
    ("items.list_related(x)", lambda s, r, x: s.items.list_related(x), ITEM),
    ("tags[x]", lambda s, r, x: s.tags[x], TAG),
    ("tags.delete(x)", lambda s, r, x: s.tags.delete(x), TAG),
    ("tags.update(x)", lambda s, r, x: s.tags.update(x, name="studio"), TAG),
    ("tags.list(item=x)", lambda s, r, x: s.tags.list(item=x), ITEM),
]
CALL_IDS = [label for label, _, _ in CALLS]


@pytest.mark.parametrize(("label", "call", "error"), CALLS, ids=CALL_IDS)
def test_an_unknown_row_raises_its_own_not_found_error(
    service: TaxomeshService, label: str, call: Call, error: type[TaxomeshNotFoundError]
) -> None:
    rows = build(service)
    unknown = uuid4()

    with pytest.raises(error) as caught:
        call(service, rows, unknown)

    assert str(unknown) in str(caught.value)


def test_a_key_asked_of_a_lookup_is_not_a_subject(service: TaxomeshService) -> None:
    build(service)

    assert service.items.get_many_related([uuid4()]) == {}


class TestTheCheckReadsOnlyWhatNoLinkProves:
    """The relation reads and ``unrelate`` read a subject only where no link proves it stored."""

    def test_an_item_without_relations_is_read_once(self, counting_service: CountedService) -> None:
        service = counting_service.service
        rows = build(service)

        for read in (service.items.list_relations, service.items.list_related):
            counting_service.cold()
            read(rows.tune)
            assert counting_service.reads.calls == ["list_item_relation_links", "find_item"]

    def test_and_not_at_all_once_its_row_is_cached(self, counting_service: CountedService) -> None:
        service = counting_service.service
        rows = build(service)

        for read in (service.items.list_relations, service.items.list_related):
            counting_service.cold()
            service.items[rows.tune]
            counting_service.reads.reset()
            read(rows.tune)
            assert counting_service.reads.calls == ["list_item_relation_links"]

    def test_an_item_with_a_relation_is_not_read(self, counting_service: CountedService) -> None:
        service = counting_service.service
        rows = build(service)
        service.items.relate(rows.song, rows.tune, "covers")

        counting_service.cold()
        service.items.list_relations(rows.song)
        assert counting_service.reads.calls == ["list_item_relation_links"]
        counting_service.cold()
        service.items.list_related(rows.song)
        assert counting_service.reads.calls == ["list_item_relation_links", "map_items_by_id"]

    def test_an_unrelate_that_removes_reads_nothing(self, counting_service: CountedService) -> None:
        service = counting_service.service
        rows = build(service)
        service.items.relate(rows.song, rows.tune, "covers")

        counting_service.cold()
        service.items.unrelate(rows.song, rows.tune, "covers")

        assert counting_service.reads.total == 0

    def test_an_unrelate_that_removes_nothing_reads_both_ends(self, counting_service: CountedService) -> None:
        service = counting_service.service
        rows = build(service)

        counting_service.cold()
        service.items.unrelate(rows.song, rows.tune, "covers")

        assert counting_service.reads.calls == ["find_item", "find_item"]
