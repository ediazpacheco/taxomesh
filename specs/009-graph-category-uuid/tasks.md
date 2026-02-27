# Tasks: Graph Category UUID Display

**Input**: Design documents from `/specs/009-graph-category-uuid/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: TDD is mandatory per constitution (Principle VIII / CLAUDE.md). Tests are written first.

**Organization**: Single user story — tasks are sequential due to the minimal scope.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup needed — project structure and dependencies already exist.

*No tasks in this phase.*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational changes needed — `category_id` field already exists on
the `Category` model and is accessible via `CategoryNode.category.category_id`.

*No tasks in this phase.*

---

## Phase 3: User Story 1 - Category UUID in Graph Output (Priority: P1)

**Goal**: Display `category_id` (UUID) in dim style after each category name in `taxomesh graph` output.

**Independent Test**: Run `taxomesh graph` with at least one category; verify each category line includes its UUID.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T001 [US1] Write test `test_graph_shows_category_uuid` in tests/test_cli.py — create a category, run `taxomesh graph`, assert `str(cat.category_id)` appears in output. Follow existing pattern from `test_graph_shows_item_item_id()` (line 800).

### Implementation for User Story 1

- [x] T002 [US1] Modify `_add_graph_node()` in taxomesh/adapters/cli/main.py (line 428) — append `  [dim]{category_node.category.category_id}[/dim]` to the category branch label, matching the item UUID dim style.

**Checkpoint**: `taxomesh graph` shows category UUIDs. Run `pytest tests/test_cli.py -k test_graph` — all graph tests pass including the new one.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T003 Run full quality gates: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`
- [x] T004 Verify existing graph tests still pass (no regressions in item rendering)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 3 (US1)**: No prerequisites — existing code and models are sufficient.
- **Phase 4 (Polish)**: Depends on Phase 3 completion.

### Within User Story 1

- T001 (test) MUST be written and FAIL before T002 (implementation)
- T002 makes T001 pass

### Parallel Opportunities

- T001 and T002 are sequential (TDD: test first, then implement)
- T003 and T004 can run in parallel (different tool invocations)

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Write failing test (T001)
2. Implement the one-line change (T002)
3. Run quality gates (T003, T004)
4. Done — single user story, single increment

---

## Notes

- This is a minimal feature: 1 line changed, 1 test added
- No new files, no new dependencies, no model changes
- The change mirrors the existing item UUID display pattern exactly
