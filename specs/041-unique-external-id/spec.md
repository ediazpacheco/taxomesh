# Feature Specification: Unique External ID (1:1 Constraint)

**Feature Branch**: `041-unique-external-id`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "Make external_id a true 1:1 unique identifier on both Item and Category."

## Background

`external_id` was originally designed to bridge an external system's identifiers to taxomesh
internal IDs. The original design (spec 013) explicitly allowed duplicates, returning a
`list[Item]` / `list[Category]` and using list length as an orphan/duplicate signal.

This design is unnecessarily complex. The consuming application owns a 1:1 mapping between
its entities and taxomesh Items/Categories. Duplicates are not a valid use case. This spec
simplifies the data model, the API, and all dependent layers to reflect that reality.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Look up an Item by its external identifier (Priority: P1)

A developer calls the library to retrieve the Item that corresponds to a known external entity
(e.g., an article UUID from the consuming app). The call returns either the Item or nothing —
no list, no length check.

**Why this priority**: This is the primary use case for `external_id`. Simplifying the return
type removes ambiguity and reduces error-prone caller code.

**Independent Test**: Can be fully tested by creating an Item with an `external_id`, calling
`get_item_by_external_id()`, and asserting the returned Item matches; then calling with an
unknown id and asserting `None` is returned.

**Acceptance Scenarios**:

1. **Given** an Item exists with `external_id = "abc-123"`, **When** `get_item_by_external_id("abc-123")` is called, **Then** that exact Item is returned.
2. **Given** no Item exists with `external_id = "xyz"`, **When** `get_item_by_external_id("xyz")` is called, **Then** `None` is returned.
3. **Given** an Item exists with `external_id = None`, **When** it is retrieved by its `item_id`, **Then** the Item's `external_id` is `None`.

---

### User Story 2 — Look up a Category by its external identifier (Priority: P1)

A developer calls the library to retrieve the Category that corresponds to a known external
entity. The call returns either the Category or nothing.

**Why this priority**: Symmetric with item lookup; same simplification applies.

**Independent Test**: Can be fully tested by creating a Category with an `external_id`, calling
`get_category_by_external_id()`, and asserting the result.

**Acceptance Scenarios**:

1. **Given** a Category exists with `external_id = "cat-ext-1"`, **When** `get_category_by_external_id("cat-ext-1")` is called, **Then** that Category is returned.
2. **Given** no Category matches, **When** `get_category_by_external_id("unknown")` is called, **Then** `None` is returned.
3. **Given** the root Category (which always has `external_id = None`), **When** `get_category_by_external_id` is called for any value, **Then** the root Category is never returned.

---

### User Story 3 — Enforce uniqueness at write time (Priority: P1)

When creating or updating an Item or Category, the system rejects an `external_id` that is
already assigned to another record of the same type. The caller receives a clear, actionable
error.

**Why this priority**: Without write-time enforcement, the uniqueness guarantee is meaningless.
This is the gate that prevents duplicate state from being created.

**Independent Test**: Can be fully tested by creating two Items with the same `external_id`
and asserting the second creation raises a specific, documented error.

**Acceptance Scenarios**:

1. **Given** Item A has `external_id = "dup"`, **When** Item B is saved with `external_id = "dup"`, **Then** `TaxomeshExternalIdConflictError` is raised and Item B is not persisted.
2. **Given** Category A has `external_id = "dup-cat"`, **When** Category B is saved with `external_id = "dup-cat"`, **Then** `TaxomeshExternalIdConflictError` is raised and Category B is not persisted.
3. **Given** Item A has `external_id = "shared"`, **When** a Category is saved with `external_id = "shared"`, **Then** no error is raised — uniqueness is scoped per entity type (Items and Categories are separate namespaces).
4. **Given** multiple Items with `external_id = None`, **When** another Item with `external_id = None` is created, **Then** no error is raised — `None` is never treated as a duplicate.

---

### User Story 4 — Create Items and Categories without an external identifier (Priority: P2)

Items and Categories that have no corresponding external entity can be created without
providing an `external_id`. The absence is represented as `None`, not as an empty string.

**Why this priority**: Enabling `None` is a prerequisite for the uniqueness constraint —
`""` as a sentinel cannot be made unique.

**Independent Test**: Can be fully tested by creating an Item without an `external_id` and
verifying the stored value is `None` across all three repository backends.

**Acceptance Scenarios**:

1. **Given** an Item is created without specifying `external_id`, **When** it is retrieved, **Then** its `external_id` is `None`.
2. **Given** a Category is created without specifying `external_id`, **When** it is retrieved, **Then** its `external_id` is `None`.
3. **Given** many Items with `external_id = None`, **When** they are all retrieved, **Then** all return `external_id = None` — no uniqueness collision occurs.

---

### Edge Cases

- What happens when `external_id` input is a UUID or integer? It must be coerced to `str` before storage and lookup; `None` input stays `None`.
- What happens when `get_item_by_external_id(None)` is called? The service returns `None` immediately — `None` is not a searchable value.
- What happens when existing persisted data has `external_id = ""`? The migration converts all `""` values to `NULL` before applying the unique constraint.
- What happens if production data contains actual duplicate non-empty `external_id` values? The migration does not resolve duplicates automatically — they must be resolved manually before the migration is applied.
- What happens when the root Category's `external_id` is checked? It is `None` and must never be returned by `get_category_by_external_id`.
- What happens when an Item is re-saved with the same `external_id` it already owns? The uniqueness check passes — the record being saved is excluded from the conflict check (same primary key). This applies to all three backends.
- Can `external_id` be changed to a different non-None value? Yes — `external_id` is mutable. It can be changed to any value (including `None`) via a normal save; the uniqueness constraint is still enforced against other records.

---

## Requirements *(mandatory)*

### Functional Requirements

**Domain Model**

- **FR-001**: `Item.external_id` MUST have type `str | None` with default `None`.
- **FR-002**: `Category.external_id` MUST have type `str | None` with default `None`.
- **FR-003**: The Pydantic validator on `external_id` MUST coerce UUID and integer inputs to `str`; `None` input MUST remain `None`.
- **FR-004**: The constants `DEFAULT_CATEGORY_EXTERNAL_ID` and `DEFAULT_ITEM_EXTERNAL_ID` MUST be removed or redefined as `None` (type `Final[None]` or `Final[str | None]`).

**Repository Protocol**

- **FR-005**: `TaxomeshRepositoryBase` MUST replace `list_items_by_external_id(external_id: str) -> list[Item]` with `get_item_by_external_id(external_id: str) -> Item | None`.
- **FR-006**: `TaxomeshRepositoryBase` MUST replace `list_categories_by_external_id(external_id: str) -> list[Category]` with `get_category_by_external_id(external_id: str) -> Category | None`.
- **FR-007**: Both new protocol methods MUST return `None` when no match is found (repository layer; no exception raised for missing records).
- **FR-008**: Saving an Item or Category with a non-None `external_id` that already exists in **a different record** of the same type MUST raise `TaxomeshExternalIdConflictError`. Re-saving a record with its own existing `external_id` (same primary key) MUST succeed. Records with `external_id = None` are exempt.

**Repository Implementations**

- **FR-009**: `JsonRepository`, `YAMLRepository`, and `DjangoRepository` MUST implement `get_item_by_external_id` and `get_category_by_external_id` per FR-005 – FR-007.
- **FR-010**: `JsonRepository` and `YAMLRepository` MUST enforce uniqueness on `save_item` / `save_category` and raise `TaxomeshExternalIdConflictError` when a duplicate non-None `external_id` is detected in a **different record** (FR-008). The check MUST exclude the record being saved (matched by primary key) to allow re-saves without conflict.
- **FR-011**: `DjangoRepository` MUST rely on the database `UNIQUE` constraint for conflict detection and translate the resulting `IntegrityError` into `TaxomeshExternalIdConflictError`.
- **FR-012**: `DjangoRepository` MUST remove the `list_items_by_external_id` and `list_categories_by_external_id` method implementations.

**Django ORM**

- **FR-013**: `CategoryModel.external_id` MUST change to `CharField(null=True, blank=True, unique=True, default=None)`.
- **FR-014**: `ItemModel.external_id` MUST change to `CharField(null=True, blank=True, unique=True, default=None)`.
- **FR-015**: A new Django migration MUST: (a) convert existing `""` values to `NULL`; (b) alter both columns to `null=True, unique=True`; (c) drop the old non-unique index. The migration does NOT include a pre-check for duplicate values — if duplicates exist, the database will raise an `IntegrityError` naturally and the operator must resolve them manually before re-running.
- **FR-016**: The unique constraint on both columns MUST use `NULL`-safe semantics — multiple `NULL` values allowed. This is standard SQL behaviour verified for SQLite and PostgreSQL; no partial index is required.

**Service Layer**

- **FR-017**: `TaxomeshService.get_item_by_external_id(external_id: ExternalId) -> Item | None` MUST replace `get_items_by_external_id`.
- **FR-018**: `TaxomeshService.get_category_by_external_id(external_id: ExternalId) -> Category | None` MUST replace `get_categories_by_external_id`. The root Category MUST still be excluded.
- **FR-019**: Both service methods MUST return `None` (not raise) when no matching record is found (service layer complement to FR-007; the service adds the `None` short-circuit for `None` input and root-category exclusion on top of the repository guarantee).
- **FR-020**: Both service methods MUST return `None` immediately when called with `external_id = None`.

**Error Handling**

- **FR-021**: A new exception `TaxomeshExternalIdConflictError` MUST be added to `taxomesh.exceptions`. It MUST subclass `TaxomeshError` and include the conflicting `external_id` value in its message.

**CLI**

- **FR-022**: Any CLI command that displays `external_id` MUST render `None` as `—` (U+2014 em dash) rather than the literal string `"None"`.
- **FR-023**: Any CLI command that accepts `external_id` as input MUST treat an empty string argument as `None`.

**Django Admin**

- **FR-024**: Admin `list_display` for both Item and Category MUST display `external_id` as an empty cell when the value is `None` — not the string `"None"`.
- **FR-025**: Admin `search_fields` MUST retain `external_id`. Django's search backend handles `NULL`/`None` values in `CharField` columns correctly (an `icontains` search against a NULL column simply yields no match), so no removal is needed.
- **FR-026**: Admin forms MUST accept an empty input for `external_id` and persist it as `NULL`.

**Documentation**

- **FR-027**: All docstrings referencing `list_items_by_external_id`, `list_categories_by_external_id`, or the orphan/duplicate list-length semantics MUST be updated or removed.
- **FR-028**: The README public API section MUST be updated to document `get_item_by_external_id` / `get_category_by_external_id` with `None` return semantics and `TaxomeshExternalIdConflictError`.
- **FR-029**: `CLAUDE.md` Active Technologies entries referencing specs 013 (`external-id-lookup`) and 021 (`optional-external-id`) MUST be updated to reflect the new `str | None` type, 1:1 constraint, and new exception.
- **FR-030**: Inline comments in all modified files MUST reflect the new semantics; references to "orphan", "duplicate signal", or "len > 1" MUST be removed.

**Tests**

- **FR-031**: All tests in `tests/test_service_external_id.py` MUST be replaced. New tests MUST cover: (a) found → returns entity; (b) not found → returns `None`; (c) `None` input → returns `None`; (d) UUID/int coercion; (e) root Category never returned.
- **FR-032**: Tests MUST cover `TaxomeshExternalIdConflictError` on duplicate writes for all three repository backends. Tests MUST also verify that re-saving a record with its own existing `external_id` does NOT raise an error.
- **FR-033**: Tests MUST cover `None` round-trips (save with `None`, retrieve, assert `external_id is None`) for all three repository backends.
- **FR-034**: Django-specific tests MUST verify that multiple records with `external_id = NULL` do not trigger a unique constraint violation.

### Key Entities

- **Item**: Domain entity. `external_id: str | None` — optional link to an external record. Unique within all Items, excluding `None`.
- **Category**: Domain entity. `external_id: str | None` — optional link to an external record. Unique within all Categories, excluding `None`.
- **TaxomeshExternalIdConflictError**: New exception raised when a non-None `external_id` conflicts with an existing record of the same entity type.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `get_item_by_external_id` and `get_category_by_external_id` each return a single entity or `None` — callers never need to inspect list length to determine lookup state.
- **SC-002**: Assigning the same non-None `external_id` to two Items (or two Categories) always raises `TaxomeshExternalIdConflictError` — verified across all three storage backends.
- **SC-003**: The full quality gate passes without modification: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov=taxomesh --cov-fail-under=80`.
- **SC-004**: No call site in the library or tests references the removed `list_items_by_external_id` or `list_categories_by_external_id` names after the change.
- **SC-005**: All three repository backends correctly store and retrieve `None` as the absent-value sentinel; the empty string `""` no longer appears as a valid `external_id` value anywhere in the codebase or persisted data.
- **SC-006**: The Django migration applies cleanly on a database with existing `""` values and on a fresh database.

---

## Dependencies

- Specs 013 (`external-id-lookup`), 021 (`optional-external-id`), and 032 (`external-id-index`) are superseded by this spec for uniqueness and lookup semantics. The migration in this spec must account for data written under those prior specs (rows with `external_id = ""`).
- `TaxomeshExternalIdConflictError` must be exported from `taxomesh.exceptions` alongside existing error types.

## Assumptions

- The consuming application does not have existing data where two Items (or two Categories) legitimately share the same non-empty `external_id`. If true duplicates exist in production data, they must be resolved manually before applying the migration.
- SQLite and PostgreSQL both allow multiple `NULL` values under a `UNIQUE` constraint — this is standard SQL behaviour and does not require a partial index.
- The `ExternalId` type alias (`str | int | UUID`) is retained at service-layer inputs for coercion convenience; internally `external_id` is always `str | None`.

---

## Clarifications

### Session 2026-03-20

- Q: When re-saving a record with its own existing `external_id`, is this a conflict? → A: No — pass through (same record, not a conflict). The uniqueness check must exclude the record being saved by primary key.
- Q: Should the Django migration include a safety guard that checks for duplicate non-empty `external_id` values before applying the unique constraint? → A: No — no guard; let the database raise `IntegrityError` naturally if duplicates exist.
- Q: Is `external_id` mutable once set to a non-None value, or immutable? → A: Mutable — can be changed to any value (including `None`) via a normal save; uniqueness enforced against other records.
