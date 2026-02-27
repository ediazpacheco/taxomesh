# Tasks: Unique Parent Link Constraint

**Input**: Design documents from `/specs/010-unique-parent-links/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-protocol.md

**Tests**: TDD is mandatory per project constitution. Every implementation task has a corresponding test task.

**Organization**: Tasks are grouped by user story (US1: category-parent upsert, US2: item-category upsert formalization).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup needed — this feature modifies existing files only.

*No tasks — project infrastructure already exists.*

---

## Phase 2: Foundational (Protocol Docstring)

**Purpose**: Update the repository protocol contract before implementing upsert logic.

- [x] T001 Update `save_category_parent_link()` docstring in `taxomesh/ports/repository.py` to document upsert semantics matching `save_item_parent_link()` (FR-003)

**Checkpoint**: Protocol contract documented — implementation can begin.

---

## Phase 3: User Story 1 — Idempotent Category-Parent Assignment (Priority: P1) 🎯 MVP

**Goal**: `save_category_parent_link()` upserts by `(category_id, parent_category_id)` — no duplicate links created on repeated calls.

**Independent Test**: Call `save_category_parent_link()` twice with the same `(category_id, parent_category_id)` and different `sort_index`. Verify only one link exists with the latest `sort_index`.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T002 [P] [US1] Write test for category-parent upsert on InMemoryRepository — call `save_category_parent_link()` twice with same pair, assert single link with updated `sort_index` in `tests/service/test_category_parent_upsert.py`
- [x] T003 [P] [US1] Write test for category-parent upsert on JsonRepository — call `save_category_parent_link()` twice with same pair, assert single link with updated `sort_index` in `tests/service/test_json_repository.py`
- [x] T004 [P] [US1] Write test for category-parent upsert on YAMLRepository — call `save_category_parent_link()` twice with same pair, assert single link with updated `sort_index` in `tests/service/test_yaml_repository.py`
- [x] T005 [P] [US1] Write test for service-level `add_category_parent()` idempotency — call twice with same `(category_id, parent_id)`, assert single link in `tests/service/test_category_parent_upsert.py`
- [x] T006 [P] [US1] Write test that distinct `(category_id, parent_category_id)` pairs are NOT affected by upsert — save links `(C, P1)` and `(C, P2)`, upsert `(C, P1)`, assert `(C, P2)` unchanged in `tests/service/test_category_parent_upsert.py`

### Implementation for User Story 1

- [x] T007 [P] [US1] Add upsert logic to `save_category_parent_link()` in `taxomesh/adapters/repositories/json_repository.py` — scan for existing `(category_id, parent_category_id)` match, replace in-place if found, else append (FR-001)
- [x] T008 [P] [US1] Add upsert logic to `save_category_parent_link()` in `taxomesh/adapters/repositories/yaml_repository.py` — same pattern as JsonRepository (FR-001)
- [x] T009 [P] [US1] Add upsert logic to `save_category_parent_link()` in `tests/service/conftest.py` (InMemoryRepository) — same pattern, no `_flush()` call (FR-001, FR-006)
- [x] T010 [US1] Update `add_category_parent()` docstring in `taxomesh/application/service.py` to document idempotent behavior (FR-004)
- [x] T011 [US1] Run all US1 tests and verify they pass

**Checkpoint**: Category-parent upsert works across all repositories. `taxomesh graph` no longer shows duplicates from repeated `add_category_parent()` calls.

---

## Phase 4: User Story 2 — Idempotent Item-Category Placement (Priority: P2)

**Goal**: Formalize existing `save_item_parent_link()` upsert as a contractual requirement with regression tests.

**Independent Test**: Call `save_item_parent_link()` twice with the same `(item_id, category_id)` and different `sort_index`. Verify only one link exists with the latest `sort_index`.

### Tests for User Story 2 ⚠️

> **NOTE: These tests should PASS immediately (existing behavior), serving as regression guards**

- [x] T012 [P] [US2] Write regression test for item-category upsert on InMemoryRepository in `tests/service/test_item_parent_upsert.py`
- [x] T013 [P] [US2] Write regression test for item-category upsert on JsonRepository in `tests/service/test_json_repository.py`
- [x] T014 [P] [US2] Write regression test for item-category upsert on YAMLRepository in `tests/service/test_yaml_repository.py`

### Implementation for User Story 2

- [x] T015 [US2] Update `place_item_in_category()` docstring in `taxomesh/application/service.py` to document idempotent behavior (FR-005)
- [x] T016 [US2] Run all US2 tests and verify they pass

**Checkpoint**: Item-category upsert formalized with regression tests. No code changes needed — only docstring and tests.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and full test suite validation.

- [x] T017 Run full quality gate suite: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`
- [x] T018 Verify `taxomesh graph` output shows no duplicate categories after repeated `add_category_parent()` calls (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: N/A — no setup tasks.
- **Phase 2 (Foundational)**: T001 — protocol docstring. Blocks nothing but should be done first for consistency.
- **Phase 3 (US1)**: Tests T002–T006 first (TDD), then implementations T007–T010 in parallel, then T011 validation.
- **Phase 4 (US2)**: Independent of US1. Tests T012–T014, then T015 docstring, then T016 validation.
- **Phase 5 (Polish)**: Depends on all user stories complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after T001 (protocol docstring). No dependency on US2.
- **User Story 2 (P2)**: Can start after T001. No dependency on US1. Tests should pass immediately (existing behavior).

### Parallel Opportunities

- T002, T003, T004, T005, T006 can all run in parallel (different test files)
- T007, T008, T009 can all run in parallel (different source files)
- T012, T013, T014 can all run in parallel (different test files)
- US1 and US2 can run in parallel (independent stories)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together (TDD — write failing tests):
Task: "Test category-parent upsert on InMemoryRepository"
Task: "Test category-parent upsert on JsonRepository"
Task: "Test category-parent upsert on YAMLRepository"
Task: "Test service-level idempotency"
Task: "Test distinct pairs unaffected"

# Launch all implementations for US1 together:
Task: "Upsert logic in json_repository.py"
Task: "Upsert logic in yaml_repository.py"
Task: "Upsert logic in InMemoryRepository conftest.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete T001 (protocol docstring)
2. Write failing tests T002–T006
3. Implement T007–T009 (upsert in all repos)
4. Update docstring T010
5. **STOP and VALIDATE**: Run T011 — all US1 tests pass
6. Category-parent duplicate bug is fixed

### Incremental Delivery

1. T001 → Protocol contract updated
2. US1 (T002–T011) → Category-parent upsert works → Bug fixed (MVP!)
3. US2 (T012–T016) → Item-category upsert formalized with regression tests
4. T017–T018 → Full quality gates pass

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD is mandatory: write failing tests before implementation
- US2 tests are regression guards — they should pass immediately against existing code
- No domain model changes — only repository method bodies + docstrings
