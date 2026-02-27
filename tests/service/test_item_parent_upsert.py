"""Regression tests for item-category link upsert (010-unique-parent-links, US2)."""

from uuid import uuid4

from taxomesh.domain.models import ItemParentLink

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
