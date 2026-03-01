# Feature Specification: Admin Service Layer

**Feature Branch**: `016-admin-service-layer`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "currently the django admin interactua directamente con el ORM. Esto tiene de problema que todas las validaciones de datos, por ej de dependencia ciclica, son evitados. Refactor the admin integration to work with the TaxomeshService and not with the ORM directly. The dependency should be: django admin -> TaxomeshService -> DjangoRepository -> django ORM"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cycle Detection Enforced in Admin (Priority: P1)

A taxonomy administrator opens the Django admin, edits a category, and attempts to assign it a parent
category that would create a cyclic relationship (e.g. A → B → A). The admin form rejects the save
and displays a clear validation error explaining the cycle was detected. No data is written.

**Why this priority**: Cycle detection is the primary business rule bypassed today. A cycle in the
taxonomy DAG corrupts the data model and causes cascading failures in graph traversal. Enforcing it
through the admin is the main motivation for this feature.

**Independent Test**: Can be fully tested by submitting a form in admin that introduces a cycle and
verifying the error message is shown and the record is unchanged.

**Acceptance Scenarios**:

1. **Given** categories A and B exist with A as parent of B, **When** an admin user edits B and sets
   its parent to A (which would create a cycle), **Then** the admin form shows a validation error and
   the category-parent relationship is not changed.
2. **Given** a category with no parents, **When** an admin user adds a valid (non-cyclic) parent,
   **Then** the save succeeds and the relationship is persisted.

---

### User Story 2 — All Category Mutations Go Through Business Rules (Priority: P2)

A taxonomy administrator creates, updates, or deletes a category through the Django admin. All
business rules enforced by the service layer (field length limits, uniqueness constraints, etc.) apply
to the operation. Errors are surfaced in the admin UI with a human-readable message.

**Why this priority**: Without service-layer routing, any business rule beyond the database constraint
can be bypassed. This includes field validation, state checks, and any future rule added to the
service.

**Independent Test**: Can be fully tested by creating/updating/deleting a category and confirming the
service's validation runs (e.g. name over maximum length raises an error in the admin form, not a
raw database exception).

**Acceptance Scenarios**:

1. **Given** an admin user submits a category name that exceeds the maximum allowed length, **When**
   the form is saved, **Then** a validation error is displayed and no record is written.
2. **Given** a valid new category, **When** saved via admin, **Then** the category is persisted and
   appears in the list view.
3. **Given** an existing category, **When** deleted via admin, **Then** the service delete method is
   called and the category is removed.

---

### User Story 3 — Item and Tag Mutations Go Through Business Rules (Priority: P3)

A taxonomy administrator creates, updates, or deletes items and tags through the Django admin. All
service-layer business rules apply. Errors are surfaced as form validation messages.

**Why this priority**: Items and tags also bypass service validation today. Consistency requires
routing all entity mutations — not just categories — through the service.

**Independent Test**: Can be fully tested by performing create/update/delete on an item and a tag
and confirming the service methods are called (e.g. via test doubles verifying call signatures).

**Acceptance Scenarios**:

1. **Given** an admin user creates a new item with a valid external ID, **When** saved, **Then** the
   item is persisted via the service and appears in the item list.
2. **Given** an admin user updates a tag name, **When** saved, **Then** the service update method
   is called and the change is reflected.

---

### Edge Cases

- What happens when the service raises an unexpected error (not a validation error) during a save?
  The admin must surface an error message rather than showing an unhandled exception page.
- What happens when an admin user attempts to delete a category that still has children or items
  assigned? The service determines the outcome; the admin displays any resulting error.
- What happens when a user with read-only admin permissions views a record? Read-only access
  (list/detail views) does not require service-layer routing and must continue to work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every create, update, and delete operation on Category records submitted through the
  admin MUST be routed through the service layer before any data is persisted.
- **FR-002**: Every create, update, and delete operation on Item records submitted through the admin
  MUST be routed through the service layer before any data is persisted.
- **FR-003**: Every create, update, and delete operation on Tag records submitted through the admin
  MUST be routed through the service layer before any data is persisted.
- **FR-004**: When the service layer raises a validation error (including cycle detection), the admin
  MUST display a human-readable error message in the form and MUST NOT persist the invalid data.
- **FR-005**: When the service layer raises a non-validation error, the admin MUST surface an error
  message to the administrator rather than propagating an unhandled exception.
- **FR-006**: All read operations (list view, detail view, graph view) MUST continue to function
  without regression.
- **FR-007**: The admin graph view (already using the service) MUST remain unchanged.
- **FR-008**: The dependency chain MUST be: admin views → service layer → repository → database.
  The admin MUST NOT call repository or database methods directly.

### Key Entities

- **Category**: A taxonomy node that may have zero or more parent categories, forming a DAG.
  Business rules include cycle detection, field length limits, and enabled/disabled state.
- **Item**: A content item assigned to one or more categories. Business rules include external ID
  validity and enabled/disabled state.
- **Tag**: A label that can be applied to items. Business rules include name uniqueness and length.
- **CategoryParentLink**: A directed edge in the category DAG. Adding an edge must pass cycle
  detection before persisting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of admin mutations (create, update, delete) on Category, Item, and Tag entities
  are routed through the service layer — verifiable by replacing the service with a test double and
  confirming all admin form submissions call service methods.
- **SC-002**: Attempting to create a cyclic category parent relationship via the admin form results
  in a displayed validation error, with zero data written to storage.
- **SC-003**: All existing admin-related tests pass without modification to test assertions.
- **SC-004**: The full quality gate suite (lint, type check, tests with ≥ 80% coverage) passes
  with no new failures.
- **SC-005**: No admin operation surfaces a raw unhandled exception page to the user when the
  service returns an error.

## Assumptions

- The service layer already implements all required create/update/delete methods for Category, Item,
  and Tag. No new service methods need to be added.
- The `CategoryParentLink` relationship is managed through category-level admin actions (inline or
  parent-field), not via a separate `CategoryParentLinkModel` admin registration.
- Inline editing of parent links (if present in the admin) is in scope and must also route through
  the service.
- Read/list/detail views (non-mutating) are out of scope for service-layer routing; they may
  continue to query the ORM directly — no change required.
- Existing admin tests that mock or interact with the ORM directly may require updating to use the
  service; this is expected and in scope.

## Dependencies

- Service layer — must expose create/update/delete methods for all three entity types (already
  implemented; no new methods needed).
- Repository layer — must be usable as the backing store for a service instance within the admin
  context (already implemented).
- Admin form hooks — used to intercept mutations before they reach the database (existing framework
  mechanism; no new code outside the admin module).
