# Quickstart: Metadata JSON Editor in Django Admin

**Branch**: `031-metadata-json-editor` | **Date**: 2026-03-14

---

## What Changes

After this feature, the `metadata` field on the **Category** and **Item** Django admin change pages renders as an Ace Editor widget instead of a plain `<textarea>`.

**Before**: `http://localhost:8000/admin/taxomesh_contrib_django/categorymodel/<uuid>/change/`
— metadata shows as a raw multi-line text box.

**After**: The metadata field shows a syntax-highlighted, auto-indented JSON editor with real-time validation.

---

## Requirements

- Internet access in the browser — Ace Editor is loaded from jsDelivr CDN.
- Django admin session (no new permissions required).
- No new Python packages to install.

---

## Files Changed

| File | Change |
|---|---|
| `taxomesh/contrib/django/widgets.py` | Add `JsonEditorWidget` class + `ACE_EDITOR_CDN_URL` / `ACE_EDITOR_BASE_PATH` constants |
| `taxomesh/contrib/django/admin.py` | Add `formfield_overrides` to `CategoryModelAdmin` and `ItemModelAdmin` |
| `tests/contrib/django/test_admin.py` | Add `TestJsonEditorWidget` test class |

---

## Manual Verification Steps

1. Start the Django dev server.
2. Open `http://localhost:8000/admin/taxomesh_contrib_django/categorymodel/` and click any category (or create one).
3. Confirm the **Metadata** field shows an Ace editor (syntax highlighting visible, not a plain textarea).
4. Edit the JSON to something invalid (e.g., delete a closing brace).
5. Confirm a red error annotation appears in the editor gutter.
6. Click **Save** — confirm the form does not submit and an alert message appears.
7. Fix the JSON and save — confirm the change persists and the page reloads correctly.
8. Repeat steps 2–7 for `http://localhost:8000/admin/taxomesh_contrib_django/itemmodel/`.
