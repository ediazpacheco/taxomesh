# Feature Specification: Metadata JSON Editor in Django Admin

**Feature Branch**: `031-metadata-json-editor`
**Created**: 2026-03-14
**Status**: Draft
**Input**: User description: "For the metadata field on the ItemModel and CategoryModel Django admin change pages, replace the plain text input with a JSON editor widget."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit Metadata as Structured JSON (Priority: P1)

A taxonomy admin opens an Item or Category change page and sees the `metadata` field rendered as an interactive JSON editor rather than a plain unformatted textarea. The editor shows the JSON content with syntax highlighting (keys, strings, numbers, booleans), making it easy to read and edit even for complex nested structures.

**Why this priority**: The plain textarea is the core pain point. Replacing it with a highlighted, auto-indented editor immediately improves usability for all metadata editing tasks and delivers standalone value without requiring any additional functionality.

**Independent Test**: Open an existing Category or Item change page that has metadata. Confirm the field is no longer a bare textarea but instead shows formatted, syntax-highlighted JSON.

**Acceptance Scenarios**:

1. **Given** an Item has `metadata = {"genre": "rock", "year": 2020}`, **When** the admin opens its change page, **Then** the metadata field displays the JSON formatted and syntax-highlighted, not as a raw string.
2. **Given** a Category has `metadata = {}`, **When** the admin opens its change page, **Then** the metadata field displays an empty JSON object `{}` in the editor (not a blank box).
3. **Given** the admin edits the metadata in the editor and clicks Save, **When** the form is submitted with valid JSON, **Then** the updated metadata is persisted correctly and the page reloads showing the new value.

---

### User Story 2 - Real-Time JSON Validation (Priority: P2)

While typing in the metadata editor, the admin receives immediate feedback when the JSON they have entered is syntactically invalid. The error is shown inline before they attempt to save, preventing a round-trip to the server with bad data.

**Why this priority**: Without validation, a typo in the metadata silently corrupts the value or causes a server-side error with no helpful message. Inline validation makes the editing experience safe and self-correcting.

**Independent Test**: Type intentionally invalid JSON (e.g., `{"key": }`) into the metadata editor and observe that an error indicator or message appears without submitting the form.

**Acceptance Scenarios**:

1. **Given** the admin is editing metadata, **When** they type syntactically invalid JSON (e.g., missing closing brace, trailing comma), **Then** the editor displays a visible error indicator while the content is invalid.
2. **Given** the metadata editor contains invalid JSON, **When** the admin attempts to submit the form, **Then** the form submission is blocked and an error message is shown directing attention to the metadata field.
3. **Given** the admin corrects the invalid JSON, **When** the content becomes valid again, **Then** the error indicator clears and the form can be submitted normally.

---

### Edge Cases

- What happens when `metadata` contains deeply nested JSON (e.g., 5 levels deep with arrays)? The editor must render and allow editing the full structure without truncating or corrupting it.
- What happens when `metadata` is a JSON array `[1, 2, 3]` instead of an object? The editor must display and preserve any valid JSON value, not only objects.
- What happens if the admin clears the editor completely and saves? Two-layer normalisation applies: (1) client-side — the `session.on("change")` listener replaces a blank textarea value with `"{}"` before the form is submitted; (2) server-side fallback — the widget's form field applies a `clean()` override that converts an empty string to `{}`, guarding against any client-side bypass.
- What happens on a page with multiple metadata fields (e.g., Category with both its own metadata and an inline Item)? Each instance of the editor must function independently.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `metadata` field on both the CategoryModel and ItemModel Django admin change pages MUST render as an interactive JSON editor widget, replacing the default plain textarea.
- **FR-002**: The editor MUST display JSON content with syntax highlighting (distinguishing keys, string values, numeric values, booleans, and null).
- **FR-003**: The editor MUST auto-indent and format the displayed JSON for readability when the page loads.
- **FR-004**: The editor MUST validate the JSON content in real time and display an error indicator when the content is not valid JSON.
- **FR-005**: The editor MUST prevent form submission when the metadata field contains syntactically invalid JSON.
- **FR-006**: When the metadata field value is an empty object (`{}`), the editor MUST display `{}` rather than a blank input.
- **FR-011**: When the admin clears the editor to a blank string, the system MUST normalise the value to `{}` at two layers: (a) client-side — the editor's change listener replaces a blank textarea value with `"{}"` before submit; (b) server-side — a `clean()` override on the form field converts an empty string to `{}` as a fallback, ensuring no empty string reaches the database regardless of client-side state.
- **FR-007**: The editor MUST preserve the complete metadata value on save, including nested objects, arrays, and all JSON-legal value types (string, number, boolean, null, array, object).
- **FR-008**: All other fields, inline sections, and save/delete actions on the Category and Item change pages MUST continue to work correctly and be unaffected by the editor widget.
- **FR-009**: The editor MUST be usable by any admin-authenticated user without additional per-user configuration.
- **FR-010**: The editor widget MUST be implemented without adding any new Python runtime dependency to taxomesh. The editor JavaScript library (e.g., CodeMirror) MUST be loaded from a public CDN at page load time. Admin environments without internet access are explicitly out of scope.

### Key Entities

- **Metadata**: A free-form JSON value (typically an object) stored on a `CategoryModel` or `ItemModel`. May be empty, shallow, or deeply nested. Contains arbitrary admin-defined key-value data with no fixed schema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can open any Category or Item change page and immediately see the metadata content presented in a readable, syntax-highlighted format — not as a raw string in a plain textarea.
- **SC-002**: 100% of invalid JSON entries in the metadata field are caught and reported before form submission, with no invalid data reaching the database.
- **SC-003**: Saving a valid metadata value results in equivalent data being retrievable on the next page load — no data loss or corruption for any valid JSON structure.
- **SC-004**: The metadata editor does not visibly degrade page load time or cause the browser to become unresponsive for metadata values up to 500 keys.
- **SC-005**: All existing Category and Item admin functionality (other fields, parent-link inlines, save/delete buttons) remains fully operational after the widget is introduced.

## Clarifications

### Session 2026-03-14

- Q: When the admin completely clears the editor and submits, where should the empty-string → `{}` normalisation happen? → A: Both layers — client-side JS guard in the `session.on("change")` listener, and a server-side `clean()` fallback on the form field.

## Assumptions

- **Scope**: Only the `metadata` field on the top-level `CategoryModelAdmin` and `ItemModelAdmin` change forms is in scope. Metadata fields on inline forms (if any) are out of scope unless explicitly requested.
- **Authentication**: No changes to admin authentication or permissions — the editor is visible to any user who already has change access to Category or Item records.
- **Data format**: `metadata` is always a valid JSON value at rest (enforced by the existing `JSONField`); the editor does not need to handle migration of corrupted data.
- **No schema enforcement**: The editor enforces only syntactic validity (well-formed JSON), not semantic validity (e.g., required keys, value types). Schema enforcement is out of scope.
- **CDN dependency**: The editor JS library is loaded from a public CDN. Admin environments without internet access are explicitly out of scope. No new Python runtime dependency is introduced.
