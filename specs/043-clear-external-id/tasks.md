# Tasks: External ID Clear Support

**Input**: Design documents from `/specs/043-clear-external-id/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/service-api.md ✅

**Tests**: Included — spec explicitly requires TDD with 8+ named test scenarios.

**Organization**: Tasks grouped by user story. All implementation is a single focused change to
`taxomesh/application/service.py`; tests are written before the implementation (TDD).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup

No project structure changes required. The sentinel class and constant are added directly to the
existing `service.py`. No new modules, no new dependencies.

*(Phase 1 is intentionally empty — no setup tasks needed.)*

---

## Phase 2: Foundational — Failing Tests (TDD Prerequisite)

**Purpose**: Write ALL test scenarios before any implementation. Every test MUST fail (red) when run
against the unmodified codebase. This is a hard prerequisite for Phases 3–5.

**⚠️ CRITICAL**: Do not write a single line of implementation code until T002 is verified.

- [ ] T001 Create `tests/service/test_service_external_id_clear.py` with all 10 test stubs covering US1 (6 cases), US2 (2 cases), US3 (2 cases). Use the parametrized `service` fixture from `tests/service/conftest.py`. Test functions: `test_update_item_clear_sets_none`, `test_update_item_clear_lookup_returns_none`, `test_update_item_reassign_after_clear`, `test_update_category_clear_sets_none`, `test_update_category_clear_lookup_returns_none`, `test_update_category_reassign_after_clear`, `test_update_item_omit_external_id_unchanged`, `test_update_category_omit_external_id_unchanged`, `test_update_item_set_external_id`, `test_update_category_set_external_id`
- [ ] T002 Run `pytest tests/service/test_service_external_id_clear.py -v` and confirm that the US1 clear tests (T001 group 1) FAIL — specifically `test_update_item_clear_sets_none` and `test_update_category_clear_sets_none` must fail with `AssertionError` (field not cleared). US2 and US3 tests may pass already (existing behaviour).

**Checkpoint**: T001 test file committed; T002 output confirms red state for US1. Ready for implementation.

---

## Phase 3: User Story 1 — Clear external_id to None (Priority: P1) 🎯 MVP

**Goal**: `update_item(..., external_id=None)` and `update_category(..., external_id=None)` explicitly
clear the `external_id` field, making the old value available for reassignment to another record.

**Independent Test**: `pytest tests/service/test_service_external_id_clear.py -k "clear or reassign" -v`
All 6 scenarios (clear, lookup-after-clear, reassignment × items + categories) must pass across all backends.

### Tests for User Story 1

> **Tests were written in Phase 2 (T001). The 6 US1 test functions are:**
> - `test_update_item_clear_sets_none` — update_item with external_id=None clears the field
> - `test_update_item_clear_lookup_returns_none` — lookup by old value returns None after clear
> - `test_update_item_reassign_after_clear` — reassignment succeeds without conflict
> - `test_update_category_clear_sets_none` — same for category
> - `test_update_category_clear_lookup_returns_none` — same for category
> - `test_update_category_reassign_after_clear` — same for category

### Implementation for User Story 1

- [ ] T003 [US1] Add private `_UnsetType` singleton class to `taxomesh/application/service.py` immediately after the module-level imports. Class must have a Google-style docstring. No exported name.
- [ ] T004 [US1] Add `_UNSET: Final[_UnsetType] = _UnsetType()` named constant to `taxomesh/application/service.py` immediately after the `_UnsetType` class definition. Must use `Final` annotation per Principle X.
- [ ] T005 [US1] Update `update_item` signature in `taxomesh/application/service.py`: change `external_id: str | None = None` to `external_id: str | None | _UnsetType = _UNSET`. Change guard from `if external_id is not None:` to `if not isinstance(external_id, _UnsetType):`. Update the `external_id` docstring arg to: "Omit to leave unchanged. Pass None to clear. Pass a string to set a new value."
- [ ] T006 [US1] Update `update_category` signature in `taxomesh/application/service.py`: same changes as T005 applied to `update_category`. Ensure existing `TaxomeshRootCategoryError` guard is untouched.
- [ ] T007 [US1] Run `pytest tests/service/test_service_external_id_clear.py -k "clear or reassign" -v` and confirm all 6 US1 tests pass across all backends (in_memory, json, yaml, django).

**Checkpoint**: US1 fully functional. `external_id=None` now clears the field. Reassignment flow unblocked.

---

## Phase 4: User Story 2 — No-op when external_id omitted (Priority: P2)

**Goal**: Calling `update_item` or `update_category` without passing `external_id` leaves the
existing field value unchanged (the sentinel default ensures this automatically).

**Independent Test**: `pytest tests/service/test_service_external_id_clear.py -k "omit" -v`
Both no-op tests must pass.

### Tests for User Story 2

> **Tests were written in Phase 2 (T001). The 2 US2 test functions are:**
> - `test_update_item_omit_external_id_unchanged`
> - `test_update_category_omit_external_id_unchanged`

### Verification for User Story 2

- [ ] T008 [US2] Run `pytest tests/service/test_service_external_id_clear.py -k "omit" -v` and confirm both no-op tests pass across all backends. No implementation change needed — the `_UNSET` sentinel default added in T003–T006 already provides this behaviour.

**Checkpoint**: US2 verified. Existing callers that omit `external_id` are unaffected.

---

## Phase 5: User Story 3 — Assign a new external_id string (Priority: P3)

**Goal**: `update_item(..., external_id="some-string")` and `update_category(..., external_id="some-string")`
continue to set the field to the given string — regression protection for pre-existing behaviour.

**Independent Test**: `pytest tests/service/test_service_external_id_clear.py -k "set_external" -v`
Both regression tests must pass.

### Tests for User Story 3

> **Tests were written in Phase 2 (T001). The 2 US3 test functions are:**
> - `test_update_item_set_external_id`
> - `test_update_category_set_external_id`

### Verification for User Story 3

- [ ] T009 [US3] Run `pytest tests/service/test_service_external_id_clear.py -k "set_external" -v` and confirm both regression tests pass across all backends. No implementation change needed — string assignment was never broken.

**Checkpoint**: US3 verified. All three `external_id` intent states work correctly.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate — no exceptions. All items must pass before opening a PR.

- [ ] T010 [P] Run `ruff check taxomesh/application/service.py tests/service/test_service_external_id_clear.py` and fix any lint errors
- [ ] T011 [P] Run `ruff format --check taxomesh/application/service.py tests/service/test_service_external_id_clear.py` and fix any formatting issues
- [ ] T012 Run `mypy --strict taxomesh/application/service.py` and confirm zero type errors (the `_UnsetType` guard must narrow correctly)
- [ ] T013 Run `pytest --cov=taxomesh --cov-fail-under=80` (full suite) and confirm ≥ 80% coverage and no regressions
- [ ] T014 Run `/speckit.analyze` and confirm zero deviations before proposing a PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **User Story 1 (Phase 3)**: Depends on Phase 2 (T001 + T002 must be done)
- **User Stories 2 & 3 (Phases 4–5)**: Depend on Phase 3 completion (T003–T006 implement the code)
- **Polish (Phase 6)**: Depends on all stories complete (T007–T009 green)

### User Story Dependencies

```
Phase 2 (tests written, failing)
    └── Phase 3 US1 (implement sentinel, verify clear tests)
            ├── Phase 4 US2 (verify no-op tests — no new code)
            ├── Phase 5 US3 (verify regression tests — no new code)
            └── Phase 6 (quality gate)
```

### Within Each Story

- Tests MUST be written (T001) and confirmed failing (T002) before any implementation
- Sentinel class (T003) before constant (T004) before method changes (T005, T006)
- T005 and T006 are independent (different methods) — can be done in either order
- Verification (T007–T009) before polish (T010–T014)

### Parallel Opportunities

- T003 and T004 must be sequential (T004 uses `_UnsetType` from T003)
- T005 and T006 [P] — `update_item` and `update_category` are in the same file but independent edits; can be done concurrently by separate agents
- T010 and T011 [P] — lint and format checks are independent
- T008 and T009 [P] — US2 and US3 verification runs are independent

---

## Parallel Example: Phase 3 Implementation

```bash
# T003 + T004 must be done first (sequential)
Task: "Add _UnsetType class to taxomesh/application/service.py"
Task: "Add _UNSET Final constant to taxomesh/application/service.py"

# Then T005 and T006 can run in parallel (different method bodies):
Task: "[P] Update update_item in taxomesh/application/service.py"
Task: "[P] Update update_category in taxomesh/application/service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Write all tests, confirm US1 tests fail
2. Complete Phase 3: Implement sentinel, verify US1 tests green
3. **STOP and VALIDATE**: `pytest -k "clear or reassign"` passes on all backends
4. The reassignment flow is unblocked — this alone delivers full business value

### Incremental Delivery

1. Phase 2 → tests committed (red)
2. Phase 3 → sentinel committed (US1 green) → MVP delivered
3. Phase 4 → US2 verified (no regressions)
4. Phase 5 → US3 verified (regression protection confirmed)
5. Phase 6 → quality gate clean → PR ready

---

## Notes

- `_UnsetType` and `_UNSET` are private (`_` prefix) — the class name is never exported or exposed in public docs; the three-state semantics they enable ARE documented in the public method docstrings per FR-010
- The parametrized `service` fixture runs each test 4× (in_memory, json, yaml, django) — total test executions: 10 scenarios × 4 backends = 40 runs
- US2 and US3 tests may already pass before implementation (they exercise non-broken paths); this is expected and not a problem
- The InMemoryRepository does not enforce `external_id` uniqueness — the reassignment test (US1 scenario 3) is most meaningful with json/yaml/django backends
- Commit order suggestion: T001+T002 in one commit, T003–T006 in one commit, T007–T009 verification, T010–T013 quality fixes if any
