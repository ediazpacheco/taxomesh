"""Parity regressions for partial updates through the public API handlers.

Verifies FR-016 / User Story 2 across every supported storage backend: an omitted
field carries no instruction, so a partial update mentioning a strict subset of an
entity's fields leaves every unmentioned field untouched. The three external-identifier
intents (preserve, replace, clear) are exercised through the item handler on each backend.

These tests live under ``tests/service/`` deliberately: the parametrized ``service``
fixture (in ``tests/service/conftest.py``) runs each test once per backend
(in-memory, JSON, YAML, Django). ``tests/contrib/`` overrides that fixture with an
in-memory-only one, which is how the original US2 coverage gap arose.
"""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.schemas import (
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Item — the external-identifier intents (preserve / replace / clear)
# ---------------------------------------------------------------------------


def test_item_name_only_update_preserves_external_id(service: TaxomeshService) -> None:
    """Renaming an item leaves its stored external identifier untouched (US2 scenario 1)."""
    item = service.create_item(name="Item", external_id="ext-original")
    result = handlers.update_item(service, item.item_id, UpdateItemRequest(name="Renamed"))
    assert result.name == "Renamed"
    assert result.external_id == "ext-original"


def test_item_explicit_string_replaces_external_id(service: TaxomeshService) -> None:
    """A supplied external identifier string replaces the stored value (US2 scenario 2)."""
    item = service.create_item(name="Item", external_id="ext-original")
    result = handlers.update_item(service, item.item_id, UpdateItemRequest(external_id="ext-new"))
    assert result.external_id == "ext-new"


def test_item_explicit_null_clears_external_id(service: TaxomeshService) -> None:
    """An explicit null external identifier clears the stored value (US2 scenario 3)."""
    item = service.create_item(name="Item", external_id="ext-original")
    result = handlers.update_item(service, item.item_id, UpdateItemRequest(external_id=None))
    assert result.external_id is None


def test_item_empty_body_is_noop(service: TaxomeshService) -> None:
    """A partial update mentioning no fields changes nothing (US2 scenario 5)."""
    item = service.create_item(name="Item", external_id="ext-original", slug="the-item")
    result = handlers.update_item(service, item.item_id, UpdateItemRequest())
    assert result.name == "Item"
    assert result.external_id == "ext-original"
    assert result.slug == "the-item"
    assert result.enabled is True


def test_item_name_only_update_preserves_every_other_field(service: TaxomeshService) -> None:
    """A single-field item update leaves all unmentioned fields untouched (US2 scenario 6)."""
    item = service.create_item(
        name="Item",
        external_id="ext-original",
        slug="the-item",
        metadata={"k": "v"},
    )
    result = handlers.update_item(service, item.item_id, UpdateItemRequest(name="Renamed"))
    assert result.name == "Renamed"
    assert result.external_id == "ext-original"
    assert result.slug == "the-item"
    assert result.metadata == {"k": "v"}
    assert result.enabled is True


# ---------------------------------------------------------------------------
# Category — subset preservation (US2 scenario 6)
# ---------------------------------------------------------------------------


def test_category_name_only_update_preserves_every_other_field(service: TaxomeshService) -> None:
    """A single-field category update leaves all unmentioned fields untouched."""
    category = service.create_category(
        name="Fiction",
        description="All fiction",
        slug="fiction",
        metadata={"k": "v"},
    )
    result = handlers.update_category(service, category.category_id, UpdateCategoryRequest(name="Novels"))
    assert result.name == "Novels"
    assert result.description == "All fiction"
    assert result.slug == "fiction"
    assert result.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# Tag — subset preservation (US2 scenario 6)
# ---------------------------------------------------------------------------


def test_tag_name_only_update_preserves_metadata(service: TaxomeshService) -> None:
    """Renaming a tag leaves its stored metadata untouched."""
    tag = service.create_tag(name="scifi", metadata={"k": "v"})
    result = handlers.update_tag(service, tag.tag_id, UpdateTagRequest(name="sci-fi"))
    assert result.name == "sci-fi"
    assert result.metadata == {"k": "v"}
