"""The widgets and the form field of the taxomesh admin: the JSON editor and the linked select."""

import json
from typing import Any, Final

from django import forms
from django.contrib.admin.widgets import AutocompleteSelect
from django.forms.renderers import BaseRenderer
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

ACE_EDITOR_CDN_URL: Final[str] = "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js"
ACE_EDITOR_BASE_PATH: Final[str] = "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/"


class JsonEditorWidget(forms.Widget):
    """The Ace editor for a ``JSONField``: JSON highlighting, and a check of the JSON as you type.

    It renders a hidden ``<textarea>``, which the form submits, beside a ``<div>`` with the Ace
    editor. The editor highlights and indents the JSON, and its web worker marks invalid JSON as
    you type. A ``submit`` listener stops the submission while the editor holds invalid JSON.

    The page loads the Ace library from the jsDelivr CDN, so it is not a Python dependency.
    """

    class Media:
        js = (ACE_EDITOR_CDN_URL,)

    # Any: an override takes what django-stubs' Widget.__init__ takes, whose attrs are dict[str, Any].
    def __init__(self, attrs: dict[str, Any] | None = None, height: str = "300px") -> None:
        super().__init__(attrs=attrs)
        self.height = height

    # Any: an override takes what django-stubs' Widget.render takes, whose attrs are dict[str, Any].
    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        """Render the hidden textarea, the ``<div>`` of the Ace editor and the script that starts it."""
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
            'window.alert("Metadata is not valid JSON. Correct it, then save.");'
            "}"
            "});"
            "}"
            "})();</script>"
        )

        return mark_safe(str(textarea_html) + str(div_html) + script)


class JsonEditorFormField(forms.JSONField):
    """The form field of ``metadata``: an empty submission is ``{}``, and only a JSON object is accepted."""

    def clean(self, value: object) -> object:
        """Convert an empty or blank submission to ``{}``, and refuse JSON that is not an object.

        Metadata is a dict, so ``null``, a list, a number or a string is a form error here rather
        than a ``TypeError`` from the service.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            value = "{}"
        cleaned = super().clean(value)
        if not isinstance(cleaned, dict):
            raise forms.ValidationError('Metadata must be a JSON object, such as {"key": "value"}.')
        return cleaned


class TaxomeshLinkedFKWidget(AutocompleteSelect):
    """An ``AutocompleteSelect`` that adds a '↗' link to the admin page of the selected object.

    It renders the Select2 autocomplete of a foreign key, and a link to the admin change page of
    the selected object. The widget builds the change URL from the ``_meta`` of the related model,
    so it works for any model that the admin registers, and names no model in its code.

    The server renders the link: it shows the value that was stored when the page loaded, and
    changes after the form is saved. When no value is selected, or when the change URL cannot be
    built, the widget renders as the standard ``AutocompleteSelect`` does.

    Usage (per-field widget override)::

        from taxomesh.contrib.django.widgets import TaxomeshLinkedFKWidget

        class MyForm(forms.ModelForm):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fields["item"].widget = TaxomeshLinkedFKWidget(
                    field=MyModel._meta.get_field("item"),
                    admin_site=admin.site,
                )

    To use it on every taxomesh foreign key of an admin, with no code for each field, use
    ``taxomesh.contrib.django.admin.TaxomeshLinkedFKMixin``.
    """

    # Any: an override takes what django-stubs' Widget.render takes, whose attrs are dict[str, Any].
    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, Any] | None = None,
        renderer: BaseRenderer | None = None,
    ) -> SafeString:
        """Render the autocomplete select and, when a value is selected, the '↗' change link.

        Args:
            name: The ``name`` attribute of the HTML input.
            value: The value of the field, the primary key of the related object, or ``None`` or
                empty when no value is selected.
            attrs: The HTML attributes, passed to the parent widget.
            renderer: The Django form renderer, passed to the parent widget.

        Returns:
            Safe HTML: the Select2 widget and, when a value is selected and its change URL can be
            built, the link to the admin change page of the selected object.
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
                ' <a href="{}" title="View in admin" style="margin-left:4px">&#8599;</a>',
                url,
            )
            return mark_safe(output + link)
        except (NoReverseMatch, Exception):  # noqa: BLE001
            return output
