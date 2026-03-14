# Tasks: Metadata JSON Editor in Django Admin

**Input**: Design documents from `/specs/031-metadata-json-editor/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: TDD is mandatory per CLAUDE.md. Every implementation task has a preceding failing-test task.

**Organization**: Tasks are grouped by user story. US1 (editor widget) must complete before US2 (validation guard) since both live in the same `render()` method.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no incomplete dependencies)
- **[Story]**: Which user story this task belongs to (US1–US2 from spec.md)
- Exact file paths are included in every description

---

## Phase 1: Setup (No new setup required)

This feature adds no new packages, no new files, no migrations, and no project structure changes. All changes are additive on existing files.

---

## Phase 2: Foundational (No blocking prerequisites)

No shared infrastructure changes are required. Both user stories depend only on the `JsonEditorWidget` class introduced in Phase 3.

---

## Phase 3: User Story 1 — Syntax-Highlighted JSON Editor (Priority: P1) 🎯 MVP

**Goal**: Replace the plain textarea for `metadata` on Category and Item change pages with an Ace Editor widget that provides syntax highlighting and auto-indenting.

**Independent Test**: Open `/admin/taxomesh_contrib_django/categorymodel/<uuid>/change/` and `/admin/taxomesh_contrib_django/itemmodel/<uuid>/change/` — the metadata field must render an Ace editor div and the response HTML must contain `ace.edit`.

### Tests (write first — must FAIL before implementation)

- [X] T001 [US1] Write failing tests for `JsonEditorWidget` in `tests/contrib/django/test_admin.py` — add class `TestJsonEditorWidget` with: `test_render_contains_hidden_textarea` (output has `<textarea name="metadata"` with `style="display:none"`), `test_render_contains_ace_div` (output has `<div id="ace__id_metadata"`), `test_render_contains_init_script` (output has `ace.edit(` and `ace.config.set`), `test_render_none_value_defaults_to_empty_object` (None → `{}`), `test_render_dict_value_is_json_serialised` (dict value serialised to JSON string), `test_render_unique_ids_for_different_attrs` (two render() calls with different `id` attrs produce different editor div IDs), `test_media_declares_ace_cdn_url` (`ACE_EDITOR_CDN_URL` in `JsonEditorWidget().media._js`), `test_value_from_datadict_reads_textarea_name` (returns value from `data[name]`)

### Implementation

- [X] T002 [US1] Implement `JsonEditorWidget` in `taxomesh/contrib/django/widgets.py` (depends on T001): add `ACE_EDITOR_CDN_URL: Final[str]` and `ACE_EDITOR_BASE_PATH: Final[str]` constants; add `class JsonEditorWidget(forms.Widget)` with `class Media` declaring `ACE_EDITOR_CDN_URL`, `__init__(self, attrs=None, height="300px")`, and `render()` producing hidden `<textarea>` + Ace div + IIFE `<script>` that calls `ace.config.set("basePath", ACE_EDITOR_BASE_PATH)`, `ace.edit(editor_div_id)` with `mode: "ace/mode/json"`, `theme: "ace/theme/tomorrow"`, `showPrintMargin: False`, and a `session.on("change")` listener that syncs `textarea.value = editor.getValue()`; derive `editor_div_id = f"ace__{textarea_id}"` from `attrs["id"]` (fallback `f"id_{name}"`); normalise value: `None → "{}"`, non-str → `json.dumps(..., indent=2, ensure_ascii=False)`, str → as-is

- [X] T003 [P] [US1] Add `formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget}}` to `CategoryModelAdmin` and `ItemModelAdmin` in `taxomesh/contrib/django/admin.py` (depends on T002); import `JsonEditorWidget` from `taxomesh.contrib.django.widgets` (add to existing import or use lazy import inside the class if circular import risk); `models.JSONField` is already available via `from django.db import models`

- [X] T004 [P] [US1] Write failing integration tests in `tests/contrib/django/test_admin.py` (depends on T002, run after T003): `test_category_change_page_renders_ace_editor` (GET category change page via `admin_client`, assert `b"ace.edit"` and `b"ace/mode/json"` in `response.content`), `test_item_change_page_renders_ace_editor` (same for item), `test_category_metadata_textarea_is_hidden` (assert `b'display:none'` in `response.content` for the metadata field)

**Checkpoint**: Category and Item change pages render an Ace editor for the metadata field. Syntax highlighting and auto-indent are active.

---

## Phase 4: User Story 2 — Real-Time Validation + Submit Guard (Priority: P2)

**Goal**: The Ace editor uses its built-in JSON web worker to annotate syntax errors inline. A JavaScript submit listener prevents form submission when the metadata field contains invalid JSON.

**Independent Test**: Verify that `render()` output includes `getAnnotations` and `preventDefault`. (Full browser-level validation is not auto-testable; the test confirms the guard code is present in the rendered HTML.)

**Depends on**: Phase 3 complete (T001–T004 passing).

### Tests (write first — must FAIL before implementation)

- [X] T005 [US2] Write failing tests in `tests/contrib/django/test_admin.py`: `test_render_uses_worker` (render() output contains `useWorker`), `test_render_contains_submit_guard` (render() output contains `getAnnotations` and `preventDefault`), `test_render_blank_guard_client_side` (render() output contains JS that sets textarea to `"{}"` when value is blank), `test_clean_empty_string_returns_empty_dict` (instantiate `JsonEditorWidget`, call its associated form field's `clean("")` and assert result is `{}`)

### Implementation

- [X] T006 [US2] Extend `JsonEditorWidget.render()` in `taxomesh/contrib/django/widgets.py` (depends on T005): add `useWorker: true` to `setOptions()`; in the `session.on("change")` listener, add a blank-guard: `if (editor.getValue().trim() === "") { textarea.value = "{}"; } else { textarea.value = editor.getValue(); }`; add a form `submit` event listener inside the IIFE that: (a) reads `editor.getSession().getAnnotations()`, (b) if any have `type === "error"`, calls `event.preventDefault()` and `window.alert("Metadata contains invalid JSON. Please fix the errors before saving.")`, (c) otherwise allows the submit to proceed

- [X] T007 [US2] Add server-side `clean()` fallback in `taxomesh/contrib/django/widgets.py` (depends on T006): add a `JsonEditorFormField(forms.JSONField)` subclass that overrides `clean(value)` to call `super().clean("{}" if not value or not value.strip() else value)`, ensuring an empty string submitted to the server is normalised to `{}` before `JSONField` validation runs; update `JsonEditorWidget` or `formfield_overrides` wiring in `admin.py` so the form field class used is `JsonEditorFormField` (use `formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget, "form_class": JsonEditorFormField}}` or override `formfield_for_dbfield`)

**Checkpoint**: Typing invalid JSON in the metadata editor shows a red gutter annotation. Clicking Save while JSON is invalid shows an alert and blocks submission.

---

## Phase 5: Polish & Quality Gates

- [X] T008 Run quality gates and fix any failures: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy --strict .`, `uv run pytest --cov=taxomesh --cov-fail-under=80`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 3 (US1) → Phase 4 (US2) → Phase 5 (Polish)
```

US1 blocks US2 because the submit guard extends the same `render()` method created in US1.

### Within-Phase Dependencies

| Phase | Sequential chain |
|-------|-----------------|
| 3 | T001 → T002 → T003 ‖ T004 |
| 4 | T005 → T006 |
| 5 | T007 |

(`‖` = can run in parallel; `→` = must be sequential)

### Parallel Opportunities

**Phase 3:**
- T003 (admin.py wiring) and T004 (integration tests) can run in parallel after T002, since they touch different files

**Phase 4:**
- T005 and T006 are sequential (TDD order)

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 3: T001 → T002 → T003 ‖ T004
2. **STOP and VALIDATE**: Open a Category and Item change page in the browser — confirm Ace editor appears with syntax highlighting
3. Proceed to US2 once US1 is confirmed working

### Incremental Delivery

| Stage | Delivers | Gate |
|-------|---------|------|
| Phase 3 (US1) | Syntax-highlighted, auto-indented JSON editor on Category + Item change pages | pytest T001, T003, T004 passing + manual browser check |
| Phase 4 (US2) | Real-time validation annotations + submit guard prevents bad saves | pytest T005, T006 passing + manual: type bad JSON, click Save → alert shown |
| Phase 5 | Quality gates green | ruff + mypy + pytest ≥ 80% |

---

## Notes

- **TDD is mandatory** (CLAUDE.md): test task must be written and confirmed FAILING before its implementation task begins
- T003 and T004 touch different files (admin.py vs test_admin.py) — safe to work in parallel after T002
- `JsonEditorWidget` lives in the existing `widgets.py` — no new files created
- `formfield_overrides` applies to all `JSONField` columns on the targeted `ModelAdmin` classes; per spec Assumptions, only `metadata` fields are in scope — both models have exactly one `metadata` field so this is safe
- CSRF and admin authentication are unaffected — this is a pure frontend widget change
- The Ace web worker (`worker-json.js`) is fetched automatically from `ACE_EDITOR_BASE_PATH` at runtime; no additional CDN URLs need to be declared in `class Media`
