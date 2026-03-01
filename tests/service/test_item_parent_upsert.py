"""Regression tests for item-category link upsert (010-unique-parent-links, US2)."""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import ItemParentLink
from taxomesh.exceptions import TaxomeshItemNotFoundError

from .conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# T012: InMemoryRepository — item-category upsert regression
# ---------------------------------------------------------------------------


def test_inmemory_item_parent_upsert_updates_sort_index() -> None:
    """Saving the same (item_id, category_id) pair twice updates sort_index."""
    repo = InMemoryRepository()
    item_id = uuid4()
    cat_id = uuid4()

    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=0))
    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=5))

    links = repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 5


def test_inmemory_item_parent_upsert_same_sort_index_no_duplicate() -> None:
    """Saving the same pair with the same sort_index does not create a duplicate."""
    repo = InMemoryRepository()
    item_id = uuid4()
    cat_id = uuid4()

    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=0))
    repo.save_item_parent_link(ItemParentLink(item_id=item_id, category_id=cat_id, sort_index=0))

    links = repo.list_item_parent_links()
    assert len(links) == 1


# ---------------------------------------------------------------------------
# T007: Service-level remove_item_from_category()
# ---------------------------------------------------------------------------


def test_remove_item_from_category_valid(service: TaxomeshService) -> None:
    """Removing an existing item-category placement removes it from the link list."""
    cat = service.create_category(name="Cat")
    item = service.create_item(name="ext-1", external_id="ext-1")
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=0)

    links_before = [
        lnk
        for lnk in service._repo.list_item_parent_links()
        if lnk.item_id == item.item_id and lnk.category_id == cat.category_id
    ]
    assert len(links_before) == 1

    service.remove_item_from_category(item.item_id, cat.category_id)

    links_after = [
        lnk
        for lnk in service._repo.list_item_parent_links()
        if lnk.item_id == item.item_id and lnk.category_id == cat.category_id
    ]
    assert len(links_after) == 0


def test_remove_item_from_category_noop_if_not_placed(service: TaxomeshService) -> None:
    """Removing a placement that does not exist raises no error."""
    cat = service.create_category(name="Cat")
    item = service.create_item(name="ext-1", external_id="ext-1")
    # No placement — must not raise
    service.remove_item_from_category(item.item_id, cat.category_id)


def test_remove_item_from_category_raises_if_item_not_found(service: TaxomeshService) -> None:
    """Removing with an unknown item_id raises TaxomeshItemNotFoundError."""
    cat = service.create_category(name="Cat")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.remove_item_from_category(uuid4(), cat.category_id)
