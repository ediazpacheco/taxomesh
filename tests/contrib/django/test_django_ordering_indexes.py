"""Schema introspection tests for ordering indexes (035-django-ordering-indexes).

Verifies that the four database indexes introduced by migration 0005 are present
after `migrate` runs. Correctness of ordering behaviour is already covered by
tests/contrib/django/test_django_repository_ordering.py (spec 034).
"""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402

pytestmark = pytest.mark.django_db


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
        """taxomesh_catlink_parent_sort_idx must be present on taxomesh_category_parent_link."""
        assert "taxomesh_catlink_parent_sort_idx" in _index_names("taxomesh_category_parent_link")

    def test_item_parent_link_composite_index_exists(self) -> None:
        """taxomesh_itemlink_cat_sort_idx must be present on taxomesh_item_parent_link."""
        assert "taxomesh_itemlink_cat_sort_idx" in _index_names("taxomesh_item_parent_link")
