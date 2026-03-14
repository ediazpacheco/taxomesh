# Data Model: Metadata JSON Editor in Django Admin

**Branch**: `031-metadata-json-editor` | **Date**: 2026-03-14

---

## No Storage Changes

This feature introduces no new models, no new database columns, and no migrations.
The `metadata` field already exists as `models.JSONField(blank=True, default=dict)` on:

- `CategoryModel` (`taxomesh/contrib/django/models.py:68`)
- `ItemModel` (`taxomesh/contrib/django/models.py:97`)

The widget change affects only how the field is **rendered and edited** in the Django admin. The stored format is unchanged.

---

## Widget Data Contract

| Property | Value |
|---|---|
| Form field type | `django.db.models.JSONField` (standard Django field) |
| Widget replaces | Default `django.forms.Textarea` rendered by `JSONField` |
| Submitted value | Raw JSON string from hidden `<textarea name="{field_name}">` |
| Django processing | Standard `JSONField` clean/to_python pipeline — parses submitted string to Python object and validates JSON syntax server-side (no change to this path) |
| Default display | `{}` when field value is `None` or `{}` |

---

## New Python Class: `JsonEditorWidget`

Location: `taxomesh/contrib/django/widgets.py`

| Attribute | Value |
|---|---|
| Base class | `django.forms.Widget` |
| Constructor args | `height: str = "300px"` |
| `Media.js` | One CDN URL: `ACE_EDITOR_CDN_URL` |
| `render()` output | Hidden `<textarea>` + Ace editor `<div>` + inline `<script>` IIFE |
| `value_from_datadict()` | Inherited default (`data.get(name)`) — no override needed |

---

## New Named Constants (in `widgets.py`)

| Constant | Type | Value |
|---|---|---|
| `ACE_EDITOR_CDN_URL` | `Final[str]` | `"https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js"` |
| `ACE_EDITOR_BASE_PATH` | `Final[str]` | `"https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/"` |
