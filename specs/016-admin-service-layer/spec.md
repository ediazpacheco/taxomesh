# Feature Specification: Admin Service Layer

**Feature Branch**: `016-admin-service-layer`
**Created**: 2026-03-01
**Status**: Implemented
**Input**: User description: "currently the django admin interactua directamente con el ORM. Esto tiene de problema que todas las validaciones de datos, por ej de dependencia ciclica, son evitados. Refactor the admin integration to work with the TaxomeshService and not with the ORM directly. The dependency should be: django admin -> TaxomeshService -> DjangoRepository -> django ORM"

## Clarifications

### Session 2026-03-01

- Q: Does this feature include adding UI to manage category parent relationships in the admin (currently absent), or only route existing CRUD operations through the service? → A: Add a `CategoryParentLink` inline to `CategoryModelAdmin` AND route it through the service.
- Q: Should the `TaxomeshService` instance in admin be created per-request or shared as a class attribute? → A: Per-request — instantiate fresh on each admin method call.
- Q: Should Django admin bulk actions (e.g. bulk delete via changelist checkboxes) also route through the service? → A: Yes — bulk delete on Category, Item, and Tag must route through the service.

### Session 2026-03-01 (continued)

- Q: SC-003 stated existing tests must pass without modification, but Assumptions says tests may need updating — which is correct? → A: Existing tests may be updated to mock/stub the service layer instead of the ORM.
- Q: Should inlines for `ItemParentLink` (item-to-category) and `ItemTagLink` (tag-to-item) also be added and routed through the service? → A: Yes — add inlines for both, routed through the service.

### Session 2026-03-01 (post-implementation)

- Q: FR-008 says the admin MUST NOT call repository or database methods directly (absolute), but the Assumptions section says read views may query the ORM directly — which scope is correct? → A: Narrow FR-008 to mutation operations only; read operations (list view, detail view, FK dropdowns) may query the ORM directly.
- Q: Should SC-002 explicitly cover self-reference (A→A) alongside multi-node cycles, or is it implicit? → A: Extend SC-002 to name both cyclic and self-referential relationships explicitly.
- Q: Should the root-category visibility rule and `Category.is_root` property be formal requirements, or remain as Assumptions only? → A: Promote to requirements — add FR-014 for root hiding and document `is_root` in Key Entities.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cycle Detection Enforced via Parent-Link Inline (Priority: P1)

A taxonomy administrator opens the Django admin category detail page, which now includes an inline
section for managing parent-category relationships. When the admin adds a parent that would create a
cyclic relationship (e.g. A → B → A), the inline rejects the save and displays a clear validation
error. No data is written.

**Why this priority**: Cycle detection is the primary business rule bypassed today. A cycle in the
taxonomy DAG corrupts the data model and causes cascading failures in graph traversal. The inline is
the primary new UI surface through which parent links are created — enforcing the rule here is the
core motivation for this feature.

**Independent Test**: Can be fully tested by using the inline to add a parent that creates a cycle
and verifying the error message is shown and the relationship is unchanged.

**Acceptance Scenarios**:

1. **Given** categories A and B exist with A as parent of B, **When** an admin user uses the
   parent-link inline on B to add A as a parent (which would create a cycle), **Then** the admin
   form shows a validation error and the category-parent relationship is not changed.
2. **Given** a category with no parents, **When** an admin user uses the parent-link inline to add
   a valid (non-cyclic) parent, **Then** the save succeeds and the relationship is persisted.
3. **Given** an existing parent-link in the inline, **When** an admin user deletes it, **Then** the
   service removes the relationship and the inline reflects the updated state.

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

### User Story 4 — Item Placement and Tag Assignment via Inlines (Priority: P3)

A taxonomy administrator opens an Item record in the Django admin. The item detail page includes two
new inline sections: one for assigning the item to categories, and one for assigning tags to the
item. All additions and removals via these inlines are routed through the service layer.

**Why this priority**: Without these inlines, the admin has no UI for placing items into categories
or tagging items. Routing them through the service ensures service-layer business rules apply to
these relationships, consistent with all other mutations in this feature.

**Independent Test**: Can be fully tested by adding and removing a category placement and a tag
assignment via the item detail page inlines and verifying the service methods are called.

**Acceptance Scenarios**:

1. **Given** an item and a category exist, **When** an admin user uses the item-category inline to
   place the item in the category, **Then** the service persists the placement and it appears in the
   inline.
2. **Given** an item-category placement exists in the inline, **When** an admin user removes it,
   **Then** the service removes the placement and the inline is updated.
3. **Given** a tag exists, **When** an admin user uses the item-tag inline to assign the tag to an
   item, **Then** the service persists the assignment.
4. **Given** a tag assignment exists in the inline, **When** an admin user removes it, **Then** the
   service removes the assignment.

---

### Edge Cases

- What happens when an admin user attempts to add a category as its own parent (A → A)?
  The admin form must reject it with a validation error ("A category cannot be its own parent.") and
  no link is created. This is enforced at both the form `clean()` level and the service layer.
- What happens when the service raises an unexpected error (not a validation error) during a save?
  The admin must surface an error message rather than showing an unhandled exception page.
- What happens during a bulk delete when some records succeed and others fail service validation?
  Each record is processed individually; successful deletions proceed and failures are reported
  per-record without rolling back the successful ones.
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
  MUST display a human-readable error message (as a form-level validation error or an admin message
  banner) and MUST NOT persist the invalid data.
- **FR-005**: When the service layer raises a non-validation error, the admin MUST surface an error
  message to the administrator rather than propagating an unhandled exception.
- **FR-006**: All read operations (list view, detail view, graph view) MUST continue to function
  without regression.
- **FR-007**: The admin graph view (already using the service) MUST remain unchanged.
- **FR-008**: For every **mutating** operation (create, update, delete, bulk delete, inline row add/remove),
  the dependency chain MUST be: admin views → service layer → repository → database. The admin MUST NOT
  call repository or database methods directly for any mutation. Read operations (list view, detail view,
  FK dropdown querysets) may query the ORM directly without routing through the service.
- **FR-009**: The `CategoryModelAdmin` MUST include an inline section for managing
  `CategoryParentLink` records. Adding a parent link via this inline MUST pass cycle detection
  (via `check_no_cycle()` in the inline's `ModelForm.clean()`) before any data is persisted;
  cycle or self-reference violations MUST surface as form-level validation errors. Removing a
  parent link via this inline MUST route through the service layer
  (`service.remove_category_parent()`).
- **FR-010**: Bulk delete actions on Category, Item, and Tag records (via the changelist checkbox
  selection) MUST route each deletion through the service layer. If the service raises an error for
  any record, that record MUST NOT be deleted and the error MUST be reported to the administrator.
  *(FR-011 was reserved during drafting and subsequently removed; FR-012 follows FR-010 intentionally.)*
- **FR-012**: The `ItemModelAdmin` MUST include an inline section for managing `ItemParentLink`
  records (item-to-category placements). Adding or removing placements via this inline MUST be
  routed through the service layer before any data is persisted.
- **FR-013**: The `ItemModelAdmin` MUST include an inline section for managing `ItemTagLink`
  records (tag-to-item assignments). Adding or removing assignments via this inline MUST be routed
  through the service layer before any data is persisted.
- **FR-014**: The internal root category (identified by `Category.is_root`) MUST NOT appear in any
  admin-facing view, including the `CategoryModelAdmin` changelist and any FK dropdown that allows
  selecting a category (e.g. the `parent_category` field in `CategoryParentLinkInline`). This is
  enforced via `get_queryset()` and `formfield_for_foreignkey()` overrides.

### Key Entities

- **Category**: A taxonomy node that may have zero or more parent categories, forming a DAG.
  Business rules include cycle detection, field length limits, and enabled/disabled state.
  Exposes an `is_root: bool` computed property that returns `True` when the category's name equals
  the reserved `ROOT_CATEGORY_NAME` constant. The root category is an internal implementation node
  and must never be visible to administrators.
- **Item**: A content item assigned to one or more categories. Business rules include external ID
  validity and enabled/disabled state.
- **Tag**: A label that can be applied to items. Business rules include name uniqueness and length.
- **CategoryParentLink**: A directed edge in the category DAG. Adding an edge must pass cycle
  detection before persisting.
- **ItemParentLink**: An assignment of an item to a category. Managed via inline on the item detail
  page; additions and removals route through the service.
- **ItemTagLink**: An assignment of a tag to an item. Managed via inline on the item detail page;
  additions and removals route through the service.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of admin mutations (create, update, delete, and bulk delete) on Category, Item,
  and Tag entities, plus all inline row mutations (CategoryParentLink, ItemParentLink, ItemTagLink)
  are routed through the service layer — verifiable by replacing the service with a test double and
  confirming all admin form submissions and bulk action invocations call service methods.
- **SC-002**: Attempting to create a cyclic or self-referential category parent relationship (including
  A → B → A multi-node cycles and A → A self-reference) via the parent-link inline results in a
  displayed validation error with a human-readable message, with zero data written to storage.
- **SC-003**: All admin-related test coverage is maintained or improved. Existing tests that mock
  ORM calls directly may be updated to mock the service layer instead; no test that previously
  passed may be deleted without a replacement that covers the same behaviour.
- **SC-004**: The full quality gate suite (lint, type check, tests with ≥ 80% coverage) passes
  with no new failures.
- **SC-005**: No admin operation surfaces a raw unhandled exception page to the user when the
  service returns an error.

## Assumptions

- During implementation, two new service methods were discovered to be necessary and were added:
  `remove_category_parent` and `remove_item_from_category`. Two corresponding repository port methods
  (`delete_category_parent_link`, `delete_item_parent_link`) were also added across all three
  adapters. The original assumption that "no new service methods need to be added" was incorrect.
- New inlines are added as part of this feature: `CategoryParentLink` on `CategoryModelAdmin`,
  and `ItemParentLink` + `ItemTagLink` on `ItemModelAdmin`. None are registered as standalone model
  admins. All inline mutations route through the service.
- The service layer is instantiated fresh on each admin request (per-request lifecycle), consistent
  with the existing graph view pattern. No shared service instance is stored as a class attribute.
- Read/list/detail views (non-mutating) are out of scope for service-layer routing; they may
  continue to query the ORM directly — no change required.
- Existing admin tests that mock or interact with the ORM directly may require updating to use the
  service; this is expected and in scope.
- A `__str__` method was added to `CategoryModel` outside the formal spec cycle to improve admin
  dropdown readability (`"<name> (<category_id>)"`). It is cosmetic and carries no business-rule
  implications.
- A correctness fix was applied to `CategoryModelAdmin.save_model` and `ItemModelAdmin.save_model`
  after initial implementation: when creating a new record, the service-created entity's PK is
  synced back to the Django ORM instance (`obj.pk`, `obj._state.adding = False`) so that Django
  can use the instance as a FK target for inline formset saves. This is an implementation detail
  of FR-001/FR-002, not a new requirement.
- A post-implementation bug was discovered: `InlineModelAdmin.save_model()` is **never called** by
  Django's default inline formset save flow — Django calls `formset.save()` → `form.instance.save()`
  directly. The `save_model()` override in `CategoryParentLinkInline` was therefore dead code and
  cycle detection was fully bypassed in practice. The fix was to add `CategoryParentLinkForm`
  (a `ModelForm` subclass) with a `clean()` method that runs before any ORM write. `clean()` checks
  for self-reference (explicit guard) and calls `check_no_cycle()` from the domain layer; both
  convert domain exceptions to `forms.ValidationError`. The inline sets `form = CategoryParentLinkForm`.
  This is the correct idiomatic Django hook for pre-save validation on inline rows.
- An explicit self-reference guard was added to `service.add_category_parent()`: if
  `category_id == parent_id`, a `TaxomeshCyclicDependencyError` is raised with the message
  "Category {id} cannot be its own parent." before `check_no_cycle()` is called. This ensures
  a clear error message regardless of which code path triggers the check.
- `ROOT_CATEGORY_NAME` was moved from `taxomesh/application/service.py` to
  `taxomesh/domain/constants.py`. It is a domain-level constant and its prior location in the
  application layer was incorrect. All callers (`service.py`, `django_repository.py`, admin tests)
  now import it from `domain/constants`. No behaviour change.
- `Category.is_root: bool` property was added to the `Category` domain model. It returns
  `self.name == ROOT_CATEGORY_NAME`. This is a purely read-only, computed property with no
  storage implications.
- `CategoryModelAdmin.get_queryset()` was overridden to exclude the root category
  (`name == ROOT_CATEGORY_NAME`) from the admin changelist. The root category is an internal
  implementation detail and must not be visible to administrators.
- `CategoryParentLinkInline.formfield_for_foreignkey()` was overridden to exclude the root
  category from the `parent_category` FK dropdown. Root cannot be selected as a parent.

## Dependencies

- Service layer — must expose create/update/delete methods for all three entity types (already
  implemented; no new methods needed).
- Repository layer — must be usable as the backing store for a service instance within the admin
  context (already implemented).
- Admin form hooks — used to intercept mutations before they reach the database (existing framework
  mechanism; no new code outside the admin module).
