# Implementation Plan: Metadata JSON Editor in Django Admin

**Branch**: `031-metadata-json-editor` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/031-metadata-json-editor/spec.md`

## Summary

Replace the default plain `<textarea>` for the `metadata` field on `CategoryModelAdmin` and `ItemModelAdmin` Django admin change pages with an Ace Editor widget loaded from the jsDelivr CDN. The widget provides JSON syntax highlighting, auto-indenting, real-time validation via a built-in web worker, and a form-submit guard that blocks saving invalid JSON. No new Python runtime dependencies are introduced.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Django ≥ 4.2 (admin widget system), Ace Editor v1.43.3 (CDN — no Python dep)
**Storage**: N/A — no model changes, no migrations
**Testing**: pytest + pytest-django (`admin_client` fixture)
**Target Platform**: Django admin (desktop browser, staff users — CDN internet access required)
**Project Type**: Library contrib module (Django admin extension)
**Performance Goals**: Widget loads in normal admin page latency; no special targets (SC-004: no degradation up to 500 metadata keys)
**Constraints**: No new Python runtime dependencies (FR-010); mypy strict must pass; JS editor from public CDN only
**Scale/Scope**: Admin-only; metadata values bounded by typical taxonomy admin use (< 500 keys per FR-010 assumption)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I — Hexagonal architecture | Widget lives in `contrib/django/widgets.py` (adapter layer). No domain or application layer imports. | ✅ |
| II — TaxomeshService is single facade | No service layer involvement — pure admin UI change. | ✅ |
| III — Repository as Protocol | No repository involvement. | ✅ |
| IV — Pydantic + mypy strict | `JsonEditorWidget` must be fully typed; `render()` returns `str` (via `format_html` which returns `SafeString`). | ✅ |
| V — Exception hierarchy | Not applicable — no domain errors involved. | ✅ |
| VI — DAG cycle detection | Not applicable. | ✅ |
| VII — Spec-driven development | Spec exists at `specs/031-metadata-json-editor/spec.md`. | ✅ |
| VIII — Quality gates | ruff + mypy strict + pytest ≥ 80% coverage required before merge. | ✅ |
| IX — Framework-agnostic API handlers | Not applicable — this is a Django-admin-internal widget, not part of `taxomesh.contrib.api`. | ✅ |
| X — Named constants | `ACE_EDITOR_CDN_URL` and `ACE_EDITOR_BASE_PATH` defined as `Final[str]` in `widgets.py`. No magic CDN strings inline. | ✅ |
| XI — OO by default | `JsonEditorWidget` is a class extending `forms.Widget`. | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/031-metadata-json-editor/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── widget-interface.md  ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (files touched)

```text
taxomesh/
└── contrib/
    └── django/
        ├── widgets.py     # Add JsonEditorWidget + ACE_EDITOR_CDN_URL / ACE_EDITOR_BASE_PATH
        └── admin.py       # Add formfield_overrides to CategoryModelAdmin + ItemModelAdmin

tests/
└── contrib/
    └── django/
        └── test_admin.py  # Add TestJsonEditorWidget test class
```

No new files. No new directories. No migrations. No new Python runtime dependencies.

**Structure Decision**: Single-project layout. All changes are additive on existing files in the `contrib/django` module. The widget pattern follows the existing `TaxomeshLinkedFKWidget` in `widgets.py`.

---

## Implementation Phases

### Phase A — Widget Implementation (TDD first)

**A1 — Tests for `JsonEditorWidget`** *(write and confirm FAILING before A2)*

In `tests/contrib/django/test_admin.py`, add class `TestJsonEditorWidget`:

- `test_render_contains_hidden_textarea` — call `render("metadata", {"key": "val"}, {"id": "id_metadata"})`, assert output contains `<textarea name="metadata"` with `display:none`.
- `test_render_contains_ace_div` — assert output contains `<div id="ace__id_metadata"`.
- `test_render_contains_init_script` — assert output contains `ace.edit(` and `ace.config.set`.
- `test_render_none_value_defaults_to_empty_object` — call with `value=None`, assert textarea value is `{}`.
- `test_render_dict_value_is_json_serialised` — call with `value={"a": 1}`, assert textarea contains `"a"`.
- `test_render_unique_ids_for_different_attrs` — call twice with different `id` attrs, assert the two editor div IDs differ.
- `test_media_declares_ace_cdn_url` — assert `ACE_EDITOR_CDN_URL` in `JsonEditorWidget().media._js`.
- `test_value_from_datadict_reads_textarea_name` — call `value_from_datadict({"metadata": '{"x":1}'}, {}, "metadata")`, assert returns `'{"x":1}'`.

**A2 — Implement `JsonEditorWidget` in `widgets.py`** *(after A1 tests are FAILING)*

Add at the top of `widgets.py`:

```python
ACE_EDITOR_CDN_URL: Final[str] = (
    "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js"
)
ACE_EDITOR_BASE_PATH: Final[str] = (
    "https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/"
)
```

`JsonEditorWidget(forms.Widget)`:

- `class Media`: `js = (ACE_EDITOR_CDN_URL,)`
- `__init__(self, attrs=None, height="300px")`: store `self.height`; call `super().__init__(attrs=attrs)`
- `render(self, name, value, attrs=None, renderer=None) -> str`:
  - Normalise `value`: `None` → `"{}"`, non-str → `json.dumps(..., indent=2, ensure_ascii=False)`, str → as-is
  - Derive `textarea_id` from `attrs["id"]` (fallback `f"id_{name}"`)
  - Derive `editor_div_id = f"ace__{textarea_id}"`
  - Return `format_html(...)` with: hidden textarea, Ace div, IIFE `<script>` containing:
    - `ace.config.set("basePath", ACE_EDITOR_BASE_PATH)`
    - `ace.edit(editor_div_id)` with `mode: "ace/mode/json"`, `theme: "ace/theme/tomorrow"`, `useWorker: true`, `showPrintMargin: false`
    - `editor.setValue(textarea.value || "{}", -1)`
    - `session.on("change")` listener to sync textarea
    - Form `submit` listener: check `editor.getSession().getAnnotations()` for `type === "error"`; if found call `event.preventDefault()` and `window.alert("...")`

**A3 — Integration tests for admin change pages** *(after A2 passes unit tests)*

In `tests/contrib/django/test_admin.py`, add to `TestJsonEditorWidget` (or separate class `TestJsonEditorAdminIntegration`):

- `test_category_change_page_renders_ace_editor` — GET category change page via `admin_client`, assert `b"ace.edit"` in response content and `b"ace/mode/json"` in response content.
- `test_item_change_page_renders_ace_editor` — same for item change page.
- `test_category_change_page_has_no_plain_metadata_textarea` — assert the metadata field does not render as a visible unstyled textarea (i.e., `display:none` is present on the metadata textarea).

---

### Phase B — Admin Wiring

**B1 — Add `formfield_overrides` to `CategoryModelAdmin` and `ItemModelAdmin`** *(after A1 failing tests exist)*

In `taxomesh/contrib/django/admin.py`:

1. Import `JsonEditorWidget` from `taxomesh.contrib.django.widgets` (lazy import inside the class or at module top — check for circular imports; use lazy if needed).
2. On `CategoryModelAdmin`: add `formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget}}`.
3. On `ItemModelAdmin`: add `formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget}}`.

Note: `models.JSONField` requires `from django.db import models` — already imported in `admin.py`.

---

### Phase C — Quality Gates

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

All must pass before proposing a commit.

---

## Named Constants to Add

| Constant | Type | Value | Location |
|----------|------|-------|----------|
| `ACE_EDITOR_CDN_URL` | `Final[str]` | `"https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js"` | `widgets.py` |
| `ACE_EDITOR_BASE_PATH` | `Final[str]` | `"https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/"` | `widgets.py` |

---

## Complexity Tracking

No constitution violations.
