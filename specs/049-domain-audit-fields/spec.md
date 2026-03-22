# Feature Specification: Domain Audit Fields (created_at, updated_at, version)

**Feature Branch**: `049-domain-audit-fields`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "add date of created and last updated to Category/Item; add version: int to Category/Item (default 0, autoincremental on each update)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect Creation and Modification Timestamps (Priority: P1)

A developer using the library creates a Category or Item, then later retrieves it. They can
inspect `created_at` to know when the record originated and `updated_at` to know when it was
last changed — without digging through storage files or repository logs.

**Why this priority**: Timestamps are the most immediately useful form of audit metadata. Every
downstream use case (sorting by recency, filtering stale records, displaying modification history
in a UI) depends on them being present.

**Independent Test**: Can be fully tested by creating a Category/Item, verifying `created_at` and
`updated_at` are set, then updating the entity and verifying `updated_at` advances while
`created_at` is unchanged.

**Acceptance Scenarios**:

1. **Given** a new Category is created, **When** the returned object is inspected, **Then** `created_at` and `updated_at` are both set to the moment of creation and are equal to each other.
2. **Given** an existing Category is updated, **When** the returned object is inspected, **Then** `updated_at` reflects the moment of the update and `created_at` remains unchanged from its original value.
3. **Given** a new Item is created, **When** the returned object is inspected, **Then** `created_at` and `updated_at` are both set to the moment of creation.
4. **Given** an existing Item is updated, **When** the returned object is inspected, **Then** `updated_at` reflects the moment of the update and `created_at` remains unchanged.
5. **Given** a Category or Item is persisted and then reloaded from storage, **When** the reloaded object is inspected, **Then** `created_at` and `updated_at` match the values at the time of persistence.

---

### User Story 2 - Track Modification Count via Version (Priority: P2)

A developer retrieves a Category or Item and records its `version`. Later they retrieve the same
entity again. By comparing versions they can tell whether the entity has changed between the two
reads, enabling optimistic concurrency patterns, cache invalidation, or change detection without
timestamp comparison.

**Why this priority**: The version field enables change detection without requiring callers to
compare timestamps; it is a simpler and more reliable signal. However, it is secondary to
timestamps because timestamps deliver independent value.

**Independent Test**: Can be fully tested by creating an entity (version = 0), performing an
update, and verifying version becomes 1; performing a second update and verifying version becomes 2.

**Acceptance Scenarios**:

1. **Given** a new Category is created, **When** the returned object is inspected, **Then** `version` is `0`.
2. **Given** a Category with `version = N` is updated, **When** the returned object is inspected, **Then** `version` is `N + 1`.
3. **Given** a new Item is created, **When** the returned object is inspected, **Then** `version` is `0`.
4. **Given** an Item with `version = N` is updated, **When** the returned object is inspected, **Then** `version` is `N + 1`.
5. **Given** a Category or Item is persisted and then reloaded from storage, **When** the reloaded object is inspected, **Then** `version` matches the value at the time of persistence.

---

### Edge Cases

- What happens when a Category or Item is loaded from storage that pre-dates this feature (i.e. has no `created_at`, `updated_at`, or `version` stored)? Legacy records must deserialize without error; missing fields fall back to a defined default (e.g. epoch or a sentinel value for timestamps, `0` for version).
- What happens if two processes update the same entity concurrently? The library makes no concurrent-write guarantee — version is a read-side signal only. No locking or conflict error is raised by the library.
- Does the version field ever reset to `0` after creation? No — version is monotonically non-decreasing; it only ever increases.
- What time zone are timestamps stored in? UTC, always. Timezone-aware datetimes only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `Category` model MUST include a `created_at` field representing the UTC datetime when the category was first created.
- **FR-002**: The `Category` model MUST include an `updated_at` field representing the UTC datetime when the category was most recently modified.
- **FR-003**: The `Item` model MUST include a `created_at` field representing the UTC datetime when the item was first created.
- **FR-004**: The `Item` model MUST include an `updated_at` field representing the UTC datetime when the item was most recently modified.
- **FR-005**: The `Category` model MUST include a `version` field of integer type, defaulting to `0` on creation.
- **FR-006**: The `Item` model MUST include a `version` field of integer type, defaulting to `0` on creation.
- **FR-007**: When a Category or Item is first created, `created_at` and `updated_at` MUST be set to the same UTC timestamp representing the moment of creation.
- **FR-008**: `created_at` MUST be immutable after creation — no operation may change it.
- **FR-009**: Only operations that modify an entity's own direct fields (name, description, slug, enabled, metadata, external_id) MUST trigger a `version` increment and `updated_at` refresh. Structural operations (adding/removing parent links, tag assignments, item relations) MUST NOT increment `version` or change `updated_at`.
- **FR-010**: Each time `version` is incremented, `updated_at` MUST be updated to the current UTC datetime at the moment of the operation.
- **FR-011**: `version` MUST be monotonically increasing — it MUST only ever increase by exactly `1` per update operation and MUST never decrease or reset.
- **FR-012**: All existing repository adapters (JSON, YAML, Django ORM) MUST persist and restore `created_at`, `updated_at`, and `version` faithfully across read/write cycles.
- **FR-013**: Records pre-dating this feature that lack `created_at`, `updated_at`, or `version` in storage MUST deserialize without error, using defined sentinel defaults for missing fields.
- **FR-014**: The Django ORM adapter MUST expose `created_at`, `updated_at`, and `version` as queryable columns on the Category and Item database tables, with appropriate migrations.
- **FR-015**: The library MUST set `created_at`, `updated_at`, and `version` automatically — callers MUST NOT be required to supply these values when creating or updating entities.

### Key Entities

- **Category**: Taxonomy node in a DAG. Gains three new audit fields: `created_at` (UTC datetime, immutable), `updated_at` (UTC datetime, mutable), `version` (non-negative integer).
- **Item**: Generic categorized record. Gains the same three audit fields as `Category`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A newly created Category or Item always exposes non-null `created_at`, `updated_at`, and `version = 0` immediately after creation — verified across all repository backends.
- **SC-002**: After any qualifying update operation, `version` is exactly `previous_version + 1` and `updated_at` is later than or equal to the pre-update `updated_at` — verified by round-trip read.
- **SC-003**: `created_at` is identical before and after any number of update operations on the same entity — verified across all repository backends.
- **SC-004**: Existing data (pre-feature records) loads without error across all repository backends; all existing tests continue to pass.
- **SC-005**: All quality gates pass (`ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov=taxomesh --cov-fail-under=80`) with the new fields in place.

## Assumptions

- Timestamps are UTC-aware `datetime` objects (timezone-aware, UTC offset = 0). The library never stores or returns naive datetimes.
- The system clock is the authoritative source for all timestamps — no distributed clock synchronization is required.
- Callers who supply `created_at`, `updated_at`, or `version` explicitly in a constructor call (e.g. when deserializing from storage) are permitted to do so; the library does not forbid it. The auto-management logic lives in the service layer, not in the model's validator.
- `InMemoryRepository` (used in tests) stores and restores `created_at`, `updated_at`, and `version` faithfully via Pydantic (field defaults and serialization). It does **not** implement version atomicity (`version += 1`) — version incrementing is a repository responsibility, and `InMemoryRepository` is a test fixture that relies on the service tests using storage-backed repos (JSON/YAML/Django) to verify that behaviour. Audit-field service tests therefore use `JsonRepository`, not `InMemoryRepository`.
- Pre-existing sentinel defaults for legacy records: `created_at` and `updated_at` default to `datetime(1970, 1, 1, tzinfo=timezone.utc)` (Unix epoch); `version` defaults to `0`. (These defaults are for deserialization only — freshly created records always get the real current UTC time.)
