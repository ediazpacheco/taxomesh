"""Tests for CLI external_id handling (spec 041)."""

from uuid import UUID, uuid4

from taxomesh.adapters.cli.main import _parse_external_id


class TestParseExternalId:
    def test_empty_string_returns_none(self) -> None:
        assert _parse_external_id("") is None

    def test_valid_uuid_string_returns_uuid(self) -> None:
        uid = uuid4()
        result = _parse_external_id(str(uid))
        assert isinstance(result, UUID)
        assert result == uid

    def test_integer_string_returns_int(self) -> None:
        result = _parse_external_id("42")
        assert isinstance(result, int)
        assert result == 42

    def test_plain_string_returns_str(self) -> None:
        result = _parse_external_id("my-external-id")
        assert result == "my-external-id"

    def test_return_type_is_none_for_empty(self) -> None:
        result = _parse_external_id("")
        assert result is None


class TestCliExternalIdDisplay:
    """Verify that None external_id does not render as 'None' in CLI output."""

    def test_item_str_with_none_external_id_omits_ext_id(self) -> None:
        from taxomesh.domain.models import Item  # noqa: PLC0415

        item = Item(item_id=uuid4(), name="Test", external_id=None)
        rendered = str(item)
        assert "None" not in rendered
        assert "ext_id" not in rendered

    def test_item_str_with_none_external_id_not_empty_dash(self) -> None:
        """None external_id renders as empty indicator, not literal 'None'."""
        from taxomesh.domain.models import Item  # noqa: PLC0415

        item = Item(item_id=uuid4(), name="Product", external_id=None)
        rendered = str(item)
        # The rendered string must not contain the Python literal "None"
        assert "None" not in rendered
