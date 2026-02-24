"""Tests for TaxomeshService category operations (US1) and DAG integrity."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import ROOT_CATEGORY_NAME, TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshCyclicDependencyError, TaxomeshRootCategoryError


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


# ---------------------------------------------------------------------------
# T-06: update_category, list_categories filtered (FR-027, FR-033)
# ---------------------------------------------------------------------------


def test_update_category_name(service: TaxomeshService) -> None:
    cat = service.create_category(name="Old")
    updated = service.update_category(cat.category_id, name="New")
    assert updated.name == "New"
    assert updated.description == ""  # unchanged


def test_update_category_description(service: TaxomeshService) -> None:
    cat = service.create_category(name="X")
    assert cat.description == ""  # BeforeValidator coerces None → ""
    updated = service.update_category(cat.category_id, description="New desc")
    assert updated.description == "New desc"
    assert updated.name == "X"  # unchanged


def test_update_category_partial_leaves_other_fields(service: TaxomeshService) -> None:
    cat = service.create_category(name="Keep", description="Also keep")
    updated = service.update_category(cat.category_id, name="Changed")
    assert updated.description == "Also keep"


def test_update_category_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.update_category(uuid4(), name="Ghost")


def test_list_categories_filtered_by_parent(service: TaxomeshService) -> None:
    parent = service.create_category(name="P")
    c1 = service.create_category(name="C1")
    c2 = service.create_category(name="C2")
    service.add_category_parent(c2.category_id, parent.category_id, sort_index=1)
    service.add_category_parent(c1.category_id, parent.category_id, sort_index=2)
    result = service.list_categories(parent_id=parent.category_id)
    assert [c.category_id for c in result] == [c2.category_id, c1.category_id]


def test_list_categories_parent_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.list_categories(parent_id=uuid4())


# ---------------------------------------------------------------------------
# Root category (006-taxonomy-graph prerequisite)
# ---------------------------------------------------------------------------


def test_root_category_exists_after_init(service: TaxomeshService) -> None:
    root = service.get_category(service._root_id)
    assert root.name == ROOT_CATEGORY_NAME


def test_list_categories_excludes_root(service: TaxomeshService) -> None:
    categories = service.list_categories()
    names = {c.name for c in categories}
    assert ROOT_CATEGORY_NAME not in names


def test_create_category_reserved_name_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshRootCategoryError):
        service.create_category(name=ROOT_CATEGORY_NAME)


def test_delete_root_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshRootCategoryError):
        service.delete_category(service._root_id)


def test_update_root_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshRootCategoryError):
        service.update_category(service._root_id, name="x")


def test_add_category_parent_root_as_child_raises(service: TaxomeshService) -> None:
    cat = service.create_category(name="SomeCat")
    with pytest.raises(TaxomeshRootCategoryError):
        service.add_category_parent(service._root_id, cat.category_id)


def test_create_category_auto_links_to_root(service: TaxomeshService) -> None:
    cat = service.create_category(name="Animals")
    links = service._repo.list_category_parent_links()
    root_link = next(
        (lnk for lnk in links if lnk.category_id == cat.category_id and lnk.parent_category_id == service._root_id),
        None,
    )
    assert root_link is not None
    assert root_link.sort_index == 0


def test_list_categories_returns_direct_children_of_root(service: TaxomeshService) -> None:
    cat = service.create_category(name="Animals")
    result = service.list_categories()
    assert len(result) == 1
    assert result[0].category_id == cat.category_id
