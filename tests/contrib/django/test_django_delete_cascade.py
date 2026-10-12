"""On Django, a delete removes every link naming its row inside the one transaction it opens.

The link tables' foreign keys are ``on_delete=CASCADE``, and ``QuerySet.delete()`` runs the whole
cascade in an atomic block. These tests run without pytest-django's wrapping transaction, so that
block is the outermost one: a failure after every ``DELETE`` has run must leave the row and each of
its links stored.
"""

from dataclasses import dataclass
from uuid import UUID

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db.models import Q  # noqa: E402
from django.db.models.signals import post_delete  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.contrib.django.models import (  # noqa: E402
    CategoryModel,
    CategoryParentLinkModel,
    ItemModel,
    ItemParentLinkModel,
    ItemRelationLinkModel,
    ItemTagLinkModel,
    TagModel,
)

pytestmark = pytest.mark.django_db(transaction=True)


class _Interrupted(Exception):
    """Raised by a receiver after the delete's last statement, before its transaction commits."""


@dataclass(frozen=True)
class _Scene:
    category_id: UUID
    item_id: UUID
    tag_id: UUID


def _scene(service: TaxomeshService) -> _Scene:
    """A category, an item and a tag, each at the end of every kind of link it can have."""
    parent = service.categories.create("Parent")
    category = service.categories.create("Category")
    child = service.categories.create("Child")
    service.categories.add_parent(category.category_id, parent.category_id)
    service.categories.add_parent(child.category_id, category.category_id)
    item = service.items.create("Item")
    other = service.items.create("Other")
    service.items.place_in(item.item_id, category.category_id)
    tag = service.tags.create("tag")
    service.items.tag(item.item_id, tag.tag_id)
    service.items.tag(other.item_id, tag.tag_id)
    service.items.relate(item.item_id, other.item_id, "covers")
    service.items.relate(other.item_id, item.item_id, "samples")
    return _Scene(category.category_id, item.item_id, tag.tag_id)


def _link_rows_naming(row_id: UUID) -> int:
    """Count the rows of the four link tables with this identifier at either end."""
    return (
        CategoryParentLinkModel.objects.filter(Q(category_id=row_id) | Q(parent_category_id=row_id)).count()
        + ItemParentLinkModel.objects.filter(Q(item_id=row_id) | Q(category_id=row_id)).count()
        + ItemTagLinkModel.objects.filter(Q(item_id=row_id) | Q(tag_id=row_id)).count()
        + ItemRelationLinkModel.objects.filter(Q(source_item_id=row_id) | Q(target_item_id=row_id)).count()
    )


_KINDS = {
    "category": (CategoryModel, "delete_category", "category_id"),
    "item": (ItemModel, "delete_item", "item_id"),
    "tag": (TagModel, "delete_tag", "tag_id"),
}


@pytest.mark.parametrize("kind", list(_KINDS))
def test_a_delete_leaves_no_link_row_naming_its_row(kind: str) -> None:
    repo = DjangoRepository()
    scene = _scene(TaxomeshService(repository=repo))
    model, delete, key = _KINDS[kind]
    row_id = getattr(scene, key)
    assert _link_rows_naming(row_id) > 0

    assert getattr(repo, delete)(row_id) is True

    assert _link_rows_naming(row_id) == 0
    assert not model._default_manager.filter(pk=row_id).exists()


@pytest.mark.parametrize("kind", list(_KINDS))
def test_a_delete_that_fails_after_its_last_statement_keeps_the_row_and_every_link(kind: str) -> None:
    repo = DjangoRepository()
    scene = _scene(TaxomeshService(repository=repo))
    model, delete, key = _KINDS[kind]
    row_id = getattr(scene, key)
    links_before = _link_rows_naming(row_id)

    def interrupt(**_: object) -> None:
        raise _Interrupted

    # Django deletes the rows that point at a row before the row itself, so the row's own
    # post_delete runs after every cascaded DELETE, still inside the delete's transaction.
    post_delete.connect(interrupt, sender=model, dispatch_uid="interrupt-delete")
    try:
        with pytest.raises(_Interrupted):
            getattr(repo, delete)(row_id)
    finally:
        post_delete.disconnect(sender=model, dispatch_uid="interrupt-delete")

    assert model._default_manager.filter(pk=row_id).exists()
    assert _link_rows_naming(row_id) == links_before
