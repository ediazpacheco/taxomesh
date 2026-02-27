"""Tests for category-parent link upsert (010-unique-parent-links, US1)."""

from uuid import uuid4

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import CategoryParentLink

from .conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# T002: InMemoryRepository — category-parent upsert
# ---------------------------------------------------------------------------


def test_inmemory_category_parent_upsert_updates_sort_index() -> None:
    """Saving the same (category_id, parent_category_id) pair twice updates sort_index."""
    repo = InMemoryRepository()
    cat_id = uuid4()
    parent_id = uuid4()

    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=0))
    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=5))

    links = repo.list_category_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 5


def test_inmemory_category_parent_upsert_same_sort_index_no_duplicate() -> None:
    """Saving the same pair with the same sort_index does not create a duplicate."""
    repo = InMemoryRepository()
    cat_id = uuid4()
    parent_id = uuid4()

    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=0))
    repo.save_category_parent_link(CategoryParentLink(category_id=cat_id, parent_category_id=parent_id, sort_index=0))

    links = repo.list_category_parent_links()
    assert len(links) == 1


# ---------------------------------------------------------------------------
# T005: Service-level add_category_parent() idempotency
# ---------------------------------------------------------------------------


def test_add_category_parent_idempotent(service: TaxomeshService) -> None:
    """Calling add_category_parent() twice with the same pair creates only one link."""
    cat_a = service.create_category(name="Child")
    cat_b = service.create_category(name="Parent")

    service.add_category_parent(cat_a.category_id, cat_b.category_id, sort_index=0)
    service.add_category_parent(cat_a.category_id, cat_b.category_id, sort_index=7)

    # Filter to explicit links only (exclude auto-created root links)
    all_links = service._repo.list_category_parent_links()
    explicit = [
        lnk
        for lnk in all_links
        if lnk.category_id == cat_a.category_id and lnk.parent_category_id == cat_b.category_id
    ]
    assert len(explicit) == 1
    assert explicit[0].sort_index == 7


# ---------------------------------------------------------------------------
# T006: Distinct pairs unaffected by upsert
# ---------------------------------------------------------------------------


def test_upsert_does_not_affect_distinct_pairs(service: TaxomeshService) -> None:
    """Upserting (C, P1) does not affect (C, P2)."""
    child = service.create_category(name="Child")
    parent1 = service.create_category(name="Parent1")
    parent2 = service.create_category(name="Parent2")

    service.add_category_parent(child.category_id, parent1.category_id, sort_index=1)
    service.add_category_parent(child.category_id, parent2.category_id, sort_index=2)
    # Upsert (child, parent1) with new sort_index
    service.add_category_parent(child.category_id, parent1.category_id, sort_index=99)

    all_links = service._repo.list_category_parent_links()
    link_p1 = next(
        lnk
        for lnk in all_links
        if lnk.category_id == child.category_id and lnk.parent_category_id == parent1.category_id
    )
    link_p2 = next(
        lnk
        for lnk in all_links
        if lnk.category_id == child.category_id and lnk.parent_category_id == parent2.category_id
    )
    assert link_p1.sort_index == 99
    assert link_p2.sort_index == 2
