# Feature Specification: Atomic Multi-Write Service Operations

**Feature Branch**: `058-atomic-operations`  
**Created**: 2026-07-17  
**Status**: Draft  
**Input**: User description: "Make the service's multi-write operations atomic via a repository-level atomic() context manager (operation-level / L2 consistency)."

## Clarifications

### Session 2026-07-17

- Q: On a transactional backend, after a mid-operation write fails and the operation rolls back, what does the caller observe? → A: The operation raises a taxomesh-specific exception that **chains** the original error as its cause. Resolved in `/speckit.plan`: reuse the existing `TaxomeshRepositoryError` (no new exception class); only **raw** (non-`TaxomeshError`) backend exceptions are wrapped — existing `TaxomeshError` subclasses (e.g. `TaxomeshDuplicateSlugError`, `TaxomeshExternalIdConflictError`) propagate unchanged so current behavior is preserved.
- Q: Where must the two-tier consistency guarantee (full rollback vs. best-effort no-op) be documented (FR-008)? → A: Docstrings only — on the repository protocol's `atomic()` method plus per-adapter overrides. No README change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No orphaned data when a multi-write operation fails midway (Priority: P1)

A consumer of the library (via the service layer, CLI, or admin) performs an
operation that internally writes more than one record — for example, creating a
category, which saves the category record and then links it to a parent. If the
second write fails (validation error, constraint violation, transient backend
error), the operation must not leave the first write persisted. On a
transactional backend the datastore is left exactly as it was before the
operation began.

**Why this priority**: This is the entire point of the feature. Today a
mid-operation failure can persist a category with no parent link — an orphan
unreachable from the root — corrupting the library's own invariants. This is
the core value and the minimum viable slice.

**Independent Test**: Force the second (or Nth) write of each affected operation
to raise on a transactional backend, then assert the datastore is byte-for-byte
unchanged: no orphaned category, no half-applied reorder, no half-applied
reparent.

**Acceptance Scenarios**:

1. **Given** a transactional backend, **When** `create_category` saves the
   category but the parent-link write then fails, **Then** the category is not
   persisted, no parent link exists, and the caller receives a taxomesh-specific
   exception that chains the original error as its cause.
2. **Given** a transactional backend and a category with N ordered children,
   **When** `reparent_category` deletes the old parent link but a subsequent
   link write fails, **Then** the original parent link and original ordering are
   fully restored (no partial reparent, no lost link).
3. **Given** a transactional backend, **When** any of `reorder_subcategories`,
   `reorder_items_in_category`, or `reparent_item` fails on the Nth write of its
   loop, **Then** none of the writes from that operation survive.

---

### User Story 2 - Successful operations behave exactly as before (Priority: P1)

Wrapping the affected operations in a consistency boundary must not change their
observable success behavior. A successful `create_category`,
`reorder_subcategories`, `reorder_items_in_category`, `reparent_category`, or
`reparent_item` produces the same result and same persisted state as it does
today. Single-write operations are untouched.

**Why this priority**: The change must be transparent on the happy path — a
regression here would break every existing consumer. It ships together with
User Story 1.

**Independent Test**: Run the existing service and adapter test suites; all
current passing behavior for the five operations and all single-write operations
remains green.

**Acceptance Scenarios**:

1. **Given** any backend, **When** an affected operation completes without
   error, **Then** its persisted result is identical to the pre-change behavior.
2. **Given** any backend, **When** a single-write operation runs, **Then** its
   behavior is unchanged (it was already atomic at the storage level).

---

### User Story 3 - Per-backend guarantee is documented and honest (Priority: P2)

The consistency guarantee differs by backend, and consumers must be able to know
which guarantee they get. Transactional backends give full rollback.
File-based and in-memory backends provide a best-effort no-op boundary: a
mid-operation failure may leave partial state. This limitation is documented
explicitly as a per-backend characteristic, not treated as a defect.

**Why this priority**: Consumers making correctness decisions (e.g. whether they
need their own recovery logic) depend on knowing the real guarantee. Important,
but the behavior itself is delivered by Stories 1–2; this story is the
documentation and contract clarity around it.

**Independent Test**: Verify documentation states the two-tier guarantee, and a
test asserts the file/in-memory backends expose the best-effort (no-op) boundary
semantics the documentation describes.

**Acceptance Scenarios**:

1. **Given** the published documentation, **When** a consumer reads the
   consistency section, **Then** it clearly states full rollback on
   transactional backends and best-effort (possible partial state) on
   file/in-memory backends.
2. **Given** a file or in-memory backend, **When** the consistency boundary is
   entered and exited, **Then** it behaves as a no-op that never changes the
   operation's outcome on success.

---

### Edge Cases

- **Nested boundaries on transactional backends**: Each individual repository
  method already runs inside its own storage-level consistency boundary. When
  the service wraps a whole operation, these inner boundaries must nest inside
  the outer one and roll back together as a unit — the inner boundaries are not
  removed.
- **Failure on the very first write**: The operation fails before any state
  change is visible; the datastore is trivially unchanged.
- **Failure on the last write of a loop**: All prior loop writes from the same
  operation must be undone on transactional backends.
- **Best-effort backends with partial failure**: On file/in-memory backends a
  mid-operation failure may leave partial state; this is the documented,
  accepted limitation and is not treated as a bug.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository contract MUST expose a single consistency-boundary
  mechanism that callers can enter around a sequence of writes and whose meaning
  each backend defines.
- **FR-002**: The five multi-write service operations — `create_category`,
  `reorder_subcategories`, `reorder_items_in_category`, `reparent_category`, and
  `reparent_item` — MUST each execute all of their writes within a single
  consistency boundary.
- **FR-003**: On a transactional backend, if any write within an affected
  operation fails, the system MUST leave the datastore in the exact state it was
  in before the operation began (full rollback; no partial state survives).
- **FR-004**: On file-based and in-memory backends, the consistency boundary
  MUST behave as a best-effort no-op that does not alter the operation's
  successful outcome; partial state after a mid-operation failure is an accepted,
  documented limitation.
- **FR-005**: The existing per-method storage-level boundaries on the
  transactional backend MUST continue to function and MUST nest within the
  operation-level boundary so that they roll back together as one unit.
- **FR-006**: Service orchestration logic for the five operations MUST remain in
  the service layer; the consistency boundary MUST NOT cause business/ordering
  logic to move into the backends.
- **FR-007**: Single-write service operations MUST remain unchanged; they are
  already atomic at the storage level.
- **FR-008**: The two-tier consistency guarantee (full rollback on transactional
  backends; best-effort on file/in-memory backends) MUST be documented in
  docstrings — on the repository protocol's `atomic()` method and on each
  adapter's override. No README change is required by this feature.
- **FR-009**: The scope MUST be limited to operation-level (L2) consistency
  within taxomesh's own data. Cross-boundary consistency between a consumer's
  application entities and taxomesh data (L3) is explicitly out of scope and
  remains the consumer's responsibility.
- **FR-010**: The consistency-boundary mechanism MUST be the only new capability
  added to the repository contract. No composite, batch, broad unit-of-work, or
  session abstraction is introduced.
- **FR-011**: When an affected operation fails mid-way, any **raw**
  (non-`TaxomeshError`) exception escaping the consistency boundary MUST be
  re-raised as `TaxomeshRepositoryError`, chaining the original error as its
  cause. Existing `TaxomeshError` subclasses MUST propagate unchanged. Raw
  backend-specific exception types MUST NOT leak to the caller from the affected
  operations.

### Key Entities *(include if feature involves data)*

- **Consistency boundary**: A scope around a sequence of repository writes whose
  guarantee is defined by the active backend. On transactional backends it is a
  rollback boundary; on file/in-memory backends it is a no-op.
- **Multi-write operation**: A single service operation that performs more than
  one repository write (a save plus a link, or a delete plus a loop of saves).
  These are the five operations this feature protects.
- **Category parent link / Item parent link**: The records written in the loops
  of the affected operations; their partial persistence is the concrete failure
  mode this feature prevents on transactional backends.
- **Rollback exception**: The existing `TaxomeshRepositoryError` is reused as the
  type raised when an affected operation fails on a raw backend error and rolls
  back. It chains the original error as its cause and shields consumers from
  backend-specific exception types. No new exception class is introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the five affected operations, a forced mid-operation
  write failure on a transactional backend leaves zero partial records — 100% of
  such failures result in an unchanged datastore.
- **SC-002**: No orphaned category (a category with no parent link) can be
  produced by a failed `create_category` on a transactional backend.
- **SC-003**: All existing service, adapter, and integration tests continue to
  pass, confirming successful-path behavior for the five operations and all
  single-write operations is unchanged.
- **SC-004**: Failure-injection coverage exists for all five operations,
  including at least one fixed-pair operation (`create_category`) and at least
  one loop-shaped operation that includes a delete (a reparent).
- **SC-005**: The best-effort (no-op) semantics of file/in-memory backends are
  asserted by test to match exactly what the documentation states.
- **SC-006**: The full quality gate stays green: linting, formatting, strict
  type checking, and the test suite at ≥ 80% coverage.
- **SC-007**: A failed affected operation on a transactional backend raises a
  taxomesh-specific exception whose cause chain contains the original error, and
  no raw backend-specific exception type reaches the caller — asserted by test.

## Assumptions

- The "transactional backend" in this project is the Django ORM adapter; "file
  backends" are the JSON and YAML adapters; "in-memory" is the test-fixture
  repository. The guarantee is expressed per-backend regardless of naming.
- Nesting the existing per-method boundaries inside the new operation-level
  boundary is supported by the transactional backend (to be verified during
  implementation, not assumed away).
- Consumers needing consistency across their own application entities and
  taxomesh data will continue to provide that boundary themselves (L3 is out of
  scope).

## Out of Scope

- Cross-boundary (L3) transactions spanning consumer application entities and
  taxomesh data.
- Any broad unit-of-work, session, composite, or batch repository abstraction.
- Adding transactional guarantees to file-based or in-memory backends.
- Changing any single-write service operation.
