"""Tests for Item.external_id type, default, and coercion (spec 041)."""

from uuid import uuid4

from taxomesh.domain.models import Item


def test_external_id_default_is_none() -> None:
    item = Item()
    assert item.external_id is None


def test_external_id_none_input_stays_none() -> None:
    item = Item(external_id=None)
    assert item.external_id is None


def test_external_id_str_input_stays_str() -> None:
    item = Item(external_id="abc-123")
    assert item.external_id == "abc-123"
    assert isinstance(item.external_id, str)


def test_external_id_int_coerced_to_str() -> None:
    item = Item(external_id=42)  # type: ignore[arg-type]
    assert item.external_id == "42"
    assert isinstance(item.external_id, str)


def test_external_id_uuid_coerced_to_str() -> None:
    uid = uuid4()
    item = Item(external_id=uid)  # type: ignore[arg-type]
    assert item.external_id == str(uid)
    assert isinstance(item.external_id, str)


def test_external_id_type_is_str_or_none() -> None:
    """external_id must be str or None — never an empty string by default."""
    item = Item()
    # Default must be None, not ""
    assert item.external_id is None
    assert item.external_id != ""


def test_external_id_annotation_accepts_none() -> None:
    """Pydantic model_fields should reflect str | None type."""
    field = Item.model_fields["external_id"]
    # Verify the field's default is None
    assert field.default is None
