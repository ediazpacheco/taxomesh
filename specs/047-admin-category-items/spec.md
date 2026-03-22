# Feature Specification: Category Items Inline on Admin Change Page

**Feature Branch**: `047-admin-category-items`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "que en por /admin/taxomesh_contrib_django/categorymodel/{uuid}/change/ se puedan ver y editar y agregar items de esa categoría"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — View Items in a Category (Priority: P1)

An admin opens the change page for a category and immediately sees the list of items currently assigned to that category, without navigating away.

**Why this priority**: Visibility is the foundation; editors need to know what items belong to a category before making any changes. This alone delivers immediate value.

**Independent Test**: Navigate to any category change page. The page must display all items belonging to that category in a dedicated section.

**Acceptance Scenarios**:

1. **Given** a category that has 3 items assigned to it, **When** an admin opens the category change page, **Then** all 3 items appear in the "Items" section of the page with their names visible.
2. **Given** a category with no items assigned, **When** an admin opens the category change page, **Then** the "Items" section appears but is empty, with an option to add items.

---

### User Story 2 — Add an Existing Item to a Category (Priority: P2)

An admin opens a category change page and assigns an existing item to that category directly from the same page, without visiting the item's own admin page.

**Why this priority**: Adding items to a category is the primary write operation editors perform; it must be available on the category page.

**Independent Test**: Open a category change page, use the item inline to link an existing item, save, and verify the item appears in the category.

**Acceptance Scenarios**:

1. **Given** an existing item not yet in the category, **When** an admin selects it in the add row of the items inline and saves, **Then** the item appears in the category on reload.
2. **Given** the inline shows an empty add row, **When** the admin leaves the row empty and saves, **Then** no change is made and no error is shown.
3. **Given** an item already assigned to the category, **When** the admin tries to add it again, **Then** a validation error is shown and no duplicate link is created.

---

### User Story 3 — Remove an Item from a Category (Priority: P3)

An admin removes an item from a category by deleting its entry in the items inline on the category change page.

**Why this priority**: Removal completes the CRUD surface; without it, admins must navigate to each item individually to unlink it.

**Independent Test**: Open a category change page, mark an item link for deletion, save, and verify the item no longer appears in the category.

**Acceptance Scenarios**:

1. **Given** a category with item A assigned, **When** an admin checks the delete checkbox for item A and saves, **Then** item A is no longer listed in the category items inline on reload.
2. **Given** the delete operation, **When** the admin saves, **Then** the item record itself is NOT deleted — only the link between the item and the category is removed.

---

### Edge Cases

- What happens when a category has a very large number of items (e.g., 500+)? No explicit row limit is applied — Django inline defaults are used, consistent with existing inlines. If a category grows unmanageably large, a row limit is a future product decision.
- How does the system handle attempting to add an item that has been deleted concurrently? A user-friendly validation error must be shown.
- What happens if the admin removes the last category assignment for an item? The item continues to exist; it is simply unlinked from this category.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The category admin change page MUST display an "Items" inline section listing all items currently assigned to that category.
- **FR-002**: Each row in the items inline MUST show the item name (for identification) and the `sort_index` field as an editable column, consistent with all other tabular inlines in this admin.
- **FR-003**: The items inline MUST allow an admin to add an existing item to the category by selecting it from a searchable field.
- **FR-004**: The items inline MUST allow an admin to remove an item from the category using a delete checkbox, without deleting the item record itself.
- **FR-005**: The system MUST prevent duplicate item–category links; attempting to add the same item twice to the same category MUST produce a validation error.
- **FR-006**: All changes to item–category assignments via the inline MUST be routed through the taxomesh service layer, consistent with how other inlines on this page operate.

### Key Entities

- **Category**: A node in the taxonomy DAG. Has a unique identifier and name. The admin change page is the context for this feature.
- **Item**: A content object that can belong to one or more categories. Has a name and unique identifier.
- **Item–Category Link**: The association between an item and a category. This is what the inline creates and deletes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can view all items assigned to a category without leaving the category change page.
- **SC-002**: An admin can add an item to a category and confirm the change in a single save action from the category change page.
- **SC-003**: An admin can remove an item from a category and confirm the change in a single save action; the item record is preserved.
- **SC-004**: Attempting to create a duplicate item–category link results in a visible validation error; no duplicate record is stored.
- **SC-005**: All item assignment changes made via the category page are reflected consistently when viewing the item's own admin page. *(Validated by the shared service layer: the same `ItemParentLinkModel` table is queried by both the category and item admin pages. No dedicated test task required — covered by existing `ItemParentLinkInline` tests on `ItemModelAdmin`.)*

## Clarifications

### Session 2026-03-22

- Q: Should the `sort_index` field be visible and editable in the items inline? → A: Yes — show sort_index as an editable column, consistent with all other tabular inlines in this admin.
- Q: Should the inline apply a hard row limit for categories with many items? → A: No explicit limit — use Django inline defaults, consistent with existing inlines.

## Assumptions

- Only authenticated admin users with change permission on CategoryModel interact with this feature; no additional permission model is introduced.
- The inline uses the existing item–category join table — no new data structure is introduced.
- Item selection in the inline uses the existing autocomplete/searchable widget already configured for item FK fields in this admin, consistent with the rest of the admin.
- No explicit row limit is set on the inline; Django inline defaults apply, consistent with all other inlines in this admin.
- "Edit" scope is limited to managing the item–category link (add / remove); editing item fields (name, metadata, etc.) from the category page is out of scope.
