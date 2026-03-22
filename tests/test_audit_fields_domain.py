"""Tests for audit field defaults on legacy deserialization (no created_at/updated_at/version in data)."""

import uuid

from taxomesh.domain.constants import AUDIT_EPOCH
from taxomesh.domain.models.category import Category
from taxomesh.domain.models.item import Item

# ---------------------------------------------------------------------------
# Phase 3 / US1 — legacy deserialization (T012)
# ---------------------------------------------------------------------------


def test_category_legacy_deserialization_missing_timestamps() -> None:
    cat = Category.model_validate({"category_id": str(uuid.uuid4()), "name": "Legacy"})
    assert cat.created_at == AUDIT_EPOCH
    assert cat.updated_at == AUDIT_EPOCH


def test_item_legacy_deserialization_missing_timestamps() -> None:
    item = Item.model_validate({"item_id": str(uuid.uuid4()), "name": "Legacy"})
    assert item.created_at == AUDIT_EPOCH
    assert item.updated_at == AUDIT_EPOCH


# ---------------------------------------------------------------------------
# Phase 4 / US2 — legacy deserialization (T018)
# ---------------------------------------------------------------------------


def test_category_legacy_deserialization_missing_version() -> None:
    cat = Category.model_validate({"category_id": str(uuid.uuid4()), "name": "Legacy"})
    assert cat.version == 0


def test_item_legacy_deserialization_missing_version() -> None:
    item = Item.model_validate({"item_id": str(uuid.uuid4()), "name": "Legacy"})
    assert item.version == 0
