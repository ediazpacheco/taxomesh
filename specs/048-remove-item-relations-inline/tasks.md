# Tasks: Remove Redundant Item Relation Link Models Inline

**Input**: Design documents from `/specs/048-remove-item-relations-inline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**Tests**: TDD is mandatory per project constitution. Test tasks run before implementation tasks.

**Organization**: Single user story — all tasks belong to US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

---

## Phase 3: User Story 1 - Clean Item Change Page (Priority: P1) 🎯 MVP

**Goal**: Remove the read-only "Item relation link models" inline from the item change page, eliminating visual redundancy without loss of data or functionality.

**Independent Test**: Navigate to any item change page (or run `pytest tests/contrib/django/test_admin_relations.py`) — no incoming-relation section appears; "Items related with" section is still present and functional.

### Tests for User Story 1 (TDD — write and verify FAIL before Step T002)

- [x] T001 [US1] Update `test_incoming_inline_registered_on_item_admin` → rename to `test_incoming_inline_not_registered_on_item_admin` and invert assertion: verify no inline in `ItemModelAdmin.get_inline_instances()` targets `ItemRelationLinkModel` via `fk_name == "target_item"` in `tests/contrib/django/test_admin_relations.py`
- [x] T002 [US1] Delete `test_incoming_inline_is_read_only` from `tests/contrib/django/test_admin_relations.py`

> **Verify T001 FAILS** before proceeding: `pytest tests/contrib/django/test_admin_relations.py::TestOutgoingRelationInline::test_incoming_inline_not_registered_on_item_admin` must fail (IncomingRelationInline is still registered).

### Implementation for User Story 1

- [x] T003 [US1] Delete the `IncomingRelationInline` class from `taxomesh/contrib/django/admin.py` (lines ~1391–1397)
- [x] T004 [US1] Remove `IncomingRelationInline` from `ItemModelAdmin.inlines` list in `taxomesh/contrib/django/admin.py` (line ~1413)

**Checkpoint**: Run `pytest tests/contrib/django/test_admin_relations.py` — all tests must pass.

---

## Phase N: Polish & Cross-Cutting Concerns

- [x] T005 Run full quality gates: `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80`

---

## Dependencies & Execution Order

### Phase Dependencies

- **US1 tests (T001, T002)**: No dependencies — write first; T001 must FAIL before T003/T004
- **US1 implementation (T003, T004)**: Depends on T001 and T002 being written
- **Polish (T005)**: Depends on all US1 tasks complete

### User Story Dependencies

- **User Story 1 (P1)**: Standalone — no external dependencies

### Within User Story 1

1. T001 — write failing test (must observe failure)
2. T002 — delete obsolete test
3. T003 — delete `IncomingRelationInline` class
4. T004 — remove from `inlines` list
5. T005 — quality gates

### Parallel Opportunities

T003 and T004 are in the same file (`admin.py`) and are logically sequential — do not parallelize.
T001 and T002 are in the same file — do not parallelize.

---

## Implementation Strategy

### MVP (only story — complete in one pass)

1. Write T001 (failing test)
2. Delete T002 (obsolete test)
3. Implement T003 + T004
4. Verify T001 now passes
5. Run T005 (quality gates)

---

## Notes

- No setup or foundational phase needed — this is a pure deletion in two files
- No data migration, no model changes, no service changes
- The only risk is forgetting to verify T001 fails *before* implementing T003/T004 — TDD requires observing the red state
