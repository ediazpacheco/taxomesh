"""Schema introspection tests for ordering indexes (035-django-ordering-indexes).

Verifies that the four database indexes introduced by migration 0005 are present
after `migrate` runs. Correctness of ordering behaviour is already covered by
tests/contrib/django/test_django_repository_ordering.py (spec 034).
"""

import importlib

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402

pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# Index-name length guard
# Oracle and some other backends impose a 30-character limit on identifiers.
# This test catches violations at CI time before they can reach production.
# ---------------------------------------------------------------------------
_MAX_INDEX_NAME_LEN = 30


def _all_index_names() -> list[tuple[str, str]]:
    """Return (model_name, index_name) for every index across all taxomesh models."""
    results = []
    module = importlib.import_module("taxomesh.contrib.django.models")
    for attr in dir(module):
        obj = getattr(module, attr)
        try:
            meta = obj._meta  # type: ignore[union-attr]
        except AttributeError:
            continue
        if not hasattr(meta, "indexes"):
            continue
        for idx in meta.indexes:
            if idx.name:
                results.append((attr, idx.name))
    return results


def test_all_index_names_fit_30_chars() -> None:
    """Every index name in taxomesh Django models must be ≤ 30 characters.

    Databases such as Oracle and older PostgreSQL versions impose a 30-character
    limit on identifier names.  Django itself raises models.E034 when this limit
    is exceeded, which causes `migrate` to fail at runtime.
    """
    violations = [
        f"{model}.{name!r} ({len(name)} chars)"
        for model, name in _all_index_names()
        if len(name) > _MAX_INDEX_NAME_LEN
    ]
    assert not violations, "Index names longer than 30 characters found — shorten them:\n" + "\n".join(
        f"  {v}" for v in violations
    )


def _index_names(table: str) -> set[str]:
    """Return the set of index names present on the given table."""
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return {name for name, info in constraints.items() if info.get("index")}


class TestOrderingIndexesPresent:
    """All four ordering indexes must exist after migration 0005 is applied."""

    def test_category_name_index_exists(self) -> None:
        """taxomesh_category_name_idx must be present on taxomesh_category."""
        assert "taxomesh_category_name_idx" in _index_names("taxomesh_category")

    def test_item_name_index_exists(self) -> None:
        """taxomesh_item_name_idx must be present on taxomesh_item."""
        assert "taxomesh_item_name_idx" in _index_names("taxomesh_item")

    def test_category_parent_link_composite_index_exists(self) -> None:
        """taxomesh_catlink_par_sort_idx must be present on taxomesh_category_parent_link."""
        assert "taxomesh_catlink_par_sort_idx" in _index_names("taxomesh_category_parent_link")

    def test_item_parent_link_composite_index_exists(self) -> None:
        """taxomesh_itemlink_cat_sort_idx must be present on taxomesh_item_parent_link."""
        assert "taxomesh_itemlink_cat_sort_idx" in _index_names("taxomesh_item_parent_link")
