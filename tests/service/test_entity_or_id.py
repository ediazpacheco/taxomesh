"""A row and its identifier address the same row, wherever a parameter names one.

Every parameter naming a category, an item or a tag takes the row itself or its ``UUID``. Of a row
passed in, only its identifier is read, so a held row that is stale, or one never stored, addresses
what is stored under that identifier. The conversion happens before any cached read, so the two
spellings share one cache entry. Anything that is neither a row of the right kind nor a ``UUID``
raises ``TypeError`` before storage is read.

The parameters are annotated here as ``Category | UUID`` and its siblings, which is what
``CategoryRef``, ``ItemRef`` and ``TagRef`` stand for.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError, TaxomeshTagNotFoundError
from tests.service.conftest import CountedService


@dataclass(frozen=True, slots=True)
class World:
    """A small taxonomy: Jazz under Music, Rock at the top level, two items in Jazz."""

    music: Category
    jazz: Category
    rock: Category
    song: Item
    tune: Item
    live: Tag


def build(service: TaxomeshService) -> World:
    """Store the world, addressing every row by identifier, and return the rows as stored."""
    music = service.categories.create("Music")
    jazz = service.categories.create("Jazz")
    rock = service.categories.create("Rock")
    service.categories.add_parent(jazz.category_id, music.category_id)
    song = service.items.create("Song")
    tune = service.items.create("Tune")
    service.items.place_in(song.item_id, jazz.category_id)
    service.items.place_in(tune.item_id, jazz.category_id, sort_index=1)
    live = service.tags.create("live")
    service.items.tag(song.item_id, live.tag_id)
    service.items.relate(song.item_id, tune.item_id, "covers")
    return World(music=music, jazz=jazz, rock=rock, song=song, tune=tune, live=live)


def cat(row: Category, by_row: bool) -> Category | UUID:
    """The category itself, or its identifier."""
    return row if by_row else row.category_id


def itm(row: Item, by_row: bool) -> Item | UUID:
    """The item itself, or its identifier."""
    return row if by_row else row.item_id


def tg(row: Tag, by_row: bool) -> Tag | UUID:
    """The tag itself, or its identifier."""
    return row if by_row else row.tag_id


type Read = Callable[[TaxomeshService, World, bool], object]

READS: list[tuple[str, Read]] = [
    ("categories[x]", lambda s, w, r: s.categories[cat(w.jazz, r)]),
    ("categories.get(x)", lambda s, w, r: s.categories.get(cat(w.jazz, r))),
    ("x in categories", lambda s, w, r: cat(w.jazz, r) in s.categories),
    ("categories.get_many", lambda s, w, r: s.categories.get_many([cat(w.jazz, r), cat(w.rock, r)])),
    ("categories.list(parent=)", lambda s, w, r: s.categories.list(parent=cat(w.music, r))),
    ("categories.list(item=)", lambda s, w, r: s.categories.list(item=itm(w.song, r))),
    ("categories.search(parent=)", lambda s, w, r: s.categories.search("jazz", parent=cat(w.music, r))),
    ("items[x]", lambda s, w, r: s.items[itm(w.song, r)]),
    ("items.get(x)", lambda s, w, r: s.items.get(itm(w.song, r))),
    ("x in items", lambda s, w, r: itm(w.song, r) in s.items),
    ("items.get_many", lambda s, w, r: s.items.get_many([itm(w.song, r), itm(w.tune, r)])),
    ("items.list(category=)", lambda s, w, r: s.items.list(category=cat(w.jazz, r))),
    ("items.list(recursive)", lambda s, w, r: s.items.list(category=cat(w.music, r), recursive=True)),
    ("items.list(tag=)", lambda s, w, r: s.items.list(tag=tg(w.live, r))),
    ("items.search(category=)", lambda s, w, r: s.items.search("song", category=cat(w.jazz, r))),
    ("items.list_relations", lambda s, w, r: s.items.list_relations(itm(w.song, r))),
    ("items.list_related", lambda s, w, r: s.items.list_related(itm(w.song, r))),
    ("items.get_many_related", lambda s, w, r: s.items.get_many_related([itm(w.song, r)])),
    ("tags[x]", lambda s, w, r: s.tags[tg(w.live, r)]),
    ("tags.get(x)", lambda s, w, r: s.tags.get(tg(w.live, r))),
    ("x in tags", lambda s, w, r: tg(w.live, r) in s.tags),
    ("tags.get_many", lambda s, w, r: s.tags.get_many([tg(w.live, r)])),
    ("tags.list(item=)", lambda s, w, r: s.tags.list(item=itm(w.song, r))),
    ("graph(root=)", lambda s, w, r: [n.category for n in s.graph(root=cat(w.music, r)).walk()]),
    ("graph[x]", lambda s, w, r: s.graph()[cat(w.jazz, r)].category),
    ("graph.get(x)", lambda s, w, r: repr(s.graph().get(cat(w.jazz, r)))),
    ("x in graph", lambda s, w, r: cat(w.jazz, r) in s.graph()),
    ("graph[x].descendants()", lambda s, w, r: [n.category for n in s.graph()[cat(w.music, r)].descendants()]),
]
READ_IDS = [label for label, _ in READS]

# The reads behind a cache. A tag's subscript reads storage every time, so it has no entry to share.
CACHED: list[tuple[str, Read]] = [
    (label, read)
    for label, read in READS
    if label
    in {
        "categories[x]",
        "categories.get(x)",
        "x in categories",
        "categories.get_many",
        "categories.list(parent=)",
        "categories.list(item=)",
        "items[x]",
        "items.get(x)",
        "x in items",
        "items.get_many",
        "items.list(category=)",
        "items.list(tag=)",
        "items.list_relations",
        "items.list_related",
        "items.get_many_related",
        "tags.get_many",
        "tags.list(item=)",
        "graph(root=)",
    }
]
CACHED_IDS = [label for label, _ in CACHED]


@pytest.mark.parametrize(("label", "read"), READS, ids=READ_IDS)
def test_a_read_answers_the_same_for_the_row_and_its_identifier(
    service: TaxomeshService, label: str, read: Read
) -> None:
    world = build(service)

    by_id = read(service, world, False)

    assert read(service, world, True) == by_id
    assert by_id not in ((), {}, [], None, False), f"{label} found nothing, so the comparison proves nothing"


@pytest.mark.parametrize(("label", "read"), CACHED, ids=CACHED_IDS)
def test_the_row_and_its_identifier_share_one_cache_entry(
    counting_service: CountedService, label: str, read: Read
) -> None:
    service = counting_service.service
    world = build(service)

    for warm_by_row in (True, False):
        counting_service.cold()
        read(service, world, warm_by_row)
        assert counting_service.reads.total > 0
        counting_service.reads.reset()
        read(service, world, not warm_by_row)
        assert counting_service.reads.total == 0, f"{label}: the other spelling read storage again"


class TestAWriteTakesTheRow:
    """Each write given rows changes what the same write given identifiers would."""

    def test_add_and_remove_a_parent(self, service: TaxomeshService) -> None:
        w = build(service)

        service.categories.add_parent(w.rock, w.music)
        assert w.rock in service.categories.list(parent=w.music)
        service.categories.remove_parent(w.rock, w.music)
        assert w.rock in service.categories.roots()

    def test_move_a_category(self, service: TaxomeshService) -> None:
        w = build(service)
        service.categories.add_parent(w.rock, w.music)

        service.categories.move(w.jazz, from_parent=w.music, to_parent=w.music, before=w.rock)

        assert [c.name for c in service.categories.list(parent=w.music)] == ["Jazz", "Rock"]

    def test_reorder_categories(self, service: TaxomeshService) -> None:
        w = build(service)
        service.categories.add_parent(w.rock, w.music)

        service.categories.reorder(w.music, [w.rock, w.jazz])
        service.categories.reorder(None, service.categories.roots())

        assert [c.name for c in service.categories.list(parent=w.music)] == ["Rock", "Jazz"]

    def test_update_and_delete_a_category(self, service: TaxomeshService) -> None:
        w = build(service)

        assert service.categories.update(w.rock, name="Punk").name == "Punk"
        service.categories.delete(w.rock)
        assert w.rock.category_id not in service.categories
        del service.categories[w.jazz]
        assert w.jazz.category_id not in service.categories

    def test_place_move_and_remove_an_item(self, service: TaxomeshService) -> None:
        w = build(service)

        service.items.place_in(w.song, w.rock)
        assert w.song in service.items.list(category=w.rock)
        link = service.items.move(w.tune, from_category=w.jazz, to_category=w.rock, before=w.song)
        assert link.category_id == w.rock.category_id
        assert [i.name for i in service.items.list(category=w.rock)] == ["Tune", "Song"]
        service.items.remove_from(w.song, w.rock)
        assert [i.name for i in service.items.list(category=w.rock)] == ["Tune"]

    def test_reorder_items(self, service: TaxomeshService) -> None:
        w = build(service)

        service.items.reorder(w.jazz, [w.tune, w.song])

        assert [i.name for i in service.items.list(category=w.jazz)] == ["Tune", "Song"]

    def test_tag_and_untag(self, service: TaxomeshService) -> None:
        w = build(service)

        service.items.tag(w.tune, w.live)
        assert w.live in service.tags.list(item=w.tune)
        service.items.untag(w.tune, w.live)
        assert service.tags.list(item=w.tune) == ()

    def test_relate_and_unrelate(self, service: TaxomeshService) -> None:
        w = build(service)

        link = service.items.relate(w.tune, w.song, "samples")
        assert (link.source_item_id, link.target_item_id) == (w.tune.item_id, w.song.item_id)
        service.items.unrelate(w.tune, w.song, "samples")
        assert service.items.list_relations(w.tune) == ()

    def test_update_and_delete_an_item(self, service: TaxomeshService) -> None:
        w = build(service)

        assert service.items.update(w.tune, name="Air").name == "Air"
        service.items.delete(w.tune)
        assert w.tune.item_id not in service.items
        del service.items[w.song]
        assert w.song.item_id not in service.items

    def test_update_and_delete_a_tag(self, service: TaxomeshService) -> None:
        w = build(service)

        assert service.tags.update(w.live, name="studio").name == "studio"
        del service.tags[w.live]
        assert w.live.tag_id not in service.tags


class TestOnlyTheIdentifierIsRead:
    """A row passed in addresses what is stored under its identifier, nothing it carries."""

    def test_a_stale_row_reads_what_is_stored(self, service: TaxomeshService) -> None:
        w = build(service)
        service.categories.update(w.jazz.category_id, name="Bop")
        service.items.update(w.song.item_id, name="Standard")
        service.tags.update(w.live.tag_id, name="studio")

        assert service.categories[w.jazz].name == "Bop"
        assert service.items[w.song].name == "Standard"
        assert service.tags[w.live].name == "studio"

    def test_a_row_never_stored_is_absent(self, service: TaxomeshService) -> None:
        build(service)
        ghost_category = Category(name="Ghost")
        ghost_item = Item(name="Ghost")
        ghost_tag = Tag(name="Ghost")

        assert service.categories.get(ghost_category) is None
        assert ghost_item not in service.items
        assert service.tags.get(ghost_tag) is None
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories[ghost_category]
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items[ghost_item]
        with pytest.raises(TaxomeshTagNotFoundError):
            service.tags[ghost_tag]

    def test_the_root_row_is_absent(self, service: TaxomeshService) -> None:
        root = service.repository.find_category(service._root_id)
        assert root is not None

        assert service.categories.get(root) is None
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.graph(root=root)


# Any: a probe passes what the annotations refuse, as an untyped caller can.
type Probe = Callable[[TaxomeshService, World, Any], object]
type Wrong = Callable[[World], Any]

CATEGORY_FORMS: list[tuple[str, Probe]] = [
    ("categories[x]", lambda s, w, x: s.categories[x]),
    ("categories.get(x)", lambda s, w, x: s.categories.get(x)),
    ("x in categories", lambda s, w, x: x in s.categories),
    ("del categories[x]", lambda s, w, x: s.categories.__delitem__(x)),
    ("categories.delete(x)", lambda s, w, x: s.categories.delete(x)),
    ("categories.get_many([x])", lambda s, w, x: s.categories.get_many([x])),
    ("categories.list(parent=x)", lambda s, w, x: s.categories.list(parent=x)),
    ("categories.search(parent=x)", lambda s, w, x: s.categories.search("jazz", parent=x)),
    ("categories.update(x)", lambda s, w, x: s.categories.update(x, name="Bop")),
    ("categories.add_parent(x, parent)", lambda s, w, x: s.categories.add_parent(x, w.music)),
    ("categories.add_parent(category, x)", lambda s, w, x: s.categories.add_parent(w.rock, x)),
    ("categories.remove_parent(category, x)", lambda s, w, x: s.categories.remove_parent(w.jazz, x)),
    ("categories.move(x)", lambda s, w, x: s.categories.move(x, from_parent=None, to_parent=w.music)),
    ("categories.move(to_parent=x)", lambda s, w, x: s.categories.move(w.rock, from_parent=None, to_parent=x)),
    ("categories.reorder(x, [])", lambda s, w, x: s.categories.reorder(x, [])),
    ("categories.reorder(None, [x])", lambda s, w, x: s.categories.reorder(None, [x])),
    ("items.list(category=x)", lambda s, w, x: s.items.list(category=x)),
    ("items.place_in(item, x)", lambda s, w, x: s.items.place_in(w.tune, x)),
    ("items.move(to_category=x)", lambda s, w, x: s.items.move(w.song, from_category=w.jazz, to_category=x)),
    ("graph(root=x)", lambda s, w, x: s.graph(root=x)),
    ("graph[x]", lambda s, w, x: s.graph()[x]),
    ("graph.get(x)", lambda s, w, x: s.graph().get(x)),
    ("x in graph", lambda s, w, x: x in s.graph()),
]

ITEM_FORMS: list[tuple[str, Probe]] = [
    ("items[x]", lambda s, w, x: s.items[x]),
    ("items.get(x)", lambda s, w, x: s.items.get(x)),
    ("x in items", lambda s, w, x: x in s.items),
    ("del items[x]", lambda s, w, x: s.items.__delitem__(x)),
    ("items.delete(x)", lambda s, w, x: s.items.delete(x)),
    ("items.get_many([x])", lambda s, w, x: s.items.get_many([x])),
    ("items.update(x)", lambda s, w, x: s.items.update(x, name="Air")),
    ("items.place_in(x, category)", lambda s, w, x: s.items.place_in(x, w.rock)),
    ("items.remove_from(x, category)", lambda s, w, x: s.items.remove_from(x, w.jazz)),
    ("items.move(x)", lambda s, w, x: s.items.move(x, from_category=w.jazz, to_category=w.rock)),
    ("items.reorder(category, [x])", lambda s, w, x: s.items.reorder(w.jazz, [x])),
    ("items.tag(x, tag)", lambda s, w, x: s.items.tag(x, w.live)),
    ("items.relate(x, target)", lambda s, w, x: s.items.relate(x, w.tune, "samples")),
    ("items.unrelate(source, x)", lambda s, w, x: s.items.unrelate(w.song, x, "covers")),
    ("items.list_relations(x)", lambda s, w, x: s.items.list_relations(x)),
    ("items.list_related(x)", lambda s, w, x: s.items.list_related(x)),
    ("items.get_many_related([x])", lambda s, w, x: s.items.get_many_related([x])),
    ("categories.list(item=x)", lambda s, w, x: s.categories.list(item=x)),
    ("tags.list(item=x)", lambda s, w, x: s.tags.list(item=x)),
]

TAG_FORMS: list[tuple[str, Probe]] = [
    ("tags[x]", lambda s, w, x: s.tags[x]),
    ("tags.get(x)", lambda s, w, x: s.tags.get(x)),
    ("x in tags", lambda s, w, x: x in s.tags),
    ("del tags[x]", lambda s, w, x: s.tags.__delitem__(x)),
    ("tags.delete(x)", lambda s, w, x: s.tags.delete(x)),
    ("tags.get_many([x])", lambda s, w, x: s.tags.get_many([x])),
    ("tags.update(x)", lambda s, w, x: s.tags.update(x, name="studio")),
    ("items.tag(item, x)", lambda s, w, x: s.items.tag(w.tune, x)),
    ("items.untag(item, x)", lambda s, w, x: s.items.untag(w.song, x)),
    ("items.list(tag=x)", lambda s, w, x: s.items.list(tag=x)),
]

# For each form, a row of another kind and the text of the right row's identifier: the one a
# backend that parses text would find.
WRONG: list[tuple[str, Probe, Wrong]] = [
    *((f"{label} <- item", probe, lambda w: w.song) for label, probe in CATEGORY_FORMS),
    *((f"{label} <- str", probe, lambda w: str(w.jazz.category_id)) for label, probe in CATEGORY_FORMS),
    *((f"{label} <- tag", probe, lambda w: w.live) for label, probe in ITEM_FORMS),
    *((f"{label} <- str", probe, lambda w: str(w.song.item_id)) for label, probe in ITEM_FORMS),
    *((f"{label} <- category", probe, lambda w: w.jazz) for label, probe in TAG_FORMS),
    *((f"{label} <- str", probe, lambda w: str(w.live.tag_id)) for label, probe in TAG_FORMS),
]
WRONG_IDS = [label for label, _, _ in WRONG]

# The subject forms, where ``None`` is not "no filter" but a value of the wrong type, beside a
# number and arbitrary text.
SUBJECT_FORM_LABELS = {
    "categories[x]",
    "categories.get(x)",
    "x in categories",
    "categories.delete(x)",
    "items[x]",
    "items.place_in(x, category)",
    "tags[x]",
    "tags.update(x)",
}
NOT_A_REFERENCE: list[tuple[str, object]] = [("None", None), ("int", 5), ("text", "jazz")]
SUBJECT_CASES = [
    (f"{label} <- {kind}", probe, value)
    for label, probe in (*CATEGORY_FORMS, *ITEM_FORMS, *TAG_FORMS)
    if label in SUBJECT_FORM_LABELS
    for kind, value in NOT_A_REFERENCE
]
SUBJECT_IDS = [label for label, _, _ in SUBJECT_CASES]

# The graph's container forms read the snapshot before they refuse a key, and that read is not
# what they refuse.
READS_A_SNAPSHOT_FIRST = ("graph[", "graph.get", "x in graph")


class TestAnythingElseIsATypeError:
    """A value that is neither a row of the right kind nor a ``UUID`` is refused by its type."""

    @pytest.mark.parametrize(("label", "probe", "wrong"), WRONG, ids=WRONG_IDS)
    def test_the_wrong_kind_or_text(
        self, counting_service: CountedService, label: str, probe: Probe, wrong: Wrong
    ) -> None:
        service = counting_service.service
        world = build(service)
        counting_service.cold()

        with pytest.raises(TypeError):
            probe(service, world, wrong(world))
        if not label.startswith(READS_A_SNAPSHOT_FIRST):
            assert counting_service.reads.total == 0, f"{label} read storage before refusing"

    @pytest.mark.parametrize(("label", "probe", "value"), SUBJECT_CASES, ids=SUBJECT_IDS)
    def test_none_a_number_or_text_as_a_subject(
        self, service: TaxomeshService, label: str, probe: Probe, value: object
    ) -> None:
        world = build(service)

        with pytest.raises(TypeError):
            probe(service, world, value)
