"""Tests for category-parent link upsert."""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import CategoryParentLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshCyclicDependencyError

from .conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# InMemoryRepository — category-parent upsert
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
# Service-level categories.add_parent() idempotency
# ---------------------------------------------------------------------------


def test_categories_add_parent_idempotent(service: TaxomeshService) -> None:
    """Calling categories.add_parent() twice with the same pair creates only one link."""
    cat_a = service.categories.create(name="Child")
    cat_b = service.categories.create(name="Parent")

    service.categories.add_parent(cat_a.category_id, cat_b.category_id, sort_index=0)
    service.categories.add_parent(cat_a.category_id, cat_b.category_id, sort_index=7)

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
# Distinct pairs unaffected by upsert
# ---------------------------------------------------------------------------


def test_upsert_does_not_affect_distinct_pairs(service: TaxomeshService) -> None:
    """Upserting (C, P1) does not affect (C, P2)."""
    child = service.categories.create(name="Child")
    parent1 = service.categories.create(name="Parent1")
    parent2 = service.categories.create(name="Parent2")

    service.categories.add_parent(child.category_id, parent1.category_id, sort_index=1)
    service.categories.add_parent(child.category_id, parent2.category_id, sort_index=2)
    # Upsert (child, parent1) with new sort_index
    service.categories.add_parent(child.category_id, parent1.category_id, sort_index=99)

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


# ---------------------------------------------------------------------------
# Service-level categories.remove_parent()
# ---------------------------------------------------------------------------


def test_categories_remove_parent_valid(service: TaxomeshService) -> None:
    """Removing an existing link removes it from list_category_parent_links()."""
    cat_a = service.categories.create(name="Child")
    cat_b = service.categories.create(name="Parent")
    service.categories.add_parent(cat_a.category_id, cat_b.category_id, sort_index=0)

    # Confirm the explicit link exists before removal
    explicit_before = [
        lnk
        for lnk in service._repo.list_category_parent_links()
        if lnk.category_id == cat_a.category_id and lnk.parent_category_id == cat_b.category_id
    ]
    assert len(explicit_before) == 1

    service.categories.remove_parent(cat_a.category_id, cat_b.category_id)

    explicit_after = [
        lnk
        for lnk in service._repo.list_category_parent_links()
        if lnk.category_id == cat_a.category_id and lnk.parent_category_id == cat_b.category_id
    ]
    assert len(explicit_after) == 0


def test_categories_remove_parent_noop_if_not_linked(service: TaxomeshService) -> None:
    """Removing a non-existent link raises no error."""
    cat_a = service.categories.create(name="A")
    cat_b = service.categories.create(name="B")
    # No link exists — must not raise
    service.categories.remove_parent(cat_a.category_id, cat_b.category_id)


def test_categories_remove_parent_raises_if_category_not_found(service: TaxomeshService) -> None:
    """Removing with an unknown category_id raises TaxomeshCategoryNotFoundError."""
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories.remove_parent(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# Self-reference guard in categories.add_parent()
# ---------------------------------------------------------------------------


def test_categories_add_parent_self_reference_raises_cyclic_error(service: TaxomeshService) -> None:
    """categories.add_parent(A, A) raises TaxomeshCyclicDependencyError with a clear message."""
    cat = service.categories.create(name="SelfRef")
    with pytest.raises(TaxomeshCyclicDependencyError, match="cannot be its own parent"):
        service.categories.add_parent(cat.category_id, cat.category_id)
