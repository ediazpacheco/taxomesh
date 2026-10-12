"""Partial updates through the public API handlers, on every backend.

An omitted field carries no instruction, so a partial update mentioning a strict subset of an
entity's fields leaves every unmentioned field untouched. The three external-identifier
intents (preserve, replace, clear) are exercised through the item handler on each backend.

These tests live under ``tests/service/`` deliberately: the parametrized ``service``
fixture (in ``tests/service/conftest.py``) runs each test once per backend
(in-memory, JSON, YAML, Django). ``tests/contrib/`` overrides that fixture with an
in-memory-only one, which would leave the other three untested.
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
    """Renaming an item leaves its stored external identifier untouched."""
    item = service.items.create(name="Item", external_id="ext-original")
    result = handlers.items_update(service, item.item_id, body=UpdateItemRequest(name="Renamed"))
    assert result.name == "Renamed"
    assert result.external_id == "ext-original"


def test_item_explicit_string_replaces_external_id(service: TaxomeshService) -> None:
    """A supplied external identifier string replaces the stored value."""
    item = service.items.create(name="Item", external_id="ext-original")
    result = handlers.items_update(service, item.item_id, body=UpdateItemRequest(external_id="ext-new"))
    assert result.external_id == "ext-new"


def test_item_explicit_null_clears_external_id(service: TaxomeshService) -> None:
    """An explicit null external identifier clears the stored value."""
    item = service.items.create(name="Item", external_id="ext-original")
    result = handlers.items_update(service, item.item_id, body=UpdateItemRequest(external_id=None))
    assert result.external_id is None


def test_item_empty_body_is_noop(service: TaxomeshService) -> None:
    """A partial update mentioning no fields changes nothing."""
    item = service.items.create(name="Item", external_id="ext-original", slug="the-item")
    result = handlers.items_update(service, item.item_id, body=UpdateItemRequest())
    assert result.name == "Item"
    assert result.external_id == "ext-original"
    assert result.slug == "the-item"
    assert result.enabled is True


def test_item_name_only_update_preserves_every_other_field(service: TaxomeshService) -> None:
    """A single-field item update leaves all unmentioned fields untouched."""
    item = service.items.create(
        name="Item",
        external_id="ext-original",
        slug="the-item",
        metadata={"k": "v"},
    )
    result = handlers.items_update(service, item.item_id, body=UpdateItemRequest(name="Renamed"))
    assert result.name == "Renamed"
    assert result.external_id == "ext-original"
    assert result.slug == "the-item"
    assert result.metadata == {"k": "v"}
    assert result.enabled is True


# ---------------------------------------------------------------------------
# Category — subset preservation
# ---------------------------------------------------------------------------


def test_category_name_only_update_preserves_every_other_field(service: TaxomeshService) -> None:
    """A single-field category update leaves all unmentioned fields untouched."""
    category = service.categories.create(
        name="Fiction",
        description="All fiction",
        slug="fiction",
        metadata={"k": "v"},
    )
    result = handlers.categories_update(service, category.category_id, body=UpdateCategoryRequest(name="Novels"))
    assert result.name == "Novels"
    assert result.description == "All fiction"
    assert result.slug == "fiction"
    assert result.metadata == {"k": "v"}


# ---------------------------------------------------------------------------
# Tag — subset preservation
# ---------------------------------------------------------------------------


def test_tag_name_only_update_preserves_metadata(service: TaxomeshService) -> None:
    """Renaming a tag leaves its stored metadata untouched.

    Until the tag-update schema carried ``metadata``, this passed for a weaker reason than it
    appears to: the handler had no metadata to forward, so "untouched" was vacuously true. The
    schema can now express the field, so the omission is a real instruction being honoured.
    """
    tag = service.tags.create(name="scifi", metadata={"k": "v"})
    result = handlers.tags_update(service, tag.tag_id, body=UpdateTagRequest(name="sci-fi"))
    assert result.name == "sci-fi"
    assert result.metadata == {"k": "v"}


def test_tag_metadata_only_update_preserves_name(service: TaxomeshService) -> None:
    """The inverse subset: replacing metadata alone leaves the stored name untouched.

    Asserted by reading the tag back through ``service.tags[...]`` rather than trusting the
    returned object: three of the four repositories return the same instance that they store,
    so a return-value assertion would pass on those three even if nothing were persisted.
    """
    tag = service.tags.create(name="scifi", metadata={"k": "v"})
    handlers.tags_update(service, tag.tag_id, body=UpdateTagRequest(metadata={"k": "w"}))
    stored = service.tags[tag.tag_id]
    assert stored.name == "scifi"
    assert stored.metadata == {"k": "w"}
