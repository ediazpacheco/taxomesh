"""Two Django repositories on one database: a write reads what it changes from that database.

This is the shape of two worker processes, each with its own service and its own cache: service
``a`` reads a row, service ``b``, over its own ``DjangoRepository``, changes or deletes it, and
``a``'s next write is built on, and checked against, the stored row. The same cases over one
repository and four backends are in ``tests/service/test_writes_read_storage.py``.
"""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture()
def a() -> TaxomeshService:
    return TaxomeshService(repository=DjangoRepository())


@pytest.fixture()
def b() -> TaxomeshService:
    return TaxomeshService(repository=DjangoRepository())


@pytest.mark.parametrize("with_version", [True, False], ids=["version", "no-version"])
def test_an_item_update_keeps_the_other_workers_rename(
    a: TaxomeshService, b: TaxomeshService, with_version: bool
) -> None:
    held = a.items.create("Percanta")
    assert a.items[held] == held
    renamed = b.items.update(held, name="Mina")
    a.items.update(held, metadata={"k": 1}, expected_version=renamed.version if with_version else None)
    stored = b.repository.find_item(held.item_id)
    assert stored is not None
    assert (stored.name, stored.version, dict(stored.metadata)) == ("Mina", 2, {"k": 1})


@pytest.mark.parametrize("with_version", [True, False], ids=["version", "no-version"])
def test_a_category_update_keeps_the_other_workers_rename(
    a: TaxomeshService, b: TaxomeshService, with_version: bool
) -> None:
    held = a.categories.create("Tango")
    assert a.categories[held] == held
    renamed = b.categories.update(held, name="Milonga")
    a.categories.update(held, description="danced", expected_version=renamed.version if with_version else None)
    stored = b.repository.find_category(held.category_id)
    assert stored is not None
    assert (stored.name, stored.version, stored.description) == ("Milonga", 2, "danced")


def test_an_item_the_other_worker_deleted_is_not_stored_again(a: TaxomeshService, b: TaxomeshService) -> None:
    held = a.items.create("Percanta")
    assert a.items[held] == held
    b.items.delete(held)
    with pytest.raises(TaxomeshItemNotFoundError):
        a.items.update(held, name="Mina")
    assert b.repository.find_item(held.item_id) is None


def test_a_category_the_other_worker_deleted_is_not_stored_again(a: TaxomeshService, b: TaxomeshService) -> None:
    held = a.categories.create("Tango")
    assert a.categories[held] == held
    b.categories.delete(held)
    with pytest.raises(TaxomeshCategoryNotFoundError):
        a.categories.update(held, name="Milonga")
    assert b.repository.find_category(held.category_id) is None


def test_a_placement_in_a_category_the_other_worker_deleted_is_refused(a: TaxomeshService, b: TaxomeshService) -> None:
    item = a.items.create("Percanta")
    category = a.categories.create("Tango")
    assert a.categories[category] == category
    b.categories.delete(category)
    with pytest.raises(TaxomeshCategoryNotFoundError):
        a.items.place_in(item, category)
    assert not b.repository.list_item_parent_links(category_ids=[category.category_id])
