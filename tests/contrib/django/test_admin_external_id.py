"""Tests for Django admin external_id handling when value is None (spec 041)."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")


class TestResolveLinkedUrl:
    """_resolve_linked_url must return None when external_id is None."""

    def test_returns_none_for_none_external_id(self) -> None:
        from taxomesh.contrib.django.admin import _resolve_linked_url  # noqa: PLC0415

        result = _resolve_linked_url(None)  # type: ignore[arg-type]
        assert result is None

    def test_returns_none_for_empty_string(self) -> None:
        from taxomesh.contrib.django.admin import _resolve_linked_url  # noqa: PLC0415

        result = _resolve_linked_url("")
        assert result is None


class TestGraphEntryExternalId:
    """GraphEntry external_id field accepts str | None."""

    def test_graph_entry_external_id_type_allows_none(self) -> None:
        import typing  # noqa: PLC0415

        from taxomesh.contrib.django.admin import GraphEntry  # noqa: PLC0415

        hints = typing.get_type_hints(GraphEntry)
        # external_id must be annotated as str | None (not plain str)
        field_type = hints["external_id"]
        # Accept Union[str, None] or str | None (both are Optional[str])
        assert field_type is not str, "GraphEntry.external_id must be str | None after spec 041, got plain str"


class TestExternalIdWithLinkRendering:
    """ExternalIdLinkMixin.external_id_with_link returns empty string for None."""

    @pytest.mark.django_db
    def test_returns_empty_string_for_none_external_id(self) -> None:
        from unittest.mock import MagicMock  # noqa: PLC0415

        from taxomesh.contrib.django.admin import TaxomeshAdminMixin  # noqa: PLC0415

        mixin = TaxomeshAdminMixin()
        obj = MagicMock()
        obj.external_id = None
        result = mixin.external_id_with_link(obj)
        assert result == ""
        assert "None" not in result
