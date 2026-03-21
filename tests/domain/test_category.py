"""Tests for Category.external_id type, default, and coercion (spec 041)."""

from uuid import uuid4

from taxomesh.domain.models import Category


def test_external_id_default_is_none() -> None:
    cat = Category(name="Test")
    assert cat.external_id is None


def test_external_id_none_input_stays_none() -> None:
    cat = Category(name="Test", external_id=None)
    assert cat.external_id is None


def test_external_id_str_input_stays_str() -> None:
    cat = Category(name="Test", external_id="abc-123")
    assert cat.external_id == "abc-123"
    assert isinstance(cat.external_id, str)


def test_external_id_int_coerced_to_str() -> None:
    cat = Category(name="Test", external_id=42)  # type: ignore[arg-type]
    assert cat.external_id == "42"
    assert isinstance(cat.external_id, str)


def test_external_id_uuid_coerced_to_str() -> None:
    uid = uuid4()
    cat = Category(name="Test", external_id=uid)  # type: ignore[arg-type]
    assert cat.external_id == str(uid)
    assert isinstance(cat.external_id, str)


def test_external_id_type_is_str_or_none() -> None:
    """external_id must be str or None — never an empty string by default."""
    cat = Category(name="Test")
    assert cat.external_id is None
    assert cat.external_id != ""


def test_external_id_annotation_default_is_none() -> None:
    """Pydantic model_fields should reflect str | None type with default None."""
    field = Category.model_fields["external_id"]
    assert field.default is None
