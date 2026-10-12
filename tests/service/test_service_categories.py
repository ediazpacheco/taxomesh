"""Tests for TaxomeshService category operations and DAG integrity."""

import re
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshCyclicDependencyError, TaxomeshRootCategoryError


def test_categories_create_returns_category_with_id(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Animals")
    assert isinstance(cat.category_id, UUID)
    assert cat.name == "Animals"


def test_categories_create_with_description_and_metadata(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Books", description="All books", metadata={"source": "import"})
    assert cat.description == "All books"
    assert cat.metadata == {"source": "import"}


def test_categories_subscript_returns_category_with_all_fields(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Animals", description="Fauna")
    retrieved = service.categories[cat.category_id]
    assert retrieved.category_id == cat.category_id
    assert retrieved.name == "Animals"
    assert retrieved.description == "Fauna"


def test_get_missing_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories[uuid4()]


def test_categories_list_returns_all_created(service: TaxomeshService) -> None:
    service.categories.create(name="A")
    service.categories.create(name="B")
    categories = service.categories.roots()
    assert len(categories) == 2
    names = {c.name for c in categories}
    assert names == {"A", "B"}


def test_categories_list_empty(service: TaxomeshService) -> None:
    assert service.categories.roots() == ()


def test_categories_delete_removes_it(service: TaxomeshService) -> None:
    cat = service.categories.create(name="ToDelete")
    service.categories.delete(cat.category_id)
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories[cat.category_id]


def test_delete_missing_category_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories.delete(uuid4())


# ------------------------------------------------------------------
# DAG integrity — categories.add_parent
# ------------------------------------------------------------------


def test_categories_add_parent_returns_link(service: TaxomeshService) -> None:
    cat_a = service.categories.create(name="A")
    cat_b = service.categories.create(name="B")
    link = service.categories.add_parent(cat_a.category_id, cat_b.category_id)
    assert link.category_id == cat_a.category_id
    assert link.parent_category_id == cat_b.category_id


def test_categories_add_parent_cyclic_raises(service: TaxomeshService) -> None:
    """A → B → A must raise TaxomeshCyclicDependencyError."""
    cat_a = service.categories.create(name="A")
    cat_b = service.categories.create(name="B")
    service.categories.add_parent(cat_a.category_id, cat_b.category_id)  # A → B (valid)
    message = f"Category {cat_b.category_id} cannot have the parent {cat_a.category_id}: the parent link makes a cycle"
    with pytest.raises(TaxomeshCyclicDependencyError, match=re.escape(message)):
        service.categories.add_parent(cat_b.category_id, cat_a.category_id)  # B → A → cycle!


def test_categories_add_parent_self_loop_raises(service: TaxomeshService) -> None:
    """A → A is an immediate cycle."""
    cat_a = service.categories.create(name="A")
    with pytest.raises(TaxomeshCyclicDependencyError):
        service.categories.add_parent(cat_a.category_id, cat_a.category_id)


def test_categories_add_parent_longer_cycle_raises(service: TaxomeshService) -> None:
    """A → B → C → A must also be detected."""
    cat_a = service.categories.create(name="A")
    cat_b = service.categories.create(name="B")
    cat_c = service.categories.create(name="C")
    service.categories.add_parent(cat_a.category_id, cat_b.category_id)  # A → B
    service.categories.add_parent(cat_b.category_id, cat_c.category_id)  # B → C
    with pytest.raises(TaxomeshCyclicDependencyError):
        service.categories.add_parent(cat_c.category_id, cat_a.category_id)  # C → A → cycle!


def test_categories_add_parent_missing_category_raises(service: TaxomeshService) -> None:
    cat_a = service.categories.create(name="A")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories.add_parent(cat_a.category_id, uuid4())


# ---------------------------------------------------------------------------
# T-06: categories.update, categories.list / categories.roots filtered
# ---------------------------------------------------------------------------


def test_categories_update_name(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Old")
    updated = service.categories.update(cat.category_id, name="New")
    assert updated.name == "New"
    assert updated.description == ""  # unchanged


def test_categories_update_description(service: TaxomeshService) -> None:
    cat = service.categories.create(name="X")
    assert cat.description == ""  # BeforeValidator coerces None → ""
    updated = service.categories.update(cat.category_id, description="New desc")
    assert updated.description == "New desc"
    assert updated.name == "X"  # unchanged


def test_categories_update_partial_leaves_other_fields(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Keep", description="Also keep")
    updated = service.categories.update(cat.category_id, name="Changed")
    assert updated.description == "Also keep"


def test_categories_update_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories.update(uuid4(), name="Ghost")


def test_categories_update_metadata_replaces_value(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Meta", metadata={"old": True})
    updated = service.categories.update(cat.category_id, metadata={"new": 42})
    assert updated.metadata == {"new": 42}


def test_categories_update_metadata_none_leaves_existing_unchanged(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Preserve", metadata={"keep": "me"})
    updated = service.categories.update(cat.category_id, name="Preserve Updated")
    assert updated.metadata == {"keep": "me"}


def test_categories_list_filtered_by_parent(service: TaxomeshService) -> None:
    parent = service.categories.create(name="P")
    c1 = service.categories.create(name="C1")
    c2 = service.categories.create(name="C2")
    service.categories.add_parent(c2.category_id, parent.category_id, sort_index=1)
    service.categories.add_parent(c1.category_id, parent.category_id, sort_index=2)
    result = service.categories.list(parent=parent.category_id)
    assert [c.category_id for c in result] == [c2.category_id, c1.category_id]


def test_categories_list_parent_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.categories.list(parent=uuid4())


# ---------------------------------------------------------------------------
# The root category
# ---------------------------------------------------------------------------


def test_root_category_is_stored_after_init(service: TaxomeshService) -> None:
    """The root row exists in storage, which is where it is reached, since the container hides it.

    The root is invisible to ``service.categories`` but stored, so ``_ensure_root`` creating the
    row is asserted below the service boundary the visibility rule applies at.
    """
    root = service.repository.find_category(service._root_id)
    assert root is not None
    assert root.name == ROOT_CATEGORY_NAME


def test_categories_list_excludes_root(service: TaxomeshService) -> None:
    categories = service.categories.roots()
    names = {c.name for c in categories}
    assert ROOT_CATEGORY_NAME not in names


def test_categories_create_reserved_name_raises(service: TaxomeshService) -> None:
    message = f"Category name '{ROOT_CATEGORY_NAME}' is reserved for the implicit root"
    with pytest.raises(TaxomeshRootCategoryError, match=re.escape(message)):
        service.categories.create(name=ROOT_CATEGORY_NAME)


def test_categories_create_auto_links_to_root(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Animals")
    links = service._repo.list_category_parent_links()
    root_link = next(
        (lnk for lnk in links if lnk.category_id == cat.category_id and lnk.parent_category_id == service._root_id),
        None,
    )
    assert root_link is not None
    assert root_link.sort_index == 0


def test_categories_list_returns_direct_children_of_root(service: TaxomeshService) -> None:
    cat = service.categories.create(name="Animals")
    result = service.categories.roots()
    assert len(result) == 1
    assert result[0].category_id == cat.category_id


# ---------------------------------------------------------------------------
# Service external_id params on create/update/list
# ---------------------------------------------------------------------------


def test_categories_create_with_external_id(service: TaxomeshService) -> None:
    """categories.create accepts external_id kwarg and stores it."""
    cat = service.categories.create(name="Genre", external_id="genre-42")
    assert cat.external_id == "genre-42"


def test_categories_create_default_external_id(service: TaxomeshService) -> None:
    """categories.create without external_id defaults to None."""
    cat = service.categories.create(name="Genre2")
    assert cat.external_id is None


def test_categories_update_external_id_non_none(service: TaxomeshService) -> None:
    """categories.update with non-None external_id updates the field."""
    cat = service.categories.create(name="X")
    updated = service.categories.update(cat.category_id, external_id="new-val")
    assert updated.external_id == "new-val"


def test_categories_update_external_id_none_clears(service: TaxomeshService) -> None:
    """categories.update with external_id=None clears the field to None."""
    cat = service.categories.create(name="Y", external_id="original")
    updated = service.categories.update(cat.category_id, external_id=None)
    assert updated.external_id is None


def test_categories_update_external_id_empty_string_clears(service: TaxomeshService) -> None:
    """categories.update with external_id='' clears the field."""
    cat = service.categories.create(name="Z", external_id="something")
    updated = service.categories.update(cat.category_id, external_id="")
    assert updated.external_id == ""


def test_categories_list_filtered_by_external_id(service: TaxomeshService) -> None:
    """The lookup by external id returns the one category that carries it."""
    service.categories.create(name="A", external_id="match")
    service.categories.create(name="C", external_id="other")
    found = service.categories.get_by_external_id("match")
    assert found is not None
    assert found.name == "A"


def test_categories_list_external_id_none_returns_all(service: TaxomeshService) -> None:
    """``categories.roots()`` returns every top-level category."""
    service.categories.create(name="P")
    service.categories.create(name="Q")
    result = service.categories.roots()
    assert len(result) >= 2


def test_categories_list_external_id_empty_string(service: TaxomeshService) -> None:
    """The lookup finds the category whose external_id is '', not the one carrying a value."""
    service.categories.create(name="R", external_id="")
    service.categories.create(name="S", external_id="has-val")
    found = service.categories.get_by_external_id("")
    assert found is not None
    assert found.name == "R"


class TestCategoriesGetByExternalId:
    """``categories.get_by_external_id`` finds a category by external id, whatever its place or state.

    It never returns the implicit root, and it does not filter on ``enabled``.
    """

    def test_the_lookup_never_returns_the_root(self, service: TaxomeshService) -> None:
        """The root carrying the external id asked for is still not returned."""
        root = next(c for c in service.repository.list_categories(enabled=None) if c.name == ROOT_CATEGORY_NAME)
        service.repository.save_category(root.model_copy(update={"external_id": "ext-root"}))

        assert service.categories.get_by_external_id("ext-root") is None

    def test_the_lookup_does_not_filter_on_enabled(self, service: TaxomeshService) -> None:
        """A disabled category is returned, as ``get`` and subscript return one."""
        dark = service.categories.create("Dark", external_id="ext-dark")
        service.categories.update(dark.category_id, enabled=False)

        found = service.categories.get_by_external_id("ext-dark")

        assert found is not None
        assert found.category_id == dark.category_id
        assert found.enabled is False
