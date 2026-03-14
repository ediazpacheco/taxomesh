# Feature Specification: Graph Drag-and-Drop Reordering

**Feature Branch**: `030-graph-drag-drop`
**Created**: 2026-03-13
**Status**: Draft
**Input**: User description: "at http://localhost:8000/admin/taxomesh_contrib_django/categorymodel/graph/ implement drag&drop of items and categories. Also allow reorder (using backend sort_index attribute of Category and Item."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reorder Items Within a Category (Priority: P1)

A taxonomy admin opens the graph view and sees items listed under their parent category. They want to change the display order of items within a category. They drag an item up or down within the same category and upon dropping it the new order is saved immediately. The graph re-renders reflecting the new sort order.

**Why this priority**: Reordering items within a category is the most common editorial task and has no structural risk (no DAG cycle concerns). Delivers immediate value with minimal complexity.

**Independent Test**: Can be fully tested by dragging an item above or below another item in the same category and verifying the sort-order values on the item-category link are updated in the database, and the graph re-renders in the new order.

**Acceptance Scenarios**:

1. **Given** a category has two or more items, **When** the admin drags an item to a new position within the same category, **Then** the new order is persisted and the graph reflects it after the drop.
2. **Given** a drag operation is in progress, **When** the admin drops the item back to its original position, **Then** no change is saved and no network request is made.
3. **Given** a category has only one item, **When** the admin views the graph, **Then** no drag affordance is shown for that single item (it cannot be reordered).

---

### User Story 2 - Reorder Categories Among Siblings (Priority: P2)

A taxonomy admin wants to change the display order of categories that share the same parent. They drag a category node up or down among its siblings and release; the updated order is saved and the graph reflects the new sequence.

**Why this priority**: Sibling-category reorder is the structural equivalent of item reorder: same parent scope, same sort-order semantics, but applies to categories.

**Independent Test**: Can be fully tested by dragging a category node above or below a sibling category, then verifying the category-parent link sort values are updated in the database and the graph renders in the new order on reload.

**Acceptance Scenarios**:

1. **Given** a parent category has two or more child categories, **When** the admin drags a child category to a new sibling position, **Then** the new order is persisted and the graph reflects it.
2. **Given** root-level categories are shown, **When** the admin drags one root category among other root categories, **Then** the root ordering is persisted.
3. **Given** a reorder completes successfully, **When** the admin refreshes the page, **Then** the new order is maintained.

---

### User Story 3 - Move an Item to a Different Category (Priority: P3)

A taxonomy admin decides that an item belongs under a different category. They drag the item from its current category and drop it onto a different category node. The old category assignment is removed, the new one is created, and the graph immediately reflects the item's new location.

**Why this priority**: Reparenting items adds significant editorial power but is non-trivial for the backend (create new link, remove old link). Items are leaf nodes so there is no cycle risk.

**Independent Test**: Can be fully tested by dragging an item from category A and dropping it onto category B, then verifying the item appears under B and no longer under A in the graph, and that the database reflects the new category assignment.

**Acceptance Scenarios**:

1. **Given** an item is assigned to category A, **When** the admin drags the item and drops it onto category B, **Then** the item is reassigned to category B, removed from category A, and the graph reflects the change immediately.
2. **Given** an item is dropped onto its current parent category, **When** the drop completes, **Then** the JS dragover guard skips the drop and no network request is made. (The backend endpoint is idempotent if called — see Implementation Notes.)
3. **Given** a reparent save fails, **When** the error is returned, **Then** the item visually reverts to its original position under category A and an error message is shown.

---

### User Story 4 - Move a Category to a Different Parent (Priority: P4)

A taxonomy admin wants to reorganise the taxonomy structure by moving a category under a different parent category. They drag a category node and drop it onto a different parent. The backend validates that no cycle would be created (DAG constraint). On success the graph re-renders with the category in its new location. On failure (cycle detected) the move is rejected and an error is shown.

**Why this priority**: Category reparenting changes the structure of the DAG and requires cycle detection, making it the most complex operation. It is essential for deep taxonomy reorganisation.

**Independent Test**: Can be fully tested by dragging category C (child of A) and dropping it onto category B, then verifying C is now a child of B, no longer a child of A, and that a cycle-inducing move (e.g., dropping A onto C) is rejected with an error.

**Acceptance Scenarios**:

1. **Given** category C is a child of A, **When** the admin drags C and drops it onto B, **Then** C becomes a child of B, the link to A is removed, and the graph reflects the new structure.
2. **Given** category C is a child of A, **When** the admin attempts to drag A and drop it onto C (which would create a cycle), **Then** the backend rejects the operation, A stays in its original position, and an error message is displayed.
3. **Given** a category is dropped onto its current parent, **When** the drop completes, **Then** the JS dragover guard skips the drop and no network request is made. (The backend endpoint is idempotent if called — see Implementation Notes.)
4. **Given** the ROOT category, **When** any drag-and-drop operation targets ROOT as the new parent, **Then** the operation is accepted (categories can be promoted to root-level children).

---

### Edge Cases

- What happens when the user drags a node while an earlier save is still in flight? The UI must indicate a pending state and prevent further drag operations until the in-flight save resolves.
- What happens if the backend rejects any operation (reorder, reparent, cycle detected)? The graph must visually revert the node to its pre-drag position and display a user-visible error message.
- What happens with collapsed subtrees during a drag? Collapsed (hidden) descendants must not be valid drop targets; only visible nodes are interactive during a drag session.
- What happens when a category appears multiple times in the graph (multi-parent DAG)? Each appearance is independently draggable within its own parent context; reparenting one appearance moves the category away from that specific parent only.
- What happens with the ROOT category node? It must never be draggable. It may be a valid drop target (to promote a category to root level) but is never itself movable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The graph view MUST display a visual drag handle on every item and category node that is eligible for interaction.
- **FR-002**: Items MUST be draggable to new positions within their current parent category, changing their relative sort order within that category.
- **FR-003**: Categories MUST be draggable to new positions among their siblings (sharing the same parent), changing their relative sort order within that parent.
- **FR-004**: Items MUST be draggable onto a different category node to reassign the item to that category (reparenting); the old category assignment is removed and the new one is created. The item MUST be inserted at the visual drop position among the new category's existing items, not appended unconditionally at top or bottom.
- **FR-005**: Categories MUST be draggable onto a different parent category node to reassign the category to that parent (reparenting); the old parent link is removed and the new one is created. The node MUST be inserted at the visual drop position among the new parent's existing siblings, not appended unconditionally at top or bottom.
- **FR-006**: Before persisting a category reparent, the system MUST validate that the operation does not introduce a cycle in the DAG; if a cycle would result, the operation MUST be rejected with an error.
- **FR-007**: When any drag-and-drop operation is confirmed, the system MUST persist the change to the backend without a full page reload.
- **FR-008**: The graph view MUST reflect the updated structure immediately after a successful save, without requiring a manual page refresh.
- **FR-009**: If the backend save fails for any reason (including cycle detection), the graph MUST revert the node to its pre-drag position and display a user-visible error message.
- **FR-010**: All existing expand/collapse toggling behaviour MUST continue to function correctly after any drag-and-drop operation.
- **FR-011**: The graph MUST render items and categories in ascending sort order (by the sort-order value stored on the link record) within each parent scope.
- **FR-012**: The ROOT category node MUST NOT be draggable. It MAY be a valid drop target for promoting a category to root level.
- **FR-013**: The system MUST expose admin-only HTTP endpoints for (a) reordering siblings and (b) reparenting a node, each persisting changes atomically.
- **FR-014**: Only admin-authenticated users may invoke the reorder and reparent endpoints; unauthenticated requests MUST be rejected.

### Key Entities

- **Category–Parent Link**: Represents the parent-child relationship between two categories; carries a sort-order value that determines the display position of a child category among its siblings within a given parent.
- **Item–Category Link**: Represents the assignment of an item to a parent category; carries a sort-order value that determines the display position of the item within that category.
- **Graph Entry**: A flattened display record used to render each row in the graph view; carries node kind ("category" or "item"), a unique identifier, depth, and ordering metadata.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can reorder any item or sibling-category and have the change persisted in under 10 seconds from drag-start to confirmed save.
- **SC-002**: An admin can reparent any item or category and have the change persisted in under 10 seconds from drag-start to confirmed save.
- **SC-003**: 100% of operations that complete without a network error result in a persistent change visible after a full page reload.
- **SC-004**: 100% of operations that fail (backend error or cycle detected) result in the graph reverting to its prior visual state within 2 seconds and an error message displayed.
- **SC-005**: 100% of category reparent operations that would create a DAG cycle are rejected before any data is written.
- **SC-006**: The graph view's initial load time is not measurably degraded compared to before this feature.
- **SC-007**: All expand/collapse interactions remain fully functional after one or more drag-and-drop operations within the same page session.

## Assumptions

- **Sort index strategy**: When a reorder is saved, sort-order values are reassigned as a dense integer sequence starting from zero based on the final visual order; gaps are not preserved.
- **Reparent insertion position**: When a node is reparented into a new parent, it is inserted at the visual drop position within that parent's existing siblings. The drop gesture must convey both the target parent and the insertion slot among visible siblings. Sort-order values for all siblings in the new parent are reassigned as a dense sequence to accommodate the inserted node.
- **Single-parent reparenting**: Each drag-and-drop reparent operation moves a node from exactly one specific parent to one new parent. Multi-parent assignment (a node having more than one parent simultaneously) is not modifiable via drag-and-drop in this feature.
- **Authentication**: Reorder and reparent endpoints rely on Django admin session authentication; no additional permission model is introduced.
- **Conflict handling**: Concurrent operations by multiple admin users are not specially handled; last-write wins.
- **Root categories**: The graph shows all non-ROOT top-level categories as visible roots. Reordering among these updates the sort order on their link to the hidden ROOT node. Dropping a category onto ROOT promotes it to a direct child of ROOT.

## Clarifications

### Session 2026-03-13

- Q: When a node (item or category) is reparented into a new parent, where does it appear in that parent's sort order? → A: At the visual drop position — inserted at the slot among the new parent's visible siblings where the user released the drag. The reparent endpoint receives the target insertion index (or the UUID of the sibling it should precede) so sort-order values for the new parent's children can be reassigned atomically.

---

## Implementation Notes

These notes document decisions made during implementation that are not covered by the functional requirements above. They are recorded here for spec completeness (Constitution Principle VII).

### AJAX Expand-on-Demand (FR-010 implementation detail)

To keep the initial graph page load fast and to support correct DnD DOM updates after reparenting, the expand/collapse toggle for collapsed categories uses AJAX lazy loading rather than a purely JS show/hide of pre-rendered HTML.

**Endpoint**: `GET graph/children/?parent_uuid=<uuid>&depth=<int>` (URL name: `taxomesh_contrib_django_graph_children`)
**Returns**: An HTML fragment rendered by the `_graph_entry_list.html` partial template, containing the direct children (categories + items) of the given category at the specified depth.
**Authentication**: Wrapped in `self.admin_site.admin_view()` — same admin-session guard as all other graph endpoints.
**Scope**: Internal to the graph view; not part of the public taxomesh API.

The partial template `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/_graph_entry_list.html` is used for both the initial server-side render and the AJAX fragment responses.

### Same-Parent Reparent Behaviour (US3 AC2 / US4 AC3 clarification)

The JS `dragover` handler prevents drops onto the current parent (the entry element is skipped when its UUID matches `dragged.dataset.parentUuid`), so no network request is made in the normal UI flow. The backend `reparent_view` endpoint does not enforce this as an error — if called with `old_parent_uuid == new_parent_uuid` it completes successfully (idempotent). This is intentional: the enforcement is a UX concern (JS layer), not a data-integrity concern (backend layer).
