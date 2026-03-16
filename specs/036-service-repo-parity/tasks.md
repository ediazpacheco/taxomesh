# Tasks: Service-Repository Behavioral Parity

**Input**: Design documents from `/specs/036-service-repo-parity/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**TDD**: Test tasks precede every implementation task (CLAUDE.md mandate).

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Baseline Verification)

**Purpose**: Confirm the current test suite is green before making any changes.
A clean baseline is required so regressions introduced by the fixture change are
immediately visible.

- [x] T001 Run `pytest tests/service/ -v --tb=short` and confirm all tests pass with zero failures. Record the current test count as the pre-parity baseline.

**Checkpoint**: All existing service tests pass. Safe to proceed.

---

## Phase 2: User Story 1 — File-Based Repository Parity (Priority: P1) 🎯 MVP

**Goal**: Replace the single-backend `service` fixture with a parametrized version
covering `InMemoryRepository`, `JsonRepository`, and `YAMLRepository`. All existing
behavioral tests automatically run 3× — once per backend — with zero changes to test
functions.

**Independent Test**: `pytest tests/service/test_service_categories.py -v` shows
three instances per test: `[in_memory]`, `[json]`, `[yaml]`. All pass.

### TDD — Write pre-flight checks first ⚠️

> **Write T002 BEFORE T003. T002 must exist before any fixture change is made.**

- [x] T002 [US1] Write `tests/service/test_parity_fixture.py` with two pre-flight smoke tests:
  - `test_json_backend_parity_smoke(tmp_path)`: creates `TaxomeshService(JsonRepository(tmp_path / "t.json"))`, calls `create_category("Smoke", slug="smoke")`, asserts `get_category(cat.category_id).name == "Smoke"` and `get_category_by_slug("smoke").name == "Smoke"`.
  - `test_yaml_backend_parity_smoke(tmp_path)`: same for `YAMLRepository(tmp_path / "t.yaml")`.
  Run `pytest tests/service/test_parity_fixture.py -v` — both tests must PASS before proceeding to T003. If either fails, a backend has a bug that must be fixed first.

### Implementation for User Story 1

- [x] T003 [US1] Update `tests/service/conftest.py` — replace the single-backend `service` fixture with a parametrized version:
  - Add `params=["in_memory", "json", "yaml"]` and `ids=["in_memory", "json", "yaml"]` to `@pytest.fixture`
  - Add `request: pytest.FixtureRequest` and `tmp_path: Path` as fixture parameters
  - Dispatch on `request.param`: `"in_memory"` → `InMemoryRepository()`, `"json"` → `JsonRepository(tmp_path / "test.json")`, `"yaml"` → `YAMLRepository(tmp_path / "test.yaml")`
  - Add `from taxomesh.adapters.repositories.json_repository import JsonRepository` and `from taxomesh.adapters.repositories.yaml_repository import YAMLRepository` imports at the top of `conftest.py`
  - Add `import pytest` if not already imported at module level (check first)
  - Keep `InMemoryRepository` class definition and `tmp_json_path` fixture unchanged

### Verification for User Story 1

- [x] T004 [US1] Run `pytest tests/service/test_service_categories.py tests/service/test_service_items.py tests/service/test_service_tags.py tests/service/test_service_graph.py tests/service/test_service_slug.py tests/service/test_service_item_relations.py tests/service/test_service_reorder_reparent.py tests/service/test_service_search.py -v --tb=short` and verify:
  - Each test appears 3× in output (`[in_memory]`, `[json]`, `[yaml]`)
  - All instances pass

- [x] T005 [US1] Run `pytest tests/service/ -v --tb=short` and verify:
  - Tests NOT using the `service` fixture (`test_service_config.py`, `test_service_cache.py`, `test_custom_backend.py`, `test_category_parent_upsert.py`, `test_item_parent_upsert.py`, `test_json_repository*.py`, `test_yaml_repository*.py`) are unaffected (no `[in_memory]`/`[json]`/`[yaml]` suffix on their output)
  - All tests pass

**Checkpoint**: User Story 1 complete. Every behavioral test runs against 3 backends.

---

## Phase 3: User Story 2 — Django Repository Parity (Priority: P2)

**Goal**: Extend the parametrized `service` fixture with an optional fourth backend
(`DjangoRepository`). Tests using the `django` parameter skip automatically when
Django is not installed; pass when the Django test environment is configured.

**Independent Test**: In the Django-enabled environment, `pytest tests/service/test_service_categories.py -v -k django` shows one instance per test (`[django]`), all passing. In a non-Django environment, the same command shows all instances marked as SKIPPED with reason `"django not installed"`.

### TDD — Write pre-flight check first ⚠️

> **Write T006 BEFORE T007.**

- [x] T006 [US2] Add a third smoke test to `tests/service/test_parity_fixture.py`:
  - `test_django_backend_parity_smoke(db)`: calls `pytest.importorskip("django")`, then creates `TaxomeshService(DjangoRepository())`, calls `create_category("Smoke")`, asserts `get_category_by_slug("smoke").name == "Smoke"`. Decorate with `@pytest.mark.django_db`.
  Run `pytest tests/service/test_parity_fixture.py::test_django_backend_parity_smoke -v` — must PASS (Django env) or SKIP (non-Django). Must not ERROR.

### Implementation for User Story 2

- [x] T007 [US2] Update `tests/service/conftest.py` — extend `service` fixture to include the `django` parameter:
  - Add `"django"` to the `params` list and `ids` list
  - Add an `elif request.param == "django":` branch:
    - Call `pytest.importorskip("django", reason="django not installed")`
    - Call `request.getfixturevalue("db")` to activate pytest-django transaction setup
    - Import and return `TaxomeshService(repository=DjangoRepository())`
    - Import `DjangoRepository` inside the branch: `from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415`

### Verification for User Story 2

- [x] T008 [US2] In the Django-enabled test environment, run `pytest tests/service/test_service_categories.py -v -k django --tb=short` and verify `[django]` instances are collected and pass.

- [x] T009 [US2] In a non-Django environment (or by temporarily removing `django` from installed packages), run `pytest tests/service/test_service_categories.py -v -k django` and verify all `[django]` instances are SKIPPED (not FAILED, not ERRORED).

**Checkpoint**: User Stories 1 and 2 complete. All four backends covered.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, documentation alignment.

- [x] T010 [P] Run `ruff check . && ruff format --check .` — fix any lint or formatting issues in `tests/service/conftest.py` and `tests/service/test_parity_fixture.py`

- [x] T011 [P] Run `mypy --strict .` — resolve any type errors in modified files (expected: `pytest.FixtureRequest` annotation on the `service` fixture parameter)

- [x] T012 Run `pytest --cov=taxomesh --cov-fail-under=80` — confirm coverage is at or above 80%. The parity suite adds test runs but no new production code, so coverage should only improve or stay the same.

- [x] T013 Verify SC-001: Count the total test instances reported for `tests/service/test_service_categories.py` — must be exactly `37 × 3 = 111` (or the current count × 3). Adjust expected count if the test file has changed since spec was written.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (US1)**: Depends on Phase 1 (baseline must be green).
- **Phase 3 (US2)**: Depends on Phase 2 (parametrized fixture must exist before extending it).
- **Phase 4 (Polish)**: Depends on Phase 2 complete; Phase 3 optional (can polish after US1 alone).

### Task Dependencies Within Each Phase

```
T001 → T002 → T003 → T004 → T005
                             ↓
              T006 → T007 → T008 → T009
                                     ↓
                         T010 [P] ─┬─ T012 → T013
                         T011 [P] ─┘
```

### Parallel Opportunities

- T010 and T011 (lint + mypy) can run in parallel after T009.
- T004 and T005 can be run in parallel (different test file subsets).

---

## Parallel Execution Examples

### User Story 1 verification (after T003)

```bash
# Run category + item tests in parallel sessions:
pytest tests/service/test_service_categories.py tests/service/test_service_items.py -v &
pytest tests/service/test_service_graph.py tests/service/test_service_slug.py -v &
wait
```

### Polish phase (after US1 complete)

```bash
ruff check . &
mypy --strict . &
wait
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. T001 — baseline check
2. T002 — pre-flight smoke tests
3. T003 — update `conftest.py` (single edit)
4. T004, T005 — verify parity
5. T010, T011, T012 — quality gates
6. **STOP and VALIDATE** — behavioral tests run 3× each, all pass

### Full Delivery

Complete MVP, then add:
7. T006 — Django pre-flight
8. T007 — extend fixture
9. T008, T009 — verify Django behavior
10. T013 — final count check

---

## Notes

- The only production-affecting file modified is `tests/service/conftest.py`.
- All behavioral test files (`test_service_*.py`) are read-only — they require zero changes.
- If T002 or T006 smoke tests fail, stop and fix the underlying repository bug before proceeding. Do not paper over failures by skipping them.
- `tmp_json_path` fixture in `conftest.py` remains unchanged — it is used by `test_json_repository.py` which is outside parity scope.
- `InMemoryRepository` class stays in `conftest.py` — do not move it (imported by `test_custom_backend.py` and `test_category_parent_upsert.py`).
