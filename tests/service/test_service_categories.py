"""Tests for TaxomeshService category operations (US1) and DAG integrity."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshCyclicDependencyError


def test_create_category_returns_category_with_id(service: TaxomeshService) -> None:
    cat = service.create_category(name="Animals")
    assert isinstance(cat.category_id, UUID)
    assert cat.name == "Animals"


def test_create_category_with_description_and_metadata(service: TaxomeshService) -> None:
    cat = service.create_category(name="Books", description="All books", metadata={"source": "import"})
    assert cat.description == "All books"
    assert cat.metadata == {"source": "import"}


def test_get_category_returns_category_with_all_fields(service: TaxomeshService) -> None:
    cat = service.create_category(name="Animals", description="Fauna")
    retrieved = service.get_category(cat.category_id)
    assert retrieved.category_id == cat.category_id
    assert retrieved.name == "Animals"
    assert retrieved.description == "Fauna"


def test_get_missing_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.get_category(uuid4())


def test_list_categories_returns_all_created(service: TaxomeshService) -> None:
    service.create_category(name="A")
    service.create_category(name="B")
    categories = service.list_categories()
    assert len(categories) == 2
    names = {c.name for c in categories}
    assert names == {"A", "B"}


def test_list_categories_empty(service: TaxomeshService) -> None:
    assert service.list_categories() == []


def test_delete_category_removes_it(service: TaxomeshService) -> None:
    cat = service.create_category(name="ToDelete")
    service.delete_category(cat.category_id)
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.get_category(cat.category_id)


def test_delete_missing_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.delete_category(uuid4())


# ------------------------------------------------------------------
# DAG integrity — add_category_parent
# ------------------------------------------------------------------


def test_add_category_parent_returns_link(service: TaxomeshService) -> None:
    cat_a = service.create_category(name="A")
    cat_b = service.create_category(name="B")
    link = service.add_category_parent(cat_a.category_id, cat_b.category_id)
    assert link.category_id == cat_a.category_id
    assert link.parent_category_id == cat_b.category_id


def test_add_category_parent_cyclic_raises(service: TaxomeshService) -> None:
    """A → B → A must raise TaxomeshCyclicDependencyError."""
    cat_a = service.create_category(name="A")
    cat_b = service.create_category(name="B")
    service.add_category_parent(cat_a.category_id, cat_b.category_id)  # A → B (valid)
    with pytest.raises(TaxomeshCyclicDependencyError):
        service.add_category_parent(cat_b.category_id, cat_a.category_id)  # B → A → cycle!


def test_add_category_parent_self_loop_raises(service: TaxomeshService) -> None:
    """A → A is an immediate cycle."""
    cat_a = service.create_category(name="A")
    with pytest.raises(TaxomeshCyclicDependencyError):
        service.add_category_parent(cat_a.category_id, cat_a.category_id)


def test_add_category_parent_longer_cycle_raises(service: TaxomeshService) -> None:
    """A → B → C → A must also be detected."""
    cat_a = service.create_category(name="A")
    cat_b = service.create_category(name="B")
    cat_c = service.create_category(name="C")
    service.add_category_parent(cat_a.category_id, cat_b.category_id)  # A → B
    service.add_category_parent(cat_b.category_id, cat_c.category_id)  # B → C
    with pytest.raises(TaxomeshCyclicDependencyError):
        service.add_category_parent(cat_c.category_id, cat_a.category_id)  # C → A → cycle!


def test_add_category_parent_missing_category_raises(service: TaxomeshService) -> None:
    cat_a = service.create_category(name="A")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.add_category_parent(cat_a.category_id, uuid4())
