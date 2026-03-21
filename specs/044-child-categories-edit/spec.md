# Feature Specification: Admin Child Categories Editable Inline

**Feature Branch**: `044-child-categories-edit`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "en /taxomesh_contrib_django/categorymodel/f7af0ce4-8d33-41a4-b991-3eedaba2dadb/change/ por ej, que donde se muestra las child categories, se puedan editar y agregar. Igual que en las parents categories."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a Child Category from the Parent's Change Page (Priority: P1)

An admin opens the change page for a category and, in the "Child categories" section, selects an existing category to become a child, assigns a sort index, and saves the record. The newly linked child category is immediately visible in that section on reload.

**Why this priority**: This is the primary motivation for the feature — the admin should not need to navigate to the child's own change page just to set up the parent-child relationship. Symmetric editability (both parent and child sections editable) is the stated goal.

**Independent Test**: Open a category change page with no children. Use the "Child categories" inline to add one child, save, and verify the child now appears in the list and the child's own change page shows the current category as a parent.

**Acceptance Scenarios**:

1. **Given** a category change page is open, **When** the admin clicks "Add another Child category link" in the child categories section, **Then** a new row appears with a category selector and a sort index field.
2. **Given** a new child row is filled with a valid category and sort index, **When** the admin saves the form, **Then** the parent-child link is persisted and the child appears in the section on reload.
3. **Given** a valid category is selected for the new child row, **When** the admin saves without filling in sort index, **Then** the sort index defaults to 0 and the link is created successfully.

---

### User Story 2 - Edit Sort Index of an Existing Child Link (Priority: P2)

An admin opens the change page for a category that already has child categories. In the "Child categories" section, the admin changes the sort index value of one of the listed children and saves. The updated order is reflected immediately.

**Why this priority**: Sort index is the ordering mechanism for siblings. If the admin can see child links but cannot adjust their sort order from the parent page, partial editability would be confusing and inconsistent with the parent categories section.

**Independent Test**: Open a category change page with at least one child. Edit the sort index of that child row, save, and verify the new sort index is persisted.

**Acceptance Scenarios**:

1. **Given** a category has existing child links, **When** the admin opens its change page, **Then** each child link row shows its current sort index in an editable field.
2. **Given** the admin modifies the sort index of a child link and saves, **Then** the updated sort index is stored and the row reflects the new value on reload.

---

### User Story 3 - Remove a Child Category Link from the Parent's Change Page (Priority: P2)

An admin opens the change page for a category and marks one of its child links for deletion. After saving, that link no longer exists and the child category is no longer a descendant of this parent.

**Why this priority**: Full symmetry with the parent categories section requires the ability to remove links, not just add them.

**Independent Test**: Open a category change page with at least one child. Check the delete checkbox for one child link row, save, and verify the link is gone and the child's change page no longer lists this category as a parent.

**Acceptance Scenarios**:

1. **Given** an existing child link is displayed, **When** the admin checks the "Delete" checkbox and saves, **Then** the link is removed and the child no longer appears in the section.
2. **Given** removing a child link would leave the child with no parents, **When** the admin saves, **Then** the link is still removed (orphan categories are allowed — the child simply becomes a root node).

---

### Edge Cases

- What happens when the admin tries to add a child link where the selected category is already a child of the current category? The form must reject the duplicate with a validation error.
- What happens when the admin tries to add a child link where the selected category is an ancestor of the current category (which would create a DAG cycle)? The form must reject it with a clear error.
- What happens when the admin adds many child links in one save (batch add)? All valid links are created; any invalid ones produce per-row errors without discarding the valid entries.
- A category with no children shows an empty child section with an "Add" control, consistent with the parent categories section behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The "Child categories" section on the category change page MUST be editable, allowing admins to add, modify, and delete child category links directly from the parent's change page.
- **FR-002**: Admins MUST be able to add a new child link by selecting any existing category from a searchable selector, matching the behavior available in the parent categories section.
- **FR-003**: Each child link row MUST expose an editable sort index field, consistent with how sort index is managed in the parent categories section.
- **FR-004**: Admins MUST be able to mark any existing child link for deletion, which removes the link when the form is saved.
- **FR-005**: The system MUST reject attempts to create a duplicate child link (same parent + same child combination) with a user-facing validation error.
- **FR-006**: The system MUST reject attempts to create a child link that would introduce a cycle in the category DAG, with a user-facing validation error.
- **FR-007**: Saving the form MUST persist all valid child link changes atomically — if any link in the batch is invalid, none of the child link changes are committed, and the form returns to the edit state with per-row error messages.
- **FR-008**: The category selector in child link rows MUST support autocomplete / search, matching the selector already used in the parent categories section.

### Key Entities

- **Category**: A taxonomy node in the DAG. Can have zero or more parents and zero or more children.
- **CategoryParentLink**: The join record linking a child category to one of its parent categories (fields: child category, parent category, sort index). Adding a child from the parent's page creates a new record where `parent = current category`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can establish a new parent-child relationship entirely from the parent category's change page, without navigating to the child's change page.
- **SC-002**: An admin can remove an existing child link from the parent's change page in a single save action.
- **SC-003**: All validation errors (duplicate link, DAG cycle) surface as form errors without data loss — the admin can correct and resubmit without re-entering unchanged fields.
- **SC-004**: After saving, the child categories section on the parent change page and the parent categories section on the child change page both reflect the same updated relationship state.
- **SC-005**: No existing functionality on the category change page (name, slug, description, metadata, parent categories inline, read-only child display) is broken or visually disrupted.

## Assumptions

- Only direct child links (depth = 1) are managed. Adding grandchildren from this view is out of scope.
- The child link inline uses the same `CategoryParentLinkModel` join table already used by the parent categories inline, accessed via the reverse relation.
- The category selector widget used in child link rows is the same autocomplete widget already in use for parent link rows (no new widget required).
- No new URL, API endpoint, or migration is required — this is a pure admin change page enhancement using the existing data model.
- DAG cycle detection uses the existing service-layer validation already tested in prior specs; this feature reuses it, not reimplements it.
