# Feature Specification: Optional Item external_id

**Feature Branch**: `021-optional-external-id`
**Created**: 2026-03-02
**Status**: Complete
**Input**: User description: "en el flujo actual hay un bug: si trato de crear un Item sin external_id (porque todavía no existe el letrastango.Content asociado) a través del admin de django me da error porque el campo external_id es obligatorio. Hacerlo opcional"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Item Without external_id via Django Admin (Priority: P1)

An admin user wants to register a new Item in taxomesh before the associated external entity (e.g. a `letrastango.Content` object) exists. Currently, submitting the Django admin create form without filling in `external_id` raises a validation error, blocking the action. After this fix, the field is optional and the form saves successfully with an empty `external_id`.

**Why this priority**: This is the reported bug. Without it, admin users cannot pre-create Items that will be linked to external entities later.

**Independent Test**: Navigate to the Django admin Item creation form, leave `external_id` blank, fill in only `name`, and submit. The Item is saved and appears in the list with an empty `external_id`.

**Acceptance Scenarios**:

1. **Given** the Django admin Item create form, **When** the user submits the form with `external_id` left blank and a valid `name`, **Then** the Item is saved successfully with `external_id = ""`.
2. **Given** an existing Item with `external_id = ""`, **When** an admin user later edits the Item and sets a non-empty `external_id`, **Then** the change is saved and the Item is retrievable by that `external_id`.
3. **Given** the Django admin Item create form, **When** the user submits the form with a non-empty `external_id`, **Then** the behaviour is identical to the current (working) behaviour.

---

### User Story 2 - Item Domain Model Accepts Missing external_id (Priority: P2)

When creating an `Item` programmatically (e.g. via the service layer or a test), omitting `external_id` should not raise a validation error. The field defaults to an empty string, consistent with how `Category.external_id` already behaves.

**Why this priority**: The domain model is the source of truth. The Django admin issue is a symptom of the domain model not having a default, so fixing the root cause here unlocks correct behaviour everywhere.

**Independent Test**: Instantiate `Item(name="test")` without providing `external_id`. Verify the instance is created with `external_id = ""` and no exception is raised.

**Acceptance Scenarios**:

1. **Given** the `Item` domain model, **When** `Item` is constructed with only `name` (no `external_id`), **Then** `item.external_id == ""`.
2. **Given** the `Item` domain model, **When** `Item` is constructed with `external_id=None`, **Then** `item.external_id == ""` (existing coercion behaviour retained).
3. **Given** the `Item` domain model, **When** `Item` is constructed with `external_id="abc"`, **Then** `item.external_id == "abc"` (no regression).

---

### Edge Cases

- What happens when an Item has `external_id = ""` and a lookup by `external_id=""` is performed? The call returns all Items with an empty `external_id`, consistent with existing lookup semantics (no special-casing required).
- How does the system handle existing rows in the database that were previously created with a required `external_id`? A migration changes only the column default and form validation; existing rows are unaffected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `Item` domain model MUST allow construction without providing `external_id`, defaulting the field to `""`.
- **FR-002**: The `ItemModel` Django ORM field `external_id` MUST allow blank values (`blank=True, default=""`), so that the Django admin create form does not require the field.
- **FR-003**: A Django migration MUST be generated to alter the `ItemModel.external_id` column to reflect the new optional constraint (empty string default).
- **FR-004**: When a non-string value is passed as `external_id`, it MUST be coerced: `None` MUST coerce to `DEFAULT_ITEM_EXTERNAL_ID` (`""`), while any other non-string value MUST coerce via `str(v)`. The previous behaviour of coercing `None` to the string `"None"` is intentionally corrected.
- **FR-005**: All existing lookups that use `external_id` (e.g. `get_items_by_external_id`) MUST continue to work without modification; no change to lookup semantics is required.
- **FR-006**: `TaxomeshService.create_item()` MUST make `external_id` an optional parameter defaulting to `""`, so that callers can create items without providing an external reference.
- **FR-007**: The CLI `taxomesh item add --external-id` flag MUST become optional (no longer required), consistent with the service and domain model change.

### Key Entities

- **Item** (domain model): Core entity. `external_id` is an escape hatch that lets an item carry a reference to an entity that lives outside taxomesh (e.g. a primary key from another system), for use when the item's built-in fields (`name`, `slug`, `enabled`, `metadata`) are insufficient. The field becomes optional with a default empty string; items that do not need an external reference simply leave it blank.
- **ItemModel** (Django ORM model): Persistence layer. `external_id` column gains a blank-string default for form validation; the DB column remains a non-nullable `VARCHAR` storing `""` when no external reference is provided.

## Clarifications

### Session 2026-03-02

- Q: Should `TaxomeshService.create_item()` and the CLI `item add --external-id` flag also be made optional in this fix, or only the Django admin path? → A: Fix all four layers atomically (domain model, service, CLI, Django ORM + migration).

## Assumptions

- `external_id` is an escape hatch for linking an Item to data that lives outside taxomesh. It is not a required identity — items that don't need an external reference simply leave it blank. This is the intended semantics, not a workaround.
- The empty string `""` is the canonical "no external reference" sentinel, consistent with `DEFAULT_CATEGORY_EXTERNAL_ID = ""` already used by `Category`.
- The DB column type remains `VARCHAR` (not SQL `NULL`); only the Django form validation and ORM default change. This avoids a nullable-column migration on potentially large datasets.
- `Category.external_id` already works correctly and is not in scope.
- `TaxomeshService.create_item()` and the CLI `item add --external-id` flag are also in scope: both currently enforce `external_id` as required and must be relaxed in the same fix. The fix is atomic across all four layers: domain model, service, CLI, and Django ORM + migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin user can create a new Item via the Django admin form without providing `external_id`, with zero validation errors shown.
- **SC-002**: An `Item` instance constructed programmatically without `external_id` has `external_id == ""` and passes Pydantic validation without raising an exception.
- **SC-003**: All existing tests pass after the change with zero regressions.
- **SC-004**: The generated migration applies cleanly on both a fresh database and an existing database that already contains Item rows.
