# Feature Specification: Admin Metadata Fields

**Feature Branch**: `019-admin-metadata-fields`
**Created**: 2026-03-01
**Status**: Implemented
**Input**: User description: "In the Django admin, add metadata fields to Category and Item detail views"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View and Edit Category Metadata (Priority: P1)

An administrator opens the detail page of a Category record in the Django admin and can see and edit the `metadata` field alongside the other Category fields.

**Why this priority**: Metadata is already stored on Category records but is invisible and inaccessible in the admin. This is the primary gap being closed.

**Independent Test**: Open a Category detail page in the admin → confirm the `metadata` field is present, shows existing data, and saves changes correctly.

**Acceptance Scenarios**:

1. **Given** a Category record exists with non-empty `metadata`, **When** an administrator opens the Category detail page, **Then** the `metadata` field is visible and displays the stored data.
2. **Given** a Category detail page is open, **When** the administrator edits the `metadata` field and saves, **Then** the updated value is persisted and visible on the next page load.
3. **Given** a Category detail page is open with empty metadata, **When** the administrator views the page, **Then** the `metadata` field is displayed (showing an empty state) without errors.

---

### User Story 2 - View and Edit Item Metadata (Priority: P2)

An administrator opens the detail page of an Item record in the Django admin and can see and edit the `metadata` field alongside the other Item fields.

**Why this priority**: Same capability as Category but for Item — equally important once Category is done.

**Independent Test**: Open an Item detail page in the admin → confirm the `metadata` field is present, shows existing data, and saves changes correctly.

**Acceptance Scenarios**:

1. **Given** an Item record exists with non-empty `metadata`, **When** an administrator opens the Item detail page, **Then** the `metadata` field is visible and displays the stored data.
2. **Given** an Item detail page is open, **When** the administrator edits the `metadata` field and saves, **Then** the updated value is persisted and visible on the next page load.
3. **Given** an Item detail page is open with empty metadata, **When** the administrator views the page, **Then** the `metadata` field is displayed (showing an empty state) without errors.

---

### Edge Cases

- What happens when `metadata` contains deeply nested JSON? The field must display and save it without data loss.
- What happens when a user submits invalid JSON for `metadata`? The admin must reject the save and show a validation error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `metadata` field MUST appear in the Category detail view of the Django admin.
- **FR-002**: The `metadata` field MUST appear in the Item detail view of the Django admin.
- **FR-003**: Administrators MUST be able to view the current `metadata` value from the detail page.
- **FR-004**: Administrators MUST be able to edit and save the `metadata` value from the detail page.
- **FR-005**: The admin MUST reject invalid JSON input for `metadata` and display an appropriate validation error without saving.
- **FR-006**: The `metadata` field MUST appear at the end of the existing field list for both Category and Item.

### Key Entities

- **CategoryModel**: Django ORM model for Category. Has a `metadata` JSONField (blank=True, default=dict). Its admin currently exposes: `name`, `slug`, `description`, `enabled`, `external_id`.
- **ItemModel**: Django ORM model for Item. Has a `metadata` JSONField (blank=True, default=dict). Its admin currently exposes: `name`, `external_id`, `slug`, `enabled`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `metadata` field appears in 100% of Category and Item detail pages opened in the admin.
- **SC-002**: Saving valid `metadata` values through the admin results in zero data loss — the exact value entered is the value retrieved on the next page load.
- **SC-003**: Submitting invalid JSON for `metadata` produces a visible validation error and prevents the save in 100% of cases.
- **SC-004**: No existing Category or Item admin functionality is broken by this change — all pre-existing fields continue to display and save correctly.

## Assumptions

- The `metadata` JSONField on both models already exists in the database schema (confirmed: migration `0001_initial.py` defines it on both `CategoryModel` and `ItemModel`).
- Django's built-in JSON widget is sufficient for editing metadata — no custom widget is required.
- The feature does not require read-only display; full edit capability is expected.
- No additional access control beyond the existing admin permissions is required.
