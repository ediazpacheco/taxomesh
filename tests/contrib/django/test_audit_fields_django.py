"""Django round-trip tests for audit fields (created_at, updated_at, version)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture()
def repo() -> DjangoRepository:
    return DjangoRepository()


# ---------------------------------------------------------------------------
# Phase 3 / US1 — Timestamp round-trips (T013)
# ---------------------------------------------------------------------------


def test_django_category_timestamps_roundtrip(repo: DjangoRepository) -> None:
    ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
    cat = Category(category_id=uuid4(), name="Roundtrip", created_at=ts, updated_at=ts)
    repo.save_category(cat)

    reloaded = repo.get_category(cat.category_id)
    assert reloaded is not None
    assert reloaded.created_at == ts
    assert reloaded.updated_at == ts


def test_django_item_timestamps_roundtrip(repo: DjangoRepository) -> None:
    ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
    item = Item(item_id=uuid4(), name="Roundtrip", created_at=ts, updated_at=ts)
    repo.save_item(item)

    reloaded = repo.get_item(item.item_id)
    assert reloaded is not None
    assert reloaded.created_at == ts
    assert reloaded.updated_at == ts


# ---------------------------------------------------------------------------
# Phase 4 / US2 — Version round-trips (T019)
# ---------------------------------------------------------------------------


def test_django_category_version_roundtrip(repo: DjangoRepository) -> None:
    cat = Category(category_id=uuid4(), name="Versioned")
    repo.save_category(cat)  # create → version 0
    repo.save_category(cat)  # update → version 1
    repo.save_category(cat)  # update → version 2
    repo.save_category(cat)  # update → version 3

    reloaded = repo.get_category(cat.category_id)
    assert reloaded is not None
    assert reloaded.version == 3


def test_django_item_version_roundtrip(repo: DjangoRepository) -> None:
    item = Item(item_id=uuid4(), name="Versioned")
    repo.save_item(item)  # create → version 0
    repo.save_item(item)  # update → version 1
    repo.save_item(item)  # update → version 2
    repo.save_item(item)  # update → version 3

    reloaded = repo.get_item(item.item_id)
    assert reloaded is not None
    assert reloaded.version == 3
