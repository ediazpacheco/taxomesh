"""Tests for TaxomeshService.get_items_by_external_id and get_categories_by_external_id (spec 013)."""

from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, Item


@pytest.fixture
def svc(tmp_path: Path) -> TaxomeshService:
    return TaxomeshService(repository=JsonRepository(tmp_path / "test.json"))


# ---------------------------------------------------------------------------
# get_items_by_external_id — str external_id
# ---------------------------------------------------------------------------


def test_get_items_by_external_id_str_found(svc: TaxomeshService) -> None:
    item = svc.create_item("my-entity-uuid", "my-entity-uuid")
    results = svc.get_items_by_external_id("my-entity-uuid")
    assert len(results) == 1
    assert results[0].item_id == item.item_id


def test_get_items_by_external_id_str_not_found(svc: TaxomeshService) -> None:
    svc.create_item("other-id", "other-id")
    results = svc.get_items_by_external_id("my-entity-uuid")
    assert results == []


def test_get_items_by_external_id_empty_store(svc: TaxomeshService) -> None:
    results = svc.get_items_by_external_id("any-id")
    assert results == []


# ---------------------------------------------------------------------------
# get_items_by_external_id — int external_id
# ---------------------------------------------------------------------------


def test_get_items_by_external_id_int_found(svc: TaxomeshService) -> None:
    item = svc.create_item("42", 42)
    results = svc.get_items_by_external_id(42)
    assert len(results) == 1
    assert results[0].item_id == item.item_id


def test_get_items_by_external_id_int_not_found(svc: TaxomeshService) -> None:
    svc.create_item("99", 99)
    results = svc.get_items_by_external_id(42)
    assert results == []


# ---------------------------------------------------------------------------
# get_items_by_external_id — UUID external_id
# ---------------------------------------------------------------------------


def test_get_items_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    item = svc.create_item(str(ext), ext)
    results = svc.get_items_by_external_id(ext)
    assert len(results) == 1
    assert results[0].item_id == item.item_id


def test_get_items_by_external_id_uuid_not_found(svc: TaxomeshService) -> None:
    _u = uuid4()
    svc.create_item(str(_u), _u)
    results = svc.get_items_by_external_id(uuid4())
    assert results == []


# ---------------------------------------------------------------------------
# get_items_by_external_id — duplicate detection
# ---------------------------------------------------------------------------


def test_get_items_by_external_id_multiple_matches(svc: TaxomeshService) -> None:
    """Returns all items sharing the same external_id (consumer detects duplicates via len > 1)."""
    svc.create_item("dup-id", "dup-id")
    svc.create_item("dup-id", "dup-id")
    results = svc.get_items_by_external_id("dup-id")
    assert len(results) == 2


def test_get_items_by_external_id_returns_list_of_item_instances(svc: TaxomeshService) -> None:
    svc.create_item("check-type", "check-type")
    results = svc.get_items_by_external_id("check-type")
    assert all(isinstance(r, Item) for r in results)


# ---------------------------------------------------------------------------
# get_categories_by_external_id — str external_id
# ---------------------------------------------------------------------------


def test_get_categories_by_external_id_str_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Animals", external_id="ext-animals")
    svc.repository.save_category(cat)
    results = svc.get_categories_by_external_id("ext-animals")
    assert len(results) == 1
    assert results[0].category_id == cat.category_id


def test_get_categories_by_external_id_str_not_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="Plants", external_id="ext-plants")
    svc.repository.save_category(cat)
    results = svc.get_categories_by_external_id("nonexistent")
    assert results == []


def test_get_categories_by_external_id_empty_external_id_not_returned(svc: TaxomeshService) -> None:
    """Root category (external_id='') is not returned when searching for a non-empty external_id."""
    results = svc.get_categories_by_external_id("any-ext")
    assert results == []


def test_get_categories_by_external_id_root_not_returned_for_empty_string(svc: TaxomeshService) -> None:
    """Root category is excluded even when searching by its own external_id ('') — FR-002 / D-007."""
    results = svc.get_categories_by_external_id("")
    assert results == []


# ---------------------------------------------------------------------------
# get_categories_by_external_id — int and UUID
# ---------------------------------------------------------------------------


def test_get_categories_by_external_id_int_found(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="LevelOne", external_id=7)  # type: ignore[arg-type]
    svc.repository.save_category(cat)
    results = svc.get_categories_by_external_id(7)
    assert len(results) == 1
    assert results[0].category_id == cat.category_id


def test_get_categories_by_external_id_uuid_found(svc: TaxomeshService) -> None:
    ext = uuid4()
    cat = Category(category_id=uuid4(), name="UUIDCat", external_id=ext)  # type: ignore[arg-type]
    svc.repository.save_category(cat)
    results = svc.get_categories_by_external_id(ext)
    assert len(results) == 1
    assert results[0].category_id == cat.category_id


# ---------------------------------------------------------------------------
# get_categories_by_external_id — duplicate detection
# ---------------------------------------------------------------------------


def test_get_categories_by_external_id_multiple_matches(svc: TaxomeshService) -> None:
    """Returns all categories sharing the same external_id (consumer detects duplicates via len > 1)."""
    cat1 = Category(category_id=uuid4(), name="A", external_id="shared-ext")
    cat2 = Category(category_id=uuid4(), name="B", external_id="shared-ext")
    svc.repository.save_category(cat1)
    svc.repository.save_category(cat2)
    results = svc.get_categories_by_external_id("shared-ext")
    assert len(results) == 2


def test_get_categories_by_external_id_returns_list_of_category_instances(svc: TaxomeshService) -> None:
    cat = Category(category_id=uuid4(), name="TypeCheck", external_id="tc-ext")
    svc.repository.save_category(cat)
    results = svc.get_categories_by_external_id("tc-ext")
    assert all(isinstance(r, Category) for r in results)


# ---------------------------------------------------------------------------
# Smoke test — matches plan verification snippet
# ---------------------------------------------------------------------------


def test_smoke_get_items_by_external_id(tmp_path: Path) -> None:
    svc = TaxomeshService(repository=JsonRepository(tmp_path / "smoke.json"))
    svc.create_item("my-entity-uuid", "my-entity-uuid")
    results = svc.get_items_by_external_id("my-entity-uuid")
    assert len(results) == 1
