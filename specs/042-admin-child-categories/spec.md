# Feature Specification: Admin Child Categories Display

**Feature Branch**: `042-admin-child-categories`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "en /taxomesh_contrib_django/categorymodel/d46f74b8-895c-48d3-9875-6bb593d7ef4e/change/ por ej, mostrar también las categories child (como ahora ya se muestran las categories parents)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Child Categories on Category Change Page (Priority: P1)

An admin user opens the Django admin change view for any category and can see, in addition to the existing "Parent categories" section, a new read-only section listing all direct child categories (i.e., categories that list this category as one of their parents).

**Why this priority**: This is the entire feature — surfacing child relationship data that is currently absent from the change page. Without it, admins must navigate away from the current category to discover its children.

**Independent Test**: Open any category change page that has at least one child category. Verify the child category section is visible and lists the correct children.

**Acceptance Scenarios**:

1. **Given** a category with one or more child categories, **When** an admin opens its change page, **Then** a "Child categories" section is displayed listing all direct children by name.
2. **Given** a category with no child categories, **When** an admin opens its change page, **Then** the "Child categories" section is present but shows no entries (empty inline).
3. **Given** a category that is both a parent and a child (mid-level node in the DAG), **When** an admin opens its change page, **Then** both the "Parent categories" section and the "Child categories" section show their respective relationships correctly.

---

### Edge Cases

- A root category (no parents, but with children) shows an empty "Parent categories" section and a populated "Child categories" section.
- A leaf category (has parents, no children) shows a populated "Parent categories" section and an empty "Child categories" section.
- A category with many children (e.g., 50+) displays all of them without errors.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The category change page MUST display a "Child categories" section alongside the existing "Parent categories" section.
- **FR-002**: The "Child categories" section MUST list every category that directly references the current category as one of its parents (direct children only — not all descendants).
- **FR-003**: The child categories section MUST be read-only; admins cannot add or remove children from this view (parent links are managed from the child's own change page).
- **FR-004**: Each child entry MUST display at minimum the child category's name.
- **FR-005**: The child categories section MUST remain visible even when there are zero children (empty state).

### Key Entities

- **Category**: A taxonomy node in the DAG. Can have zero or more parents and zero or more children.
- **CategoryParentLink**: The join record linking a child category to one of its parent categories. Queried in reverse (filtering by parent) to find children.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin visiting a category change page can identify all direct child categories without leaving that page.
- **SC-002**: The child categories section correctly reflects the current state of parent-link records — adding or removing a parent link from a child is immediately reflected when the parent's change page is reloaded.
- **SC-003**: The change page renders without errors for categories with zero, one, or many children.
- **SC-004**: No existing functionality on the category change page (name, slug, description, metadata, parent categories inline) is broken or visually disrupted by the addition.

## Assumptions

- Direct children only (depth = 1). Displaying all descendants recursively is out of scope.
- The child categories section is read-only; editing child relationships from the parent page is not required.
- No new URL, API endpoint, or migration is required — this is a pure Django admin change page enhancement.
