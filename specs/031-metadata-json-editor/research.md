# Research: Metadata JSON Editor in Django Admin

**Branch**: `031-metadata-json-editor` | **Date**: 2026-03-14

---

## Decision 1: CDN JavaScript Editor Library

**Decision**: Ace Editor via jsDelivr `src-min-noconflict` build, pinned to `v1.43.3`.

**CDN URL declared in `class Media`**:
```
https://cdn.jsdelivr.net/npm/ace-builds@1.43.3/src-min-noconflict/ace.js
```

Ace auto-fetches `mode-json.js`, `worker-json.js`, and the theme file at runtime from the same CDN path via `ace.config.set("basePath", ...)`. No additional entries are needed in `class Media`.

**Rationale**:
- UMD/IIFE global build (`window.ace`) — exactly what Django's `class Media` expects. No module system.
- One CDN file declared in `class Media`; Django's media deduplication ensures it loads once regardless of how many widget instances appear on the page (inline formsets included).
- Built-in JSON web worker validation: inline error markers and gutter annotations without any external parser library dependency.
- Actively maintained: `v1.43.6` released 2026-03-02; 27 k GitHub stars; CI green.
- The only gotcha — dynamic worker file loading from CDN — is solved with one line: `ace.config.set("basePath", "...")`.

**Alternatives considered**:

| Option | Eliminated because |
|---|---|
| CodeMirror 5 | 5–6 CDN assets required; JSON validation depends on `window.jsonlint`, an implicit external global with no cdnjs mirror; library in maintenance-only mode. |
| CodeMirror 6 | ESM-only distribution; no IIFE/UMD bundle available from any stable CDN; requires a build step — structurally incompatible with Django `class Media`. |
| `django-json-widget` PyPI package | Adds a new Python runtime dependency, violating FR-010 and the project's YAGNI principle for the contrib module. |

---

## Decision 2: Widget Integration Approach

**Decision**: `formfield_overrides = {models.JSONField: {"widget": JsonEditorWidget}}` on `CategoryModelAdmin` and `ItemModelAdmin`.

**Rationale**:
- `formfield_overrides` is the idiomatic Django admin mechanism for wholesale field-type substitution.
- No override is needed when other `JSONField`s on other models (e.g., `ItemTagLinkModel.metadata`, `ItemRelationLinkModel.metadata`) should also receive the editor in future — but per the spec, scope is limited to the top-level Category and Item admins.
- Scoping via `formfield_overrides` on individual `ModelAdmin` classes (rather than globally on `AdminSite`) keeps the change minimal and targeted.

**Alternative considered**: `formfield_for_dbfield(self, db_field, ...)` — valid, and marginally more explicit, but `formfield_overrides` is less boilerplate and is the documented pattern for this exact use case.

---

## Decision 3: Widget Class Location

**Decision**: Add `JsonEditorWidget` to the existing `taxomesh/contrib/django/widgets.py`.

**Rationale**: `widgets.py` already holds `TaxomeshLinkedFKWidget` (a custom `AutocompleteSelect` subclass). This is the correct adapter-layer file for all custom Django admin widgets in the contrib module. No new files needed.

---

## Decision 4: Named Constant for CDN URL

**Decision**: Define `ACE_EDITOR_CDN_URL: Final[str]` and `ACE_EDITOR_BASE_PATH: Final[str]` as module-level constants in `widgets.py`, per Constitution Principle X (no magic literals).

---

## Decision 5: Multiple Instances (Inline Formsets)

**Decision**: Use the Django-provided `id` attribute (`attrs["id"]`) from `render()` to derive a unique editor container ID per instance (e.g., `ace__id_metadata` for the top-level form, `ace__id_items-0-metadata` for the first inline row).

**Rationale**: Django guarantees uniqueness of the `id` attribute within a page. Wrapping each init block in an IIFE prevents variable leaks. No additional coordination mechanism is required.

---

## Decision 6: Submit Sync Strategy

**Decision**: The visible Ace editor div is cosmetic. The underlying `<textarea>` (hidden via `display:none`) is the form submission target. An Ace `session.on("change")` listener keeps the textarea in sync on every keystroke.

**Rationale**: This is the standard pattern used by all known Django JSON widget implementations (including the reference `django-json-widget`). Django's form machinery reads only named inputs from POST — the textarea fulfils this without any special `value_from_datadict` override.

---

## Decision 7: Client-Side Validation and Form Submission Guard

**Decision**: Use Ace's built-in JSON web worker for real-time inline annotations. Add a `submit` event listener on the parent `<form>` that checks `editor.getSession().getAnnotations()` for errors and calls `event.preventDefault()` if any exist, showing a `window.alert()` message.

**Rationale**: Ace's worker-json validates in a background thread, producing annotation objects with `type: "error"` for syntax violations. This is zero-implementation-cost validation — the worker is loaded automatically by setting `useWorker: true`. The submit guard is a dozen lines of vanilla JS.
