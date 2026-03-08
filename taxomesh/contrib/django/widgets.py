"""Custom Django admin widgets for taxomesh FK fields."""

from typing import Any

from django.contrib.admin.widgets import AutocompleteSelect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class TaxomeshLinkedFKWidget(AutocompleteSelect):
    """AutocompleteSelect widget that appends a '↗' admin change link when a value is selected.

    Renders a compact Select2 autocomplete for any ForeignKey field, plus an inline
    navigation link to the Django admin change page of the selected instance.  The
    change URL is derived generically from the related model's ``_meta`` attributes so
    the widget works for any FK target registered in the Django admin — no model names
    are hardcoded.

    The link is rendered server-side only: it reflects the value persisted at page-load
    time and updates after the user saves the form.  When no value is selected, or when
    the change URL cannot be resolved, the widget renders identically to the standard
    ``AutocompleteSelect``.

    Usage (per-field widget override)::

        from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget

        class MyForm(forms.ModelForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["item"].widget = TaxomeshLinkedFKWidget(
                    field=MyModel._meta.get_field("item"),
                    admin_site=admin.site,
                )

    For a drop-in solution that applies automatically, see
    ``taxomesh.contrib.django.admin.TaxomeshLinkedFKMixin``.
    """

    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: object = None,
    ) -> str:
        """Render the autocomplete select and, when a value is set, a '↗' change link.

        Args:
            name: The HTML input name attribute.
            value: The current field value (FK pk), or ``None`` / empty if not set.
            attrs: Optional HTML attributes dict passed to the underlying widget.
            renderer: Django form renderer (passed through to parent; added in Django 4.0).

        Returns:
            Safe HTML string containing the Select2 widget and, conditionally, a
            navigation link to the admin change page of the selected instance.
        """
        output = super().render(name, value, attrs, renderer)
        if not value:
            return output
        try:
            target_model = self.field.remote_field.model
            app_label = target_model._meta.app_label
            model_name = target_model._meta.model_name
            url = reverse(f"admin:{app_label}_{model_name}_change", args=[value])
            link = format_html(
                ' <a href="{}" title="Ver en admin" style="margin-left:4px">&#8599;</a>',
                url,
            )
            return mark_safe(output + link)
        except (NoReverseMatch, Exception):  # noqa: BLE001
            return output
