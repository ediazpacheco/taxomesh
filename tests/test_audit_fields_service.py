"""Tests for audit fields (created_at, updated_at, version) on Category and Item."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, Item

# A stored row's timestamps, earlier than any update this suite makes.
_PAST: Final = datetime(2020, 1, 1, tzinfo=UTC)

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
# Timestamps
# ---------------------------------------------------------------------------


def test_categories_create_timestamps_set(svc: TaxomeshService) -> None:
    before = datetime.now(tz=UTC)
    cat = svc.categories.create("Fruits")
    after = datetime.now(tz=UTC)

    assert cat.created_at.tzinfo is not None
    assert cat.updated_at.tzinfo is not None
    assert cat.created_at == cat.updated_at
    assert before <= cat.created_at <= after


def test_categories_update_advances_updated_at(svc: TaxomeshService) -> None:
    stored = svc.repository.save_category(Category(name="Fruits", created_at=_PAST, updated_at=_PAST))

    updated = svc.categories.update(stored.category_id, name="Veggies")

    assert updated.updated_at > _PAST
    assert updated.created_at == _PAST


def test_items_create_timestamps_set(svc: TaxomeshService) -> None:
    before = datetime.now(tz=UTC)
    item = svc.items.create("Apple")
    after = datetime.now(tz=UTC)

    assert item.created_at.tzinfo is not None
    assert item.updated_at.tzinfo is not None
    assert item.created_at == item.updated_at
    assert before <= item.created_at <= after


def test_items_update_advances_updated_at(svc: TaxomeshService) -> None:
    stored = svc.repository.save_item(Item(name="Apple", created_at=_PAST, updated_at=_PAST))

    updated = svc.items.update(stored.item_id, name="Orange")

    assert updated.updated_at > _PAST
    assert updated.created_at == _PAST


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_json_category_timestamps_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    cat = svc.categories.create("Fruits")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.categories[cat.category_id]

    assert reloaded.created_at == cat.created_at
    assert reloaded.updated_at == cat.updated_at


def test_json_item_timestamps_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    item = svc.items.create("Apple")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.items[item.item_id]

    assert reloaded.created_at == item.created_at
    assert reloaded.updated_at == item.updated_at


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def test_categories_create_version_is_zero(svc: TaxomeshService) -> None:
    cat = svc.categories.create("Fruits")
    assert cat.version == 0


def test_categories_update_increments_version(svc: TaxomeshService) -> None:
    cat = svc.categories.create("Fruits")
    updated1 = svc.categories.update(cat.category_id, name="Veggies")
    assert updated1.version == 1
    updated2 = svc.categories.update(cat.category_id, name="Grains")
    assert updated2.version == 2


def test_items_create_version_is_zero(svc: TaxomeshService) -> None:
    item = svc.items.create("Apple")
    assert item.version == 0


def test_items_update_increments_version(svc: TaxomeshService) -> None:
    item = svc.items.create("Apple")
    updated1 = svc.items.update(item.item_id, name="Orange")
    assert updated1.version == 1
    updated2 = svc.items.update(item.item_id, name="Grape")
    assert updated2.version == 2


# ---------------------------------------------------------------------------
# JSON version round-trip
# ---------------------------------------------------------------------------


def test_json_category_version_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    cat = svc.categories.create("Fruits")
    svc.categories.update(cat.category_id, name="Veggies")
    svc.categories.update(cat.category_id, name="Grains")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.categories[cat.category_id]
    assert reloaded.version == 2


def test_json_item_version_roundtrip(svc_path: tuple[TaxomeshService, Path]) -> None:
    svc, path = svc_path
    item = svc.items.create("Apple")
    svc.items.update(item.item_id, name="Orange")
    svc.items.update(item.item_id, name="Grape")

    svc2 = TaxomeshService(repository=JsonRepository(path))
    reloaded = svc2.items[item.item_id]
    assert reloaded.version == 2


# ---------------------------------------------------------------------------
# Edge cases and invariants
# ---------------------------------------------------------------------------


def test_structural_operations_do_not_bump_version(svc: TaxomeshService) -> None:
    """Adding item to a category (structural) must not change item version or updated_at."""
    item = svc.items.create("Apple")
    cat = svc.categories.create("Fruits")

    original_version = item.version
    original_updated_at = item.updated_at

    svc.items.place_in(item.item_id, cat.category_id)

    reloaded = svc.items[item.item_id]
    assert reloaded.version == original_version
    assert reloaded.updated_at == original_updated_at


def test_created_at_never_changes_after_multiple_updates(svc: TaxomeshService) -> None:
    """created_at is immutable across any number of updates."""
    cat = svc.categories.create("Fruits")
    original_created_at = cat.created_at

    for name in ("Veggies", "Grains", "Herbs"):
        cat = svc.categories.update(cat.category_id, name=name)
        assert cat.created_at == original_created_at
