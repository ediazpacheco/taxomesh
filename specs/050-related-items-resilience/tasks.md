---

description: "Task list for 050-related-items-resilience"
---

# Tasks: Related Items Resilience — Warning Logging and Skip-on-Error

**Input**: Design documents from `/specs/050-related-items-resilience/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

---

## Phase 1: Foundational — Logger Setup

**Purpose**: Introduce the module-level logger in `service.py` so test and
implementation tasks can reference it. This is a one-line prerequisite that
both user stories depend on.

- [x] T001 Add `import logging` and `logger = logging.getLogger(__name__)` at
  module level in `taxomesh/application/service.py` (after existing import block).
  Verify `ruff` and `mypy --strict` still pass.

**Checkpoint**: `service.py` has a module-level `logger`; quality gates green.

---

## Phase 2: User Story 1 — Skip and Log on Dangling Link (Priority: P1) 🎯 MVP

**Goal**: `list_related_items_for_sources()` skips broken links and emits a
`WARNING` log by default; callers are never interrupted by a missing target.

**Independent Test**: Run `pytest tests/service/test_service_list_related_resilience.py`
after completing this phase; all P1 tests must pass.

### Tests for User Story 1 ⚠️ Write first — must FAIL before implementation

- [x] T002 [P] [US1] Create `tests/service/test_service_list_related_resilience.py`.
  Add test: single dangling link → no exception raised, result is `{}`,
  exactly one `WARNING` record captured by `caplog`, message contains
  `source_item_id`, `target_item_id`, and `relation_type`.
  Use `InMemoryRepository` from `tests/service/conftest.py` to inject the
  dangling link directly (bypass service creation path).
  Add test: empty `source_item_ids` → returns `{}` immediately, no `WARNING` emitted
  (guards the existing early-return path, EC-02).

- [x] T003 [P] [US1] Add test: mixed valid + dangling links for same source →
  valid target appears in result, dangling target absent, one `WARNING` emitted.
  Add test: `relation_types` filter that excludes the dangling link → no `WARNING`
  emitted (EC-04: filtered links never reach the missing-target check).

- [x] T004 [P] [US1] Add test: all links dangling for one source, valid links for
  another → dangling source absent from result dict, valid source present,
  `WARNING` count equals number of dangling links.

**Verify tests FAIL** before proceeding to implementation.

### Implementation for User Story 1

- [x] T005 [US1] Modify `list_related_items_for_sources()` in
  `taxomesh/application/service.py`:
  - Add `skip_on_error: bool = True` as a keyword-only parameter.
  - In the `for link in links:` loop, change the
    `if link.target_item_id not in item_map:` branch:
    - If `skip_on_error` is `True`: call `logger.warning(...)` with
      `source_item_id`, `target_item_id`, and `relation_type` from the link;
      then `continue`.
    - If `skip_on_error` is `False`: raise `TaxomeshItemNotFoundError`
      (existing message, unchanged).
  - Update the docstring: add `skip_on_error` to `Args:`, update `Raises:`
    to note the exception is only raised when `skip_on_error=False`.

- [x] T006 [US1] Run `pytest tests/service/test_service_list_related_resilience.py`
  — all T002–T004 tests must pass.

- [x] T007 [US1] Run story-level test gate:
  ```bash
  pytest tests/service/test_service_list_related_resilience.py
  ```
  All T002–T004 tests must pass. (Full gates run in Phase 4: T011, T012.)

**Checkpoint**: US1 fully functional and tested.

---

## Phase 3: User Story 2 — Strict Mode Preserved (Priority: P2)

**Goal**: Callers passing `skip_on_error=False` still receive
`TaxomeshItemNotFoundError` on dangling links (existing behaviour, unchanged).

**Independent Test**: Run targeted tests for `skip_on_error=False` — must raise.

### Tests for User Story 2 ⚠️ Write first — must FAIL before implementation

- [x] T008 [US2] In `tests/service/test_service_list_related_resilience.py`, add
  test: dangling link + `skip_on_error=False` → `TaxomeshItemNotFoundError` raised,
  no `WARNING` log emitted.

- [x] T009 [US2] Add test: valid links only + `skip_on_error=False` → normal result
  returned, no exception, no warning.

**Verify tests FAIL** before T005. T008 will fail because `skip_on_error` does not yet
exist on the method (calling it raises `TypeError`, which is not
`TaxomeshItemNotFoundError` — the TDD red step is satisfied). T009 should pass
immediately (valid-link happy path is unchanged). Confirm both before proceeding.

### Implementation for User Story 2

User Story 2 has no separate implementation step: the `skip_on_error=False` branch
is already wired in T005. These tests validate the existing path is preserved.

- [x] T010 [US2] Run `pytest tests/service/test_service_list_related_resilience.py`
  — all T008–T009 tests must pass.

**Checkpoint**: Strict mode confirmed preserved.

---

## Phase 4: Polish & Cross-Cutting

- [x] T011 [P] Run the full test suite and confirm no regressions:
  ```bash
  pytest --cov=taxomesh --cov-fail-under=80
  ```

- [x] T012 [P] Run `ruff check . && ruff format --check . && mypy --strict .`
  — all clean.

---

## Dependencies & Execution Order

- **T001** (logger): no dependencies — start immediately.
- **T002–T004** (US1 tests): depend on T001 (logger must exist for `caplog` assertions
  to reference the right logger name).
- **T005** (implementation): depends on T001; tests T002–T004 must FAIL first.
- **T006, T007** (validation): depend on T005.
- **T008–T009** (US2 tests): can be written in parallel with T005; confirmed passing
  after T005.
- **T010**: depends on T005.
- **T011, T012**: depend on all prior tasks.

### Parallel Opportunities

- T002, T003, T004 can be written in parallel (all in the same file, non-conflicting
  test functions).
- T008, T009 can be written while T005 is in progress.
- T011, T012 can run in parallel.

---

## Notes

- `InMemoryRepository` in `tests/service/conftest.py` supports direct injection of
  `ItemRelationLink` records via `_item_relation_links`. Use this to create dangling
  links without needing to create a target `Item`.
- Use `caplog` with `propagate=True` (default) and
  `caplog.set_level(logging.WARNING, logger="taxomesh.application.service")` to
  capture the specific logger.
- The `relation_type` in a warning message will already be lowercase-normalised
  (stored that way by `ItemRelationLink`).
