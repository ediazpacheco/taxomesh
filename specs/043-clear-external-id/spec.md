# Feature Specification: External ID Clear Support

**Feature Branch**: `043-clear-external-id`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Add sentinel-based external_id clearing support to update_item and update_category in TaxomeshService"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clear an external ID to free it for reassignment (Priority: P1)

A developer wants to unlink an external system identifier from an item or category — for example, to transfer that identifier to a different record. They call the update operation passing `None` as the `external_id` value. After the call, the field is cleared and the identifier becomes available to be assigned to another record.

**Why this priority**: This is the core broken use case: without the ability to explicitly clear `external_id`, the unique-constraint reassignment flow is broken and users have no workaround.

**Independent Test**: Can be fully tested by creating a record with an external ID, calling update with `external_id=None`, then verifying the record's external ID is `None` and the old identifier can be assigned to a new record.

**Acceptance Scenarios**:

1. **Given** an item with `external_id = "content-1"`, **When** `update_item` is called with `external_id=None`, **Then** the item's `external_id` is `None`.
2. **Given** an item whose `external_id` was just cleared, **When** a lookup by the old external ID is performed, **Then** no record is returned.
3. **Given** item A had `external_id = "x"` and was cleared, **When** item B is updated with `external_id="x"`, **Then** B receives the identifier without a uniqueness conflict.
4. **Given** a category with `external_id = "cat-1"`, **When** `update_category` is called with `external_id=None`, **Then** the category's `external_id` is `None`.
5. **Given** a category whose `external_id` was just cleared, **When** a lookup by the old external ID is performed, **Then** no record is returned.
6. **Given** category A had `external_id = "y"` and was cleared, **When** category B is updated with `external_id="y"`, **Then** B receives the identifier without a uniqueness conflict.

---

### User Story 2 - Update other fields without touching external_id (Priority: P2)

A developer calls `update_item` or `update_category` to change a field such as `name` or `metadata`, intentionally omitting `external_id`. The existing `external_id` on the record must remain unchanged.

**Why this priority**: This is the "no-op" contract — without it, any call that omits `external_id` would inadvertently clear the value, breaking all existing callers.

**Independent Test**: Can be fully tested by creating a record with an external ID, calling update with no `external_id` argument, and verifying the external ID is unchanged.

**Acceptance Scenarios**:

1. **Given** an item with `external_id = "content-1"`, **When** `update_item` is called without passing `external_id`, **Then** the item's `external_id` remains `"content-1"`.
2. **Given** a category with `external_id = "cat-1"`, **When** `update_category` is called without passing `external_id`, **Then** the category's `external_id` remains `"cat-1"`.

---

### User Story 3 - Assign a new external ID (Priority: P3)

A developer assigns or overwrites the external ID of a record by passing a non-None string value to the update operation. This is the existing happy path and must continue to work unchanged.

**Why this priority**: Existing functionality; must not regress as part of this change.

**Independent Test**: Can be fully tested by creating a record without an external ID and calling update with a string value, then verifying the record carries the new ID.

**Acceptance Scenarios**:

1. **Given** an item with `external_id = None`, **When** `update_item` is called with `external_id="new-id"`, **Then** the item's `external_id` is `"new-id"`.
2. **Given** a category with `external_id = None`, **When** `update_category` is called with `external_id="new-cat"`, **Then** the category's `external_id` is `"new-cat"`.

---

### Edge Cases

- What happens when `external_id=None` is passed for a record that already has `external_id = None`? Expected: no error, record remains unchanged.
- What happens when a string `external_id` is passed but another record already holds that value? Expected: existing uniqueness error is raised; behavior is unchanged from today.
- What happens if the lookup cache is stale after a clear operation? Expected: the cache is invalidated on every write so stale results cannot occur.
- What happens when a clear and a reassignment happen in sequence without any intermediate lookup? Expected: both operations succeed independently and the final state is consistent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The update operation for items MUST distinguish three mutually exclusive `external_id` intents: "leave unchanged", "clear to no value", and "set to a specific string".
- **FR-002**: The update operation for categories MUST distinguish the same three intents as FR-001.
- **FR-003**: When a caller omits the `external_id` argument, the system MUST leave the existing `external_id` value on the record untouched.
- **FR-004**: When a caller passes `None` as `external_id`, the system MUST store `None` (no value) on the record, overwriting any previous string value.
- **FR-005**: When a caller passes a non-empty string as `external_id`, the system MUST store that string on the record, subject to the existing uniqueness constraint.
- **FR-006**: After an `external_id` is cleared on a record, a lookup by that external ID value MUST return no result.
- **FR-007**: After an `external_id` is cleared on a record, that same string MUST be assignable to a different record without a uniqueness conflict.
- **FR-008**: The in-process lookup cache for external ID queries MUST be invalidated whenever an update write completes, regardless of whether `external_id` changed.
- **FR-009**: All storage backends MUST correctly persist a cleared `external_id` (no value / null) after a clear operation.
- **FR-010**: The public documentation for `update_item` and `update_category` MUST clearly state the three-state semantics of the `external_id` parameter: omitted means unchanged, `None` means clear, string means set.

### Key Entities

- **Item**: A generic record that can carry an optional unique external system identifier. The identifier is either absent or a non-empty string unique across all items.
- **Category**: A taxonomy node that can carry an optional unique external system identifier. Same uniqueness rules as Item.
- **External ID**: A string token provided by an external system used to look up a specific Item or Category. Exactly one record may hold any given token at a time; the token may be unassigned.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 10 specified test scenarios (US1: 6 clear/lookup/reassign cases; US2: 2 no-op cases; US3: 2 set cases) pass without error.
- **SC-002**: After clearing an external ID, reassignment to a second record succeeds on the first attempt in 100% of cases across all supported storage backends.
- **SC-003**: All existing tests that call `update_item` or `update_category` without an `external_id` argument continue to pass without modification.
- **SC-004**: A lookup for a just-cleared external ID returns no result immediately after the update, with no eventual-consistency delay.
- **SC-005**: Zero uniqueness-constraint violations occur in the full reassignment flow (clear record A → assign same ID to record B) on every supported backend.

## Assumptions

- `external_id` is already `str | None` on both `Item` and `Category` domain models (introduced in 041-unique-external-id / 0.1.0a30).
- All storage backends already support writing `None` to `external_id`; no schema migrations are required for this feature.
- Invalidating the full in-process lookup cache on any write is an acceptable strategy (cache correctness over cache efficiency).
- The mechanism used to represent "not provided" is an internal implementation detail and is not part of the public API contract.
- No CLI surface change is required; this feature only affects the service layer.
- No Django admin UI change is required.

## Dependencies

- **041-unique-external-id**: Introduced `external_id: str | None` on domain models and the uniqueness constraint. This spec depends on those changes being merged and stable (released in 0.1.0a30).
- **Service read cache** (introduced circa spec 028/040): Provides the in-process memoization for external ID lookups. Cache invalidation behavior defined in FR-008 depends on this infrastructure being in place.
