"""A Django write made of one ORM call opens no savepoint beyond those of that call.

``save_item_parent_link``, ``save_item_relation_link``, ``save_category_parent_link``, ``save_tag``
and ``add_item_tag_link`` each make one ``update_or_create`` or ``get_or_create`` call, which opens a
block of its own. Inside an ``atomic()`` block, as the service runs them, each write therefore opens
as many savepoints as the same ORM call made alone, on a first write and on a write that updates.
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from uuid import UUID

import pytest

pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh import TaxomeshService  # noqa: E402
from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryParentLinkModel,
    ItemParentLinkModel,
    ItemRelationLinkModel,
    ItemTagLinkModel,
    TagModel,
)
from taxomesh.domain.models import CategoryParentLink, ItemParentLink, ItemRelationLink, Tag  # noqa: E402

pytestmark = pytest.mark.django_db


@dataclass(frozen=True)
class Rows:
    """Three items, three categories and one tag: one link of each kind goes through the port, one through the ORM."""

    items: tuple[UUID, UUID, UUID]
    categories: tuple[UUID, UUID, UUID]
    tag: UUID


@pytest.fixture
def rows() -> Rows:
    svc = TaxomeshService(DjangoRepository(), cache_ttl=0)
    a, b, c = (svc.items.create(name).item_id for name in "abc")
    p, q, r = (svc.categories.create(name).category_id for name in "pqr")
    return Rows((a, b, c), (p, q, r), svc.tags.create("t").tag_id)


type Write = Callable[[DjangoRepository, Rows, int], object]

# Each write through the port, and the ORM call it makes, on another pair of rows. The last argument
# is the position, so a second call updates the link that the first one stored.
WRITES: dict[str, tuple[Write, Write]] = {
    "save_item_parent_link": (
        lambda repo, rows, n: repo.save_item_parent_link(
            ItemParentLink(item_id=rows.items[0], category_id=rows.categories[0], sort_index=n)
        ),
        lambda repo, rows, n: ItemParentLinkModel.objects.update_or_create(
            item_id=rows.items[1], category_id=rows.categories[0], defaults={"sort_index": n}
        ),
    ),
    "save_item_relation_link": (
        lambda repo, rows, n: repo.save_item_relation_link(
            ItemRelationLink(
                source_item_id=rows.items[0], target_item_id=rows.items[1], relation_type="r", sort_index=n
            )
        ),
        lambda repo, rows, n: ItemRelationLinkModel.objects.update_or_create(
            source_item_id=rows.items[1],
            target_item_id=rows.items[2],
            relation_type="r",
            defaults={"sort_index": n, "metadata": {}},
        ),
    ),
    "save_category_parent_link": (
        lambda repo, rows, n: repo.save_category_parent_link(
            CategoryParentLink(category_id=rows.categories[1], parent_category_id=rows.categories[0], sort_index=n)
        ),
        lambda repo, rows, n: CategoryParentLinkModel.objects.update_or_create(
            category_id=rows.categories[2], parent_category_id=rows.categories[0], defaults={"sort_index": n}
        ),
    ),
    "save_tag": (
        lambda repo, rows, n: repo.save_tag(Tag(tag_id=UUID(int=1), name=f"x{n}")),
        lambda repo, rows, n: TagModel.objects.update_or_create(
            tag_id=UUID(int=2), defaults={"name": f"x{n}", "metadata": {}}
        ),
    ),
    "add_item_tag_link": (
        lambda repo, rows, n: repo.add_item_tag_link(rows.items[0], rows.tag),
        lambda repo, rows, n: ItemTagLinkModel.objects.get_or_create(item_id=rows.items[1], tag_id=rows.tag),
    ),
}


def _savepoints(call: Callable[[], object]) -> int:
    """The number of savepoints that the call opens."""
    with CaptureQueriesContext(connection) as captured:
        call()
    return sum(query["sql"].startswith("SAVEPOINT") for query in captured.captured_queries)


@pytest.mark.parametrize("write", WRITES)
@pytest.mark.parametrize("position", [0, 1], ids=["first write", "update"])
def test_a_link_write_opens_only_the_savepoints_of_its_orm_call(write: str, position: int, rows: Rows) -> None:
    through_port, through_orm = WRITES[write]
    repo = DjangoRepository()
    with repo.atomic():
        for n in range(position + 1):
            port = _savepoints(partial(through_port, repo, rows, n))
            orm = _savepoints(partial(through_orm, repo, rows, n))

    assert port == orm
