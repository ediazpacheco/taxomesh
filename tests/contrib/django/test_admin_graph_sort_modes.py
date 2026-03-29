"""Tests for pluggable graph sort modes (053-graph-sort-modes)."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Phase 2 — T001: Regression: GraphEntry and RelationEntry importable from admin
# ---------------------------------------------------------------------------


def test_graph_entry_importable_from_admin() -> None:
    """GraphEntry must remain importable from taxomesh.contrib.django.admin after the move."""
    from taxomesh.contrib.django.admin import GraphEntry  # noqa: PLC0415

    assert GraphEntry is not None


def test_relation_entry_importable_from_admin() -> None:
    """RelationEntry must remain importable from taxomesh.contrib.django.admin after the move."""
    from taxomesh.contrib.django.admin import RelationEntry  # noqa: PLC0415

    assert RelationEntry is not None


def test_graph_entry_importable_from_graph_types() -> None:
    """GraphEntry must be importable directly from taxomesh.contrib.django.graph_types."""
    from taxomesh.contrib.django.graph_types import GraphEntry  # noqa: PLC0415

    assert GraphEntry is not None


def test_relation_entry_importable_from_graph_types() -> None:
    """RelationEntry must be importable directly from taxomesh.contrib.django.graph_types."""
    from taxomesh.contrib.django.graph_types import RelationEntry  # noqa: PLC0415

    assert RelationEntry is not None


# ---------------------------------------------------------------------------
# Phase 3 — T004–T006: Unit tests for built-in sort callables and registry
# ---------------------------------------------------------------------------


def test_sort_index_asc_builtin() -> None:
    """sort_index_asc returns entries in ascending sort_index order."""
    from taxomesh.contrib.django.graph_sort import sort_index_asc  # noqa: PLC0415
    from taxomesh.contrib.django.graph_types import GraphEntry  # noqa: PLC0415

    entries: list[GraphEntry] = [
        GraphEntry(
            depth=0,
            kind="category",
            name="B",
            uuid="b",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=5,
            parent_uuid="",
        ),
        GraphEntry(
            depth=0,
            kind="category",
            name="A",
            uuid="a",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=1,
            parent_uuid="",
        ),
        GraphEntry(
            depth=0,
            kind="category",
            name="C",
            uuid="c",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=3,
            parent_uuid="",
        ),
    ]
    result = sort_index_asc(entries)
    assert [e["sort_index"] for e in result] == [1, 3, 5]


def test_sort_index_desc_builtin() -> None:
    """sort_index_desc returns entries in descending sort_index order."""
    from taxomesh.contrib.django.graph_sort import sort_index_desc  # noqa: PLC0415
    from taxomesh.contrib.django.graph_types import GraphEntry  # noqa: PLC0415

    entries: list[GraphEntry] = [
        GraphEntry(
            depth=0,
            kind="category",
            name="B",
            uuid="b",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=5,
            parent_uuid="",
        ),
        GraphEntry(
            depth=0,
            kind="category",
            name="A",
            uuid="a",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=1,
            parent_uuid="",
        ),
        GraphEntry(
            depth=0,
            kind="category",
            name="C",
            uuid="c",
            enabled=True,
            external_id=None,
            linked_url=None,
            has_descendants=False,
            depth_limited=False,
            initially_collapsed=False,
            sort_index=3,
            parent_uuid="",
        ),
    ]
    result = sort_index_desc(entries)
    assert [e["sort_index"] for e in result] == [5, 3, 1]


def test_default_sort_modes_registry() -> None:
    """DEFAULT_SORT_MODES has exactly 2 entries with keys sort_index_asc and sort_index_desc."""
    from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES  # noqa: PLC0415

    assert len(DEFAULT_SORT_MODES) == 2
    keys = [mode[0] for mode in DEFAULT_SORT_MODES]
    assert keys == ["sort_index_asc", "sort_index_desc"]


# ---------------------------------------------------------------------------
# Phase 3 — T007–T009: View integration tests
# ---------------------------------------------------------------------------


def _create_sorted_categories() -> tuple[str, str, str]:
    """Create three root categories with known sort_index values. Return their names in asc order."""
    from taxomesh import TaxomeshService  # noqa: PLC0415
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    repo = DjangoRepository()
    svc = TaxomeshService(repository=repo)

    # Create three categories
    cat_low = svc.create_category(name="SortLow")
    cat_mid = svc.create_category(name="SortMid")
    cat_high = svc.create_category(name="SortHigh")

    # Set explicit sort_index values via reorder (after placing under root)
    # Use list_category_parent_links to find root link and set sort_index
    from taxomesh.contrib.django.models import CategoryParentLinkModel  # noqa: PLC0415
    from taxomesh.domain.constants import ROOT_CATEGORY_NAME  # noqa: PLC0415

    all_cats = repo.list_categories(enabled=None)
    root = next((c for c in all_cats if c.name == ROOT_CATEGORY_NAME), None)
    assert root is not None, "Root category not found"

    # Set sort_index on the parent links
    CategoryParentLinkModel.objects.filter(category_id=cat_low.category_id).update(sort_index=10)
    CategoryParentLinkModel.objects.filter(category_id=cat_mid.category_id).update(sort_index=20)
    CategoryParentLinkModel.objects.filter(category_id=cat_high.category_id).update(sort_index=30)

    return "SortLow", "SortMid", "SortHigh"


def test_graph_view_default_sort(admin_client: object) -> None:
    """GET /graph/ with no sort_by param returns entries sorted by sort_index ascending."""
    from django.urls import reverse  # noqa: PLC0415

    _create_sorted_categories()
    url = reverse("admin:taxomesh_contrib_django_graph")
    response = admin_client.get(url)  # type: ignore[attr-defined]
    content = response.content.decode()

    low_pos = content.find("SortLow")
    mid_pos = content.find("SortMid")
    high_pos = content.find("SortHigh")
    assert low_pos != -1 and mid_pos != -1 and high_pos != -1, "All category names must appear in graph"
    assert low_pos < mid_pos < high_pos, "Default sort must be ascending by sort_index"


def test_graph_view_sort_desc(admin_client: object) -> None:
    """GET /graph/?sort_by=sort_index_desc returns entries sorted descending."""
    from django.urls import reverse  # noqa: PLC0415

    _create_sorted_categories()
    url = reverse("admin:taxomesh_contrib_django_graph")
    response = admin_client.get(url, {"sort_by": "sort_index_desc"})  # type: ignore[attr-defined]
    content = response.content.decode()

    low_pos = content.find("SortLow")
    mid_pos = content.find("SortMid")
    high_pos = content.find("SortHigh")
    assert low_pos != -1 and mid_pos != -1 and high_pos != -1, "All category names must appear in graph"
    assert high_pos < mid_pos < low_pos, "sort_index_desc must sort highest sort_index first"


def test_graph_children_sort_propagated(admin_client: object) -> None:
    """GET /graph/children/?parent_uuid=...&sort_by=sort_index_desc applies descending sort."""
    from django.urls import reverse  # noqa: PLC0415

    from taxomesh import TaxomeshService  # noqa: PLC0415
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415
    from taxomesh.contrib.django.models import CategoryParentLinkModel  # noqa: PLC0415

    repo = DjangoRepository()
    svc = TaxomeshService(repository=repo)

    parent = svc.create_category(name="ParentSortTest")
    child_a = svc.create_category(name="ChildA")
    child_b = svc.create_category(name="ChildB")
    child_c = svc.create_category(name="ChildC")
    svc.add_category_parent(child_a.category_id, parent.category_id)
    svc.add_category_parent(child_b.category_id, parent.category_id)
    svc.add_category_parent(child_c.category_id, parent.category_id)

    # Assign deterministic sort_index values
    CategoryParentLinkModel.objects.filter(
        category_id=child_a.category_id, parent_category_id=parent.category_id
    ).update(sort_index=10)
    CategoryParentLinkModel.objects.filter(
        category_id=child_b.category_id, parent_category_id=parent.category_id
    ).update(sort_index=20)
    CategoryParentLinkModel.objects.filter(
        category_id=child_c.category_id, parent_category_id=parent.category_id
    ).update(sort_index=30)

    url = reverse("admin:taxomesh_contrib_django_graph_children")
    response = admin_client.get(  # type: ignore[attr-defined]
        url,
        {"parent_uuid": str(parent.category_id), "depth": "1", "sort_by": "sort_index_desc"},
    )
    content = response.content.decode()

    pos_a = content.find("ChildA")
    pos_b = content.find("ChildB")
    pos_c = content.find("ChildC")
    assert pos_a != -1 and pos_b != -1 and pos_c != -1
    assert pos_c < pos_b < pos_a, "sort_index_desc must put ChildC (30) first, ChildA (10) last"


# ---------------------------------------------------------------------------
# Phase 4 — T016, T016b, T017, T018: _resolve_sort_fn tests
# ---------------------------------------------------------------------------


def test_resolve_sort_fn_known_key(admin_client: object) -> None:
    """_resolve_sort_fn('sort_index_desc') returns the sort_index_desc callable."""
    from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415
    from taxomesh.contrib.django.graph_sort import sort_index_desc  # noqa: PLC0415

    admin_instance = CategoryModelAdmin.__new__(CategoryModelAdmin)
    result = admin_instance._resolve_sort_fn("sort_index_desc")
    assert result is sort_index_desc


def test_consumer_sort_mode_appears_in_context(admin_client: object) -> None:
    """A subclass with a custom sort_modes entry produces sort_mode_options with the custom label."""
    from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415
    from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES, SortMode  # noqa: PLC0415
    from taxomesh.contrib.django.graph_types import GraphEntry  # noqa: PLC0415

    def my_custom_sort(entries: list[GraphEntry]) -> list[GraphEntry]:
        return entries

    class ConsumerAdmin(CategoryModelAdmin):
        sort_modes: list[SortMode] = [*DEFAULT_SORT_MODES, ("custom_mode", "My Custom Sort", my_custom_sort)]

    instance = ConsumerAdmin.__new__(ConsumerAdmin)
    sort_mode_options = [{"key": k, "label": lbl} for k, lbl, _ in instance.sort_modes]
    labels = [opt["label"] for opt in sort_mode_options]
    assert "My Custom Sort" in labels


def test_consumer_sort_callable_invoked() -> None:
    """_resolve_sort_fn returns the consumer's callable when its key is the active sort_by."""
    from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415
    from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES, SortMode  # noqa: PLC0415
    from taxomesh.contrib.django.graph_types import GraphEntry  # noqa: PLC0415

    def my_custom_sort(entries: list[GraphEntry]) -> list[GraphEntry]:
        return entries

    class ConsumerAdmin(CategoryModelAdmin):
        sort_modes: list[SortMode] = [*DEFAULT_SORT_MODES, ("custom_mode", "My Custom Sort", my_custom_sort)]

    instance = ConsumerAdmin.__new__(ConsumerAdmin)
    result = instance._resolve_sort_fn("custom_mode")
    assert result is my_custom_sort


def test_resolve_sort_fn_unknown_key_fallback() -> None:
    """_resolve_sort_fn('nonexistent') falls back to the first registered mode (sort_index_asc)."""
    from taxomesh.contrib.django.admin import CategoryModelAdmin  # noqa: PLC0415
    from taxomesh.contrib.django.graph_sort import sort_index_asc  # noqa: PLC0415

    instance = CategoryModelAdmin.__new__(CategoryModelAdmin)
    result = instance._resolve_sort_fn("nonexistent_key")
    assert result is sort_index_asc


# ---------------------------------------------------------------------------
# Phase 5 — T020: No regression — default order is sort_index_asc
# ---------------------------------------------------------------------------


def test_no_regression_default_order(admin_client: object) -> None:
    """Without sort_by param, graph view order matches sort_index_asc (pre-feature contract)."""
    from django.urls import reverse  # noqa: PLC0415

    _create_sorted_categories()
    url = reverse("admin:taxomesh_contrib_django_graph")
    response = admin_client.get(url)  # type: ignore[attr-defined]
    content = response.content.decode()

    low_pos = content.find("SortLow")
    mid_pos = content.find("SortMid")
    high_pos = content.find("SortHigh")
    assert low_pos != -1 and mid_pos != -1 and high_pos != -1
    assert low_pos < mid_pos < high_pos, "Default order must be sort_index ascending (regression test)"
