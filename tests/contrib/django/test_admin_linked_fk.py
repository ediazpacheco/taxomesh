"""Tests for TaxomeshLinkedFKWidget and TaxomeshLinkedFKMixin."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_widget(related_model: Any) -> Any:
    """Build a TaxomeshLinkedFKWidget with a mocked field pointing to related_model."""
    from django.contrib import admin  # noqa: PLC0415

    from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget  # noqa: PLC0415

    mock_field = MagicMock()
    mock_field.remote_field.model = related_model
    mock_field.remote_field.field_name = related_model._meta.pk.attname
    mock_field.model = related_model
    mock_field.name = "item"
    mock_field.db = None
    # AutocompleteMixin.optgroups accesses self.choices.field.empty_values
    mock_choices = MagicMock()
    mock_choices.field.empty_values = ["", None]
    widget = TaxomeshLinkedFKWidget.__new__(TaxomeshLinkedFKWidget)
    widget.field = mock_field
    widget.admin_site = admin.site
    widget.db = None
    widget.choices = mock_choices
    widget.attrs = {}
    widget.i18n_name = None
    return widget


# ---------------------------------------------------------------------------
# T002 — render() with no value returns no '↗' link
# ---------------------------------------------------------------------------


def test_widget_render_no_value() -> None:
    """render() with value=None must not include a navigation link."""
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    widget = _make_widget(ItemModel)
    with patch.object(type(widget).__bases__[0], "render", return_value="<select></select>"):
        output = widget.render("item", None)
    assert "↗" not in output
    assert "&#8599;" not in output
    assert "Ver en admin" not in output


def test_widget_render_empty_string_value() -> None:
    """render() with value='' must not include a navigation link."""
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    widget = _make_widget(ItemModel)
    with patch.object(type(widget).__bases__[0], "render", return_value="<select></select>"):
        output = widget.render("item", "")
    assert "&#8599;" not in output


# ---------------------------------------------------------------------------
# T003 — render() with a valid ItemModel pk returns a '↗' link to item change URL
# ---------------------------------------------------------------------------


def test_widget_render_with_item_value(db: object) -> None:
    """render() with a valid ItemModel pk includes a '↗' link to the item change page."""
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    item = ItemModel.objects.create(name="Test Item", external_id="ext-001")
    widget = _make_widget(ItemModel)
    with patch.object(type(widget).__bases__[0], "render", return_value="<select></select>"):
        output = widget.render("item", str(item.item_id))
    assert "&#8599;" in output
    assert "Ver en admin" in output
    assert str(item.item_id) in output
    # URL must point to ItemModel admin change page
    expected_url_fragment = f"/admin/taxomesh_contrib_django/itemmodel/{item.item_id}/change/"
    assert expected_url_fragment in output


# ---------------------------------------------------------------------------
# T004 — render() with unresolvable URL does not raise and returns no link
# ---------------------------------------------------------------------------


def test_widget_render_unresolvable_url() -> None:
    """render() with a value whose URL cannot be reversed returns output without link."""
    from django.urls import NoReverseMatch  # noqa: PLC0415

    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415

    widget = _make_widget(ItemModel)
    with (
        patch.object(type(widget).__bases__[0], "render", return_value="<select></select>"),
        patch("taxomesh.contrib.django.widgets.reverse", side_effect=NoReverseMatch("no match")),
    ):
        output = widget.render("item", "some-pk-value")
    assert "&#8599;" not in output
    # Must not raise


# ---------------------------------------------------------------------------
# T007 — render() with a valid CategoryModel pk returns a '↗' link to category change URL
# ---------------------------------------------------------------------------


def test_widget_render_with_category_value(db: object) -> None:
    """render() with a valid CategoryModel pk includes a '↗' link to the category change page."""
    from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415

    category = CategoryModel.objects.create(name="Test Category")
    widget = _make_widget(CategoryModel)
    # Override field.name to match category FK convention
    widget.field.name = "category"
    with patch.object(type(widget).__bases__[0], "render", return_value="<select></select>"):
        output = widget.render("category", str(category.category_id))
    assert "&#8599;" in output
    assert "Ver en admin" in output
    expected_url_fragment = f"/admin/taxomesh_contrib_django/categorymodel/{category.category_id}/change/"
    assert expected_url_fragment in output


# ---------------------------------------------------------------------------
# T009 — TaxomeshLinkedFKMixin: Item FK field uses TaxomeshLinkedFKWidget
# ---------------------------------------------------------------------------


def test_mixin_item_fk_uses_widget() -> None:
    """formfield_for_foreignkey returns TaxomeshLinkedFKWidget for an ItemModel FK."""
    from django.contrib import admin  # noqa: PLC0415
    from django.http import HttpRequest  # noqa: PLC0415

    from taxomesh.contrib.django.admin import TaxomeshLinkedFKMixin  # noqa: PLC0415
    from taxomesh.contrib.django.models import ItemModel  # noqa: PLC0415
    from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget  # noqa: PLC0415

    mock_db_field = MagicMock()
    mock_db_field.related_model = ItemModel
    mock_db_field.remote_field.model = ItemModel

    class _TestAdmin(TaxomeshLinkedFKMixin, admin.ModelAdmin):  # type: ignore[type-arg]
        pass

    ma = _TestAdmin.__new__(_TestAdmin)
    ma.admin_site = admin.site

    request = HttpRequest()

    # Patch super().formfield_for_foreignkey to capture kwargs
    captured: dict[str, Any] = {}

    def _fake_super_formfield(db_field: Any, request: Any, **kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    def _fake_super_formfield(_self: Any, db_field: Any, request: Any, **kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with patch.object(admin.ModelAdmin, "formfield_for_foreignkey", _fake_super_formfield):
        ma.formfield_for_foreignkey(mock_db_field, request)

    assert "widget" in captured
    assert isinstance(captured["widget"], TaxomeshLinkedFKWidget)


# ---------------------------------------------------------------------------
# T010 — TaxomeshLinkedFKMixin: Category FK field uses TaxomeshLinkedFKWidget
# ---------------------------------------------------------------------------


def test_mixin_category_fk_uses_widget() -> None:
    """formfield_for_foreignkey returns TaxomeshLinkedFKWidget for a CategoryModel FK."""
    from django.contrib import admin  # noqa: PLC0415
    from django.http import HttpRequest  # noqa: PLC0415

    from taxomesh.contrib.django.admin import TaxomeshLinkedFKMixin  # noqa: PLC0415
    from taxomesh.contrib.django.models import CategoryModel  # noqa: PLC0415
    from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget  # noqa: PLC0415

    mock_db_field = MagicMock()
    mock_db_field.related_model = CategoryModel
    mock_db_field.remote_field.model = CategoryModel

    class _TestAdmin(TaxomeshLinkedFKMixin, admin.ModelAdmin):  # type: ignore[type-arg]
        pass

    ma = _TestAdmin.__new__(_TestAdmin)
    ma.admin_site = admin.site

    request = HttpRequest()
    captured: dict[str, Any] = {}

    def _fake_super_formfield(_self: Any, db_field: Any, request: Any, **kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with patch.object(admin.ModelAdmin, "formfield_for_foreignkey", _fake_super_formfield):
        ma.formfield_for_foreignkey(mock_db_field, request)

    assert "widget" in captured
    assert isinstance(captured["widget"], TaxomeshLinkedFKWidget)


# ---------------------------------------------------------------------------
# T011 — TaxomeshLinkedFKMixin: unrelated FK does not use TaxomeshLinkedFKWidget
# ---------------------------------------------------------------------------


def test_mixin_unrelated_fk_unchanged() -> None:
    """formfield_for_foreignkey does not inject TaxomeshLinkedFKWidget for unrelated FKs."""
    from django.contrib import admin  # noqa: PLC0415
    from django.contrib.auth.models import User  # noqa: PLC0415
    from django.http import HttpRequest  # noqa: PLC0415

    from taxomesh.contrib.django.admin import TaxomeshLinkedFKMixin  # noqa: PLC0415
    from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget  # noqa: PLC0415

    mock_db_field = MagicMock()
    mock_db_field.related_model = User  # unrelated model

    class _TestAdmin(TaxomeshLinkedFKMixin, admin.ModelAdmin):  # type: ignore[type-arg]
        pass

    ma = _TestAdmin.__new__(_TestAdmin)
    ma.admin_site = admin.site

    request = HttpRequest()
    captured: dict[str, Any] = {}

    def _fake_super_formfield(_self: Any, db_field: Any, request: Any, **kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with patch.object(admin.ModelAdmin, "formfield_for_foreignkey", _fake_super_formfield):
        ma.formfield_for_foreignkey(mock_db_field, request)

    # No 'widget' key injected, or if injected it must not be TaxomeshLinkedFKWidget
    assert "widget" not in captured or not isinstance(captured.get("widget"), TaxomeshLinkedFKWidget)
