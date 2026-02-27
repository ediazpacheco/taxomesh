# Feature Specification: Unique Parent Link Constraint

**Feature Branch**: `010-unique-parent-links`
**Created**: 2026-02-27
**Status**: Draft
**Input**: Bug — `taxomesh graph` shows duplicate child categories because `save_category_parent_link()` unconditionally appends. The same `(category_id, parent_category_id)` pair can be stored N times.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Idempotent Category-Parent Assignment (Priority: P1)

A user assigns a category to a parent category via `add_category_parent()`. If
the user (or application code) calls `add_category_parent()` again with the same
category and parent, the operation silently succeeds — updating the `sort_index`
if it changed, without creating a duplicate link. The `taxomesh graph` output
shows each child category exactly once under each parent.

**Why this priority**: This is the root-cause fix for the duplicate-categories
bug in `taxomesh graph`. Without deduplication at the storage level, repeated
calls create phantom duplicates that pollute the graph output.

**Independent Test**: Call `add_category_parent()` twice with the same
`(category_id, parent_category_id)` pair but different `sort_index` values.
Verify that only one link exists and its `sort_index` reflects the latest call.

**Acceptance Scenarios**:

1. **Given** a category C assigned to parent P with `sort_index=0`, **When**
   `add_category_parent(C, P, sort_index=5)` is called again, **Then** only one
   `CategoryParentLink(C, P)` exists and its `sort_index` is `5`.
2. **Given** a category C assigned to parent P, **When** `add_category_parent(C, P)`
   is called again with the same `sort_index`, **Then** the operation succeeds
   silently with no error and no duplicate link.
3. **Given** a category C assigned to parents P1 and P2, **When**
   `add_category_parent(C, P1)` is called again, **Then** only the `(C, P1)` link
   is affected; the `(C, P2)` link remains unchanged.

### User Story 2 - Idempotent Item-Category Placement (Priority: P2)

A user places an item into a category via `place_item_in_category()`. If the
user calls `place_item_in_category()` again with the same item and category, the
operation silently succeeds — updating the `sort_index` if it changed, without
creating a duplicate link. This behavior already works at the repository level
but is now formally required.

**Why this priority**: The item-category upsert already works correctly in all
repository implementations. This user story formalizes the existing behavior as
a contractual requirement so it cannot regress.

**Independent Test**: Call `place_item_in_category()` twice with the same
`(item_id, category_id)` pair but different `sort_index` values. Verify that
only one link exists and its `sort_index` reflects the latest call.

**Acceptance Scenarios**:

1. **Given** an item I placed in category C with `sort_index=0`, **When**
   `place_item_in_category(I, C, sort_index=3)` is called again, **Then** only
   one `ItemParentLink(I, C)` exists and its `sort_index` is `3`.
2. **Given** an item I placed in category C, **When**
   `place_item_in_category(I, C)` is called again with the same `sort_index`,
   **Then** the operation succeeds silently with no error and no duplicate link.

---

### Edge Cases

- **Existing stores with duplicates**: Stores that already contain duplicate
  `(category_id, parent_category_id)` links from before this fix will continue
  to render those duplicates. No auto-deduplication on load and no migration
  command are provided. This is accepted technical debt.
- **Concurrent writes**: No additional concurrency guarantees are introduced.
  The existing atomic-write semantics of each repository implementation are
  unchanged.
- **DAG cycle detection**: The existing `check_no_cycle()` validation in
  `add_category_parent()` still runs before every upsert. For an existing link
  (same pair, different `sort_index`) the check passes harmlessly because the
  edge is already present in the adjacency list — no new edge is introduced.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `save_category_parent_link()` in every repository implementation
  MUST upsert by `(category_id, parent_category_id)`. If a link with the same
  pair already exists, its `sort_index` is updated in-place. No duplicate link
  is created.
- **FR-002**: `save_item_parent_link()` in every repository implementation MUST
  upsert by `(item_id, category_id)`. If a link with the same pair already
  exists, its `sort_index` is updated in-place. No duplicate link is created.
  *(Formalizes existing behavior.)*
- **FR-003**: The `TaxomeshRepositoryBase` protocol docstring for
  `save_category_parent_link()` MUST document the upsert semantics — matching
  the existing docstring pattern of `save_item_parent_link()`.
- **FR-004**: The service-level `add_category_parent()` method is documented as
  idempotent — calling it multiple times with the same `(category_id,
  parent_category_id)` pair produces the same result as calling it once.
- **FR-005**: The service-level `place_item_in_category()` method is documented
  as idempotent — calling it multiple times with the same `(item_id,
  category_id)` pair produces the same result as calling it once.
- **FR-006**: All repository implementations (JsonRepository, YAMLRepository,
  InMemoryRepository in tests) MUST enforce FR-001 and FR-002.
- **FR-007**: No migration, auto-deduplication on load, or CLI command is
  provided for existing stores with duplicate links. Prevention only.

## Assumptions

- Idempotent upsert (silently update `sort_index` on duplicate) is the correct
  behavior. Raising an error on duplicate was explicitly rejected.
- The existing item-category upsert pattern (`save_item_parent_link()`) is the
  correct reference implementation to follow for category-parent links.
- No auto-deduplication of existing data is needed — prevention of new
  duplicates is sufficient.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Calling `save_category_parent_link()` twice with the same
  `(category_id, parent_category_id)` pair results in exactly one stored link,
  across all repository implementations.
- **SC-002**: Calling `save_item_parent_link()` twice with the same
  `(item_id, category_id)` pair results in exactly one stored link, across all
  repository implementations. *(Regression guard for existing behavior.)*
- **SC-003**: The `TaxomeshRepositoryBase` protocol docstring for
  `save_category_parent_link()` documents upsert semantics.
- **SC-004**: `taxomesh graph` does not show duplicate children when a
  category-parent link is saved multiple times.
- **SC-005**: All existing tests continue to pass — no regressions.
