"""Removing a link that is not stored is a no-op, on every removal verb, as ``set.discard`` is.

``remove_parent``, ``remove_from``, ``untag`` and ``unrelate`` leave the store as it was when the
link they name is absent, whether it never existed or was removed a moment before. Deleting a row
that is not stored still raises: a row is addressed, a link is only described.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.exceptions import TaxomeshNotFoundError


@dataclass(frozen=True, slots=True)
class Rows:
    """Two categories, two items and a tag, with no link between any of them."""

    music: Category
    jazz: Category
    song: Item
    tune: Item
    live: Tag


def build(service: TaxomeshService) -> Rows:
    """Store the rows, each unlinked."""
    return Rows(
        music=service.categories.create("Music"),
        jazz=service.categories.create("Jazz"),
        song=service.items.create("Song"),
        tune=service.items.create("Tune"),
        live=service.tags.create("live"),
    )


def links(service: TaxomeshService, rows: Rows) -> tuple[object, ...]:
    """Every link the store holds among the rows, read through the port."""
    repository = service.repository
    return (
        tuple(repository.list_category_parent_links()),
        tuple(repository.list_item_parent_links()),
        tuple(repository.list_item_tag_links()),
        tuple(repository.list_item_relation_links_batch([rows.song.item_id, rows.tune.item_id], direction="both")),
    )


type Removal = Callable[[TaxomeshService, Rows], None]
type Addition = Callable[[TaxomeshService, Rows], object]

VERBS: list[tuple[str, Addition, Removal]] = [
    (
        "remove_parent",
        lambda s, r: s.categories.add_parent(r.jazz, r.music),
        lambda s, r: s.categories.remove_parent(r.jazz, r.music),
    ),
    (
        "remove_from",
        lambda s, r: s.items.place_in(r.song, r.jazz),
        lambda s, r: s.items.remove_from(r.song, r.jazz),
    ),
    (
        "untag",
        lambda s, r: s.items.tag(r.song, r.live),
        lambda s, r: s.items.untag(r.song, r.live),
    ),
    (
        "unrelate",
        lambda s, r: s.items.relate(r.song, r.tune, "covers"),
        lambda s, r: s.items.unrelate(r.song, r.tune, "covers"),
    ),
]
VERB_IDS = [name for name, _, _ in VERBS]


@pytest.mark.parametrize(("name", "add", "remove"), VERBS, ids=VERB_IDS)
class TestRemovingAnAbsentLink:
    """Each removal verb answers an absent link by changing nothing."""

    def test_a_link_never_stored(self, service: TaxomeshService, name: str, add: Addition, remove: Removal) -> None:
        rows = build(service)
        before = links(service, rows)

        remove(service, rows)

        assert links(service, rows) == before

    def test_a_link_removed_twice(self, service: TaxomeshService, name: str, add: Addition, remove: Removal) -> None:
        rows = build(service)
        before = links(service, rows)
        add(service, rows)

        remove(service, rows)
        remove(service, rows)

        assert links(service, rows) == before


def test_unrelate_ignores_the_type_s_case_and_whitespace_when_nothing_is_there(service: TaxomeshService) -> None:
    rows = build(service)
    service.items.relate(rows.song, rows.tune, "covers")
    service.items.unrelate(rows.song, rows.tune, " Covers ")
    before = links(service, rows)

    service.items.unrelate(rows.song, rows.tune, "COVERS")

    assert links(service, rows) == before


@pytest.mark.parametrize(
    "delete",
    [
        lambda s: s.categories.delete(uuid4()),
        lambda s: s.items.delete(uuid4()),
        lambda s: s.tags.delete(uuid4()),
    ],
    ids=["categories", "items", "tags"],
)
def test_deleting_an_absent_row_still_raises(
    service: TaxomeshService, delete: Callable[[TaxomeshService], None]
) -> None:
    with pytest.raises(TaxomeshNotFoundError):
        delete(service)
