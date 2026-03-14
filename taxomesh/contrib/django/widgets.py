"""Custom Django admin widgets for taxomesh FK fields."""

import json
from typing import Any, Final

from django import forms
from django.contrib.admin.widgets import AutocompleteSelect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

ACE_EDITOR_CDN_URL: Final[str] = "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js"
ACE_EDITOR_BASE_PATH: Final[str] = "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/"


class JsonEditorWidget(forms.Widget):
    """Ace Editor widget for JSONField — syntax highlighting + real-time validation.

    Renders a hidden ``<textarea>`` (the actual form submission target) paired with an
    Ace Editor div that provides JSON syntax highlighting, auto-indentation, and a
    web-worker-powered real-time validation indicator.  A ``submit`` event listener
    blocks form submission when the editor contains syntactically invalid JSON.

    The Ace library is loaded from jsDelivr CDN; no new Python runtime dependency is
    introduced.
    """

    class Media:
        js = (ACE_EDITOR_CDN_URL,)

    def __init__(self, attrs: dict[str, Any] | None = None, height: str = "300px") -> None:
        super().__init__(attrs=attrs)
        self.height = height

    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: object = None,
    ) -> str:
        """Render hidden textarea + Ace editor div + initialisation script."""
        # Normalise value to a JSON string
        if value is None:
            json_str = "{}"
        elif isinstance(value, str):
            # Django's JSONField.prepare_value() returns compact JSON; re-indent for readability.
            try:
                json_str = json.dumps(json.loads(value), indent=2, ensure_ascii=False)
            except (ValueError, TypeError):
                json_str = value  # invalid JSON — show as-is so the editor can flag it
        else:
            json_str = json.dumps(value, indent=2, ensure_ascii=False)

        # Derive element IDs
        final_attrs = self.build_attrs(self.attrs, attrs or {})
        textarea_id = str(final_attrs.get("id", f"id_{name}"))
        editor_div_id = f"ace__{textarea_id}"

        # Build the HTML elements (format_html escapes user-supplied values)
        textarea_html = format_html(
            '<textarea name="{}" id="{}" style="display:none">{}</textarea>',
            name,
            textarea_id,
            json_str,
        )
        div_html = format_html(
            '<div id="{}" style="width:100%;height:{};border:1px solid #ccc"></div>',
            editor_div_id,
            self.height,
        )

        # Build the JS separately — all values are safe (no user input)
        script = (
            "<script>(function(){"
            f'var textarea=document.getElementById("{textarea_id}");'
            f'ace.config.set("basePath","{ACE_EDITOR_BASE_PATH}");'
            f'var editor=ace.edit("{editor_div_id}");'
            "editor.setOptions({"
            '"mode":"ace/mode/json",'
            '"theme":"ace/theme/tomorrow",'
            '"useWorker":true,'
            '"showPrintMargin":false'
            "});"
            'editor.setValue(textarea.value||"{}",-1);'
            'editor.getSession().on("change",function(){'
            'if(editor.getValue().trim()===""){'
            'textarea.value="{}";'
            "}else{"
            "textarea.value=editor.getValue();"
            "}"
            "});"
            'var form=textarea.closest("form");'
            "if(form){"
            'form.addEventListener("submit",function(event){'
            "var annotations=editor.getSession().getAnnotations();"
            'var hasErrors=annotations.some(function(a){return a.type==="error";});'
            "if(hasErrors){"
            "event.preventDefault();"
            'window.alert("Metadata contains invalid JSON. Please fix the errors before saving.");'
            "}"
            "});"
            "}"
            "})();</script>"
        )

        return mark_safe(str(textarea_html) + str(div_html) + script)


class JsonEditorFormField(forms.JSONField):
    """JSONField subclass that normalises an empty string submission to ``{}``."""

    def clean(self, value: object) -> object:
        """Convert an empty or blank string to ``{}`` before JSONField validation."""
        if isinstance(value, str) and not value.strip():
            value = "{}"
        return super().clean(value)


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
