"""Audit fields a stored row omits take their defaults when it loads."""

import uuid

from taxomesh.domain.constants import AUDIT_EPOCH
from taxomesh.domain.models.category import Category
from taxomesh.domain.models.item import Item

# ---------------------------------------------------------------------------
# Missing timestamps
# ---------------------------------------------------------------------------


def test_category_data_without_timestamps_loads_at_the_epoch() -> None:
    cat = Category.model_validate({"category_id": str(uuid.uuid4()), "name": "Stored"})
    assert cat.created_at == AUDIT_EPOCH
    assert cat.updated_at == AUDIT_EPOCH


def test_item_data_without_timestamps_loads_at_the_epoch() -> None:
    item = Item.model_validate({"item_id": str(uuid.uuid4()), "name": "Stored"})
    assert item.created_at == AUDIT_EPOCH
    assert item.updated_at == AUDIT_EPOCH


# ---------------------------------------------------------------------------
# Missing version
# ---------------------------------------------------------------------------


def test_category_data_without_a_version_loads_at_zero() -> None:
    cat = Category.model_validate({"category_id": str(uuid.uuid4()), "name": "Stored"})
    assert cat.version == 0


def test_item_data_without_a_version_loads_at_zero() -> None:
    item = Item.model_validate({"item_id": str(uuid.uuid4()), "name": "Stored"})
    assert item.version == 0
