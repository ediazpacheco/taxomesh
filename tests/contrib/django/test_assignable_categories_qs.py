"""Tests for DjangoRepository.assignable_categories_qs() (spec 013)."""

from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import ROOT_CATEGORY_NAME  # noqa: E402
from taxomesh.contrib.django.models import CategoryModel  # noqa: E402

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_category(
    name: str,
    enabled: bool = True,
    external_id: str | None = None,
) -> CategoryModel:
    return CategoryModel.objects.create(
        category_id=uuid4(),
        name=name,
        enabled=enabled,
        external_id=external_id,
    )


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_assignable_categories_qs_returns_enabled_non_root_categories() -> None:
    _save_category("Electronics", enabled=True)
    _save_category("Clothing", enabled=True)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    names = set(qs.values_list("name", flat=True))
    assert "Electronics" in names
    assert "Clothing" in names


def test_assignable_categories_qs_excludes_root() -> None:
    _save_category(ROOT_CATEGORY_NAME, enabled=True)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    names = list(qs.values_list("name", flat=True))
    assert ROOT_CATEGORY_NAME not in names


def test_assignable_categories_qs_excludes_disabled_categories() -> None:
    _save_category("DisabledCat", enabled=False)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    names = list(qs.values_list("name", flat=True))
    assert "DisabledCat" not in names


def test_assignable_categories_qs_empty_when_only_root_and_disabled() -> None:
    _save_category(ROOT_CATEGORY_NAME, enabled=True)
    _save_category("Hidden", enabled=False)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    assert qs.count() == 0


def test_assignable_categories_qs_returns_queryset_of_category_model() -> None:
    _save_category("Tech", enabled=True)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    assert qs.count() >= 1
    for row in qs:
        assert isinstance(row, CategoryModel)


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


def test_assignable_categories_qs_mixed_enabled_disabled_root() -> None:
    _save_category(ROOT_CATEGORY_NAME, enabled=True)
    _save_category("Active", enabled=True)
    _save_category("Inactive", enabled=False)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    names = set(qs.values_list("name", flat=True))
    assert names == {"Active"}


def test_assignable_categories_qs_empty_store() -> None:
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    assert qs.count() == 0


def test_assignable_categories_qs_returns_lazy_queryset() -> None:
    """Result is a QuerySet (supports .filter(), .order_by(), etc)."""
    _save_category("Lazy", enabled=True)
    repo = DjangoRepository()
    qs = repo.assignable_categories_qs()
    # QuerySets support chaining
    filtered = qs.filter(name="Lazy")
    assert filtered.count() == 1
