"""Tests for audit fields (created_at, updated_at, version) on Category and Item.

TDD: timestamp tests (T009) are written before service stamping is implemented.
Version tests (T015) are added later in the same file.
"""

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def svc(tmp_path: Path) -> TaxomeshService:
    repo = JsonRepository(tmp_path / "db.json")
    return TaxomeshService(repository=repo)


@pytest.fixture()
def svc_path(tmp_path: Path) -> tuple[TaxomeshService, Path]:
    """Return (service, json_path) so tests can reload from disk."""
    path = tmp_path / "db.json"
    return TaxomeshService(repository=JsonRepository(path)), path


# ---------------------------------------------------------------------------
# Phase 3 / User Story 1 — Timestamps (T009)
# ---------------------------------------------------------------------------


def test_create_category_timestamps_set(svc: TaxomeshService) -> None:
    before = datetime.now(tz=UTC)
    cat = svc.create_category("Fruits")
    after = datetime.now(tz=UTC)

    assert cat.created_at.tzinfo is not None
    assert cat.updated_at.tzinfo is not None
    assert cat.created_at == cat.updated_at
    assert before <= cat.created_at <= after


def test_update_category_advances_updated_at(svc: TaxomeshService) -> None:
    cat = svc.create_category("Fruits")
    pre_update_updated_at = cat.updated_at
    pre_update_created_at = cat.created_at

    time.sleep(0.01)
    updated = svc.update_category(cat.category_id, name="Veggies")

    assert updated.updated_at >= pre_update_updated_at
    assert updated.created_at == pre_update_created_at


def test_create_item_timestamps_set(svc: TaxomeshService) -> None:
    before = datetime.now(tz=UTC)
    item = svc.create_item("Apple")
    after = datetime.now(tz=UTC)

    assert item.created_at.tzinfo is not None
    assert item.updated_at.tzinfo is not None
    assert item.created_at == item.updated_at
    assert before <= item.created_at <= after


def test_update_item_advances_updated_at(svc: TaxomeshService) -> None:
    item = svc.create_item("Apple")
    pre_update_updated_at = item.updated_at
    pre_update_created_at = item.created_at

    time.sleep(0.01)
    updated = svc.update_item(item.item_id, name="Orange")

    assert updated.updated_at >= pre_update_updated_at
    assert updated.created_at == pre_update_created_at


# ---------------------------------------------------------------------------
# Phase 3 / User Story 1 — JSON round-trip (T014)
# ---------------------------------------------------------------------------


def test_json_category_timestamps_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    cat = svc.create_category("Fruits")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.get_category(cat.category_id)

    assert reloaded.created_at == cat.created_at
    assert reloaded.updated_at == cat.updated_at


def test_json_item_timestamps_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    item = svc.create_item("Apple")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.get_item(item.item_id)

    assert reloaded.created_at == item.created_at
    assert reloaded.updated_at == item.updated_at


# ---------------------------------------------------------------------------
# Phase 4 / User Story 2 — Version (T015)
# ---------------------------------------------------------------------------


def test_create_category_version_is_zero(svc: TaxomeshService) -> None:
    cat = svc.create_category("Fruits")
    assert cat.version == 0


def test_update_category_increments_version(svc: TaxomeshService) -> None:
    cat = svc.create_category("Fruits")
    updated1 = svc.update_category(cat.category_id, name="Veggies")
    assert updated1.version == 1
    updated2 = svc.update_category(cat.category_id, name="Grains")
    assert updated2.version == 2


def test_create_item_version_is_zero(svc: TaxomeshService) -> None:
    item = svc.create_item("Apple")
    assert item.version == 0


def test_update_item_increments_version(svc: TaxomeshService) -> None:
    item = svc.create_item("Apple")
    updated1 = svc.update_item(item.item_id, name="Orange")
    assert updated1.version == 1
    updated2 = svc.update_item(item.item_id, name="Grape")
    assert updated2.version == 2


# ---------------------------------------------------------------------------
# Phase 4 / User Story 2 — JSON version round-trip (T020)
# ---------------------------------------------------------------------------


def test_json_category_version_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    cat = svc.create_category("Fruits")
    svc.update_category(cat.category_id, name="Veggies")
    svc.update_category(cat.category_id, name="Grains")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.get_category(cat.category_id)
    assert reloaded.version == 2


def test_json_item_version_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    item = svc.create_item("Apple")
    svc.update_item(item.item_id, name="Orange")
    svc.update_item(item.item_id, name="Grape")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.get_item(item.item_id)
    assert reloaded.version == 2


# ---------------------------------------------------------------------------
# Phase 5 — Edge cases and invariants (T021, T022)
# ---------------------------------------------------------------------------


def test_structural_operations_do_not_bump_version(svc: TaxomeshService) -> None:
    """Adding item to a category (structural) must not change item version or updated_at."""
    item = svc.create_item("Apple")
    cat = svc.create_category("Fruits")

    original_version = item.version
    original_updated_at = item.updated_at

    svc.place_item_in_category(item.item_id, cat.category_id)

    reloaded = svc.get_item(item.item_id)
    assert reloaded.version == original_version
    assert reloaded.updated_at == original_updated_at


def test_created_at_never_changes_after_multiple_updates(svc: TaxomeshService) -> None:
    """created_at is immutable across any number of updates."""
    cat = svc.create_category("Fruits")
    original_created_at = cat.created_at

    for name in ("Veggies", "Grains", "Herbs"):
        cat = svc.update_category(cat.category_id, name=name)
        assert cat.created_at == original_created_at
