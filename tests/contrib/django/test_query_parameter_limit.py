"""A Django read that names more values than one query may pass reads them in several queries.

A database accepts a limited number of parameters in one query: Django's
``connection.features.max_query_params``, 32,766 on SQLite. Each read that filters by a list of
values (``<field>__in``) cuts the list so that no query passes more, and returns every row, in the
order that the member promises. The limit is lowered here, so a few rows cross it; each query's
parameters are counted as the database receives them.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

import pytest

pytest.importorskip("django", reason="Django is not installed")

from django.db import connection
from django.db.backends.utils import CursorWrapper

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.django_repository import DjangoRepository

pytestmark = pytest.mark.django_db

# The lowered limit: below the size of every list that the reads below pass.
LIMIT: Final[int] = 7

# How many items the category holds: more than LIMIT.
ITEMS: Final[int] = 20


@dataclass(frozen=True)
class Scene:
    """The stored rows: a category holding every item, its children, tags and a chain of relations."""

    category: UUID
    categories: list[UUID]
    items: list[UUID]
    tags: list[UUID]
    missing: list[UUID]


@pytest.fixture
def scene() -> Scene:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    top = svc.categories.create("All", external_id="c-top").category_id
    children = [svc.categories.create(f"child {n}", external_id=f"c-{n}").category_id for n in range(LIMIT + 2)]
    for n, child in enumerate(children):
        svc.categories.add_parent(child, top, sort_index=LIMIT + 2 - n)
    items = [svc.items.create(f"item {n}", external_id=f"i-{n}").item_id for n in range(ITEMS)]
    for n, item in enumerate(items):
        svc.items.place_in(item, top, sort_index=ITEMS - n)
        svc.items.place_in(item, children[n % len(children)], sort_index=n)
    svc.items.update(items[3], enabled=False)
    tags = [svc.tags.create(f"tag {n}").tag_id for n in range(3)]
    for n, item in enumerate(items):
        svc.items.tag(item, tags[n % len(tags)])
    for n in range(ITEMS - 1):
        svc.items.relate(items[n], items[n + 1], "next" if n % 2 else "after", sort_index=ITEMS - n)
        svc.items.relate(items[n + 1], items[0], "first", sort_index=n)
    return Scene(top, [top, *children], items, tags, [uuid4() for _ in range(LIMIT)])


type Read = Callable[[DjangoRepository, Scene], object]

READS: dict[str, Read] = {
    "map_tags_by_id": lambda r, s: r.map_tags_by_id([*s.tags, *s.missing]),
    "map_items_by_id": lambda r, s: r.map_items_by_id(s.items),
    "map_items_by_id enabled": lambda r, s: r.map_items_by_id(s.items, enabled=True),
    "map_categories_by_id": lambda r, s: r.map_categories_by_id([*s.categories, *s.missing], enabled=None),
    "map_items_by_external_id": lambda r, s: r.map_items_by_external_id([f"i-{n}" for n in range(ITEMS)]),
    "map_categories_by_external_id": lambda r, s: r.map_categories_by_external_id(
        ["c-top", *(f"c-{n}" for n in range(LIMIT + 2))], enabled=True
    ),
    "list_item_tag_links by item": lambda r, s: r.list_item_tag_links(item_ids=s.items),
    "list_item_tag_links by both": lambda r, s: r.list_item_tag_links(item_ids=s.items, tag_ids=[*s.tags, *s.missing]),
    "list_category_parent_links by child": lambda r, s: r.list_category_parent_links(category_ids=s.categories),
    "list_category_parent_links by both": lambda r, s: r.list_category_parent_links(
        category_ids=s.categories, parent_category_ids=[*s.categories, *s.missing]
    ),
    "list_item_parent_links by item": lambda r, s: r.list_item_parent_links(item_ids=s.items),
    "list_item_parent_links by category": lambda r, s: r.list_item_parent_links(category_ids=s.categories),
    "list_item_parent_links by both": lambda r, s: r.list_item_parent_links(
        item_ids=s.items, category_ids=s.categories
    ),
    "list_item_relation_links": lambda r, s: r.list_item_relation_links(
        s.items[0], relation_types=["next", "first"], direction="both"
    ),
    "list_item_relation_links_batch outgoing": lambda r, s: r.list_item_relation_links_batch(s.items),
    "list_item_relation_links_batch incoming": lambda r, s: r.list_item_relation_links_batch(
        s.items, relation_types=["next", "after"], direction="incoming"
    ),
    "list_item_relation_links_batch both": lambda r, s: r.list_item_relation_links_batch(s.items, direction="both"),
    "list_item_relation_links_batch both typed": lambda r, s: r.list_item_relation_links_batch(
        s.items, relation_types=["first"], direction="both"
    ),
}


@contextmanager
def _parameters_per_query(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Lower the limit, and record how many parameters each query of the block passes."""
    counts: list[int] = []

    def count(
        execute: Callable[..., object], sql: str, params: object, many: bool, context: dict[str, CursorWrapper]
    ) -> object:
        counts.append(len(params) if isinstance(params, (list, tuple)) else 0)
        return execute(sql, params, many, context)

    monkeypatch.setattr(type(connection.features), "max_query_params", LIMIT)
    with connection.execute_wrapper(count):
        yield counts


@pytest.mark.parametrize("read", READS)
def test_a_read_past_the_limit_returns_every_row_in_order_and_no_query_passes_the_limit(
    read: str, scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = DjangoRepository()
    expected = READS[read](repository, scene)

    with _parameters_per_query(monkeypatch) as counts:
        held = READS[read](repository, scene)

    assert held == expected
    assert counts
    assert max(counts) <= LIMIT


def test_a_category_that_holds_more_items_than_the_limit_lists_them_all_in_order(
    scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    expected = [f"item {n}" for n in reversed(range(ITEMS)) if n != 3]

    with _parameters_per_query(monkeypatch) as counts:
        listed = [item.name for item in svc.items.list(category=scene.category)]

    assert listed == expected
    assert max(counts) <= LIMIT


@pytest.mark.parametrize(
    "read",
    [
        lambda r, s: r.list_item_parent_links(item_ids=[s.items[0]] * (LIMIT + 1)),
        lambda r, s: r.list_category_parent_links(category_ids=[s.categories[1]] * (LIMIT + 1)),
        lambda r, s: r.list_item_tag_links(item_ids=[s.items[0]] * (LIMIT + 1)),
    ],
    ids=["placements", "parent links", "tag links"],
)
def test_a_value_repeated_across_the_parts_of_a_read_returns_each_link_once(
    read: Read, scene: Scene, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = DjangoRepository()
    expected = read(repository, scene)

    with _parameters_per_query(monkeypatch):
        held = read(repository, scene)

    assert held == expected
