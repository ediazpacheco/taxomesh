# Tasks: Atomic Multi-Write Service Operations

**Input**: Design documents from `/specs/058-atomic-operations/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository-atomic.md

**Tests**: INCLUDED — TDD is mandatory per the constitution (Principle VIII) and the spec's Testing section. Every implementation task is preceded by a failing test task.

**Organization**: Tasks are grouped by user story. Foundational tasks (the `atomic()` port method + adapter no-ops + test-double compliance) are shared prerequisites and block all stories.

## Path Conventions

Single-library hexagonal layout at repo root: `taxomesh/` (source), `tests/` (pytest).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Ensure the environment can run all backends, including the Django rollback tests.

- [X] T001 Confirm the dev environment is the django-capable venv (`uv sync --extra dev --extra django --python 3.12`) so `pytest-django` and the Django adapter are importable for the rollback tests; do NOT use a Python 3.14 venv (breaks mypy on Django files).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the `atomic()` capability to the port and every backend, and make all test doubles compliant. Until this is done the five operations cannot be wrapped and any test double passed to `TaxomeshService` would raise `AttributeError`.

**⚠️ CRITICAL**: No user story can be completed before this phase is done.

- [X] T002 [P] Write failing contract test in `tests/service/test_atomic_contract.py`: parametrized over the existing backend fixtures (in_memory, json, yaml, django), assert `repo.atomic()` is usable as a `with` block, yields `None`, and that a single write performed inside the block persists on the success path. (Initially fails with `AttributeError`.)
- [X] T003 Add `def atomic(self) -> AbstractContextManager[None]: ...` to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py`, importing `AbstractContextManager` from `contextlib`; Google-style docstring MUST document the two-tier guarantee (full rollback on transactional backends; best-effort no-op on file/in-memory) per FR-008.
- [X] T004 [P] Implement `atomic()` in `taxomesh/adapters/repositories/json_repository.py` returning `contextlib.nullcontext()`; docstring states the best-effort (no-op) limitation.
- [X] T005 [P] Implement `atomic()` in `taxomesh/adapters/repositories/yaml_repository.py` returning `contextlib.nullcontext()`; docstring states the best-effort (no-op) limitation.
- [X] T006 [P] Implement `atomic()` in `taxomesh/adapters/repositories/django_repository.py` returning `transaction.atomic(using=self._using)` (deferred Django import inside the method, `# noqa: PLC0415`; localized `# type: ignore` only if mypy flags the untyped return); docstring states it is a full-rollback boundary and that inner per-method blocks nest as savepoints.
- [X] T007 [P] Add `atomic()` (returning `contextlib.nullcontext()`) to `InMemoryRepository` in `tests/service/conftest.py`.
- [X] T008 Audit every other in-test repository double passed to `TaxomeshService` that can reach one of the five operations (`tests/contrib/conftest.py`, `tests/service/test_custom_backend.py`, `tests/adapters/cli/*`, `tests/test_cli.py`, `tests/test_logging.py`) and add `atomic()` → `nullcontext()` where missing; run `grep -rn "TaxomeshService(" tests/` to enumerate.
- [X] T009 Run `pytest tests/service/test_atomic_contract.py` (now green) and the full suite to confirm no `AttributeError` regressions from the new port method.

**Checkpoint**: Every backend and test double exposes a working `atomic()`. Foundation ready.

---

## Phase 3: User Story 1 — No orphaned data when a multi-write operation fails midway (Priority: P1) 🎯 MVP

**Goal**: On a transactional backend, a mid-operation write failure rolls back the whole operation — no orphaned category, no half-applied reorder/reparent — and raw backend errors surface as `TaxomeshRepositoryError` (chained), never as raw types.

**Independent Test**: Force the Nth write of each affected operation to raise on the Django backend; assert the datastore equals its pre-operation snapshot and the caller receives a `TaxomeshError`.

### Tests for User Story 1 (write first — MUST fail before implementation)

- [X] T010 [P] [US1] In `tests/service/test_atomic_operations.py`, add a failure-injection repository double that wraps a real backend and delegates `atomic()` to the wrapped repo. It must be configurable to raise an **arbitrary exception instance** (a raw `RuntimeError` **or** a `TaxomeshError` subclass) on the **Nth** call to a targeted write method (`save_category_parent_link`, `save_item_parent_link`, `delete_*`), so tests can fail *after* an earlier write has already been performed — exercising Django savepoint nesting (FR-005).
- [X] T011 [P] [US1] Failing test: `create_category` on Django — inject failure on `save_category_parent_link`; assert the category is NOT persisted (`get_category` → None / not in `list_categories`), no parent link exists, and `TaxomeshRepositoryError` is raised (not a raw `RuntimeError`), with the `RuntimeError` as `__cause__`.
- [X] T012 [P] [US1] Failing test: `reparent_category` on Django (loop + delete) — inject failure on the Nth `save_category_parent_link` after the `delete_category_parent_link`; assert the original parent link and original ordering are fully restored and a `TaxomeshError` is raised.
- [X] T013 [P] [US1] Failing test: `reparent_item` on Django (loop + delete) — inject failure mid-loop; assert the original placement/ordering is fully restored.
- [X] T014 [P] [US1] Failing test: `reorder_subcategories` on Django — inject failure on the Nth `save_category_parent_link`; assert none of the sort_index changes survive.
- [X] T015 [P] [US1] Failing test: `reorder_items_in_category` on Django — inject failure on the Nth `save_item_parent_link`; assert none of the sort_index changes survive.
- [X] T016 [P] [US1] Failing tests for the "must NOT be wrapped" contract (FR-011 + FR-003 + FR-005), covering three exception classes:
  - (a) **Mid-write `TaxomeshError`, on Django**: configure the double so an *earlier* write in `create_category` or `reparent_category` succeeds and a *later* write raises a `TaxomeshError` (e.g. `TaxomeshExternalIdConflictError`). Assert the exact type propagates unchanged (NOT re-wrapped) **and** the datastore is fully rolled back — the earlier committed write is undone (validates savepoint nesting, FR-005 + FR-003).
  - (b) **Pre-write builtin `ValueError`** (`reorder_subcategories`/`reorder_items_in_category`): assert it propagates as `ValueError` and is NOT converted to `TaxomeshRepositoryError` (validates the C1 writes-only scope).
  - (c) **Pre-write `pydantic.ValidationError`** (`create_category` with an over-length name): assert it propagates as `ValidationError`, unwrapped, and that no partial write occurred.

### Implementation for User Story 1

**Scoping rule (finding C1)**: the `with self._repo.atomic():` block and its `try/except` enclose the **write sequence ONLY**. All pre-write validation, existence checks, reads, and `pydantic` model construction stay OUTSIDE the boundary; `clear_all_caches()`/corpus reset/`return` stay AFTER the `with` on the success path. Wrapper shape:

```text
<pre-write validation / reads / construction>   # OUTSIDE — unchanged
try:
    with self._repo.atomic():
        <mutations only>
except TaxomeshError:
    raise
except Exception as exc:
    raise TaxomeshRepositoryError(str(exc)) from exc
<clear_all_caches() / corpus reset / return>     # OUTSIDE — success path
```

- [X] T017 [US1] In `create_category` (`taxomesh/application/service.py`), wrap ONLY `save_category` → `save_category_parent_link` in the boundary. Keep the root-name check, slug check, `Category(...)` construction, and `datetime.now` OUTSIDE — the documented `Raises: pydantic.ValidationError` / `TaxomeshDuplicateSlugError` must be preserved.
- [X] T018 [US1] In `reorder_subcategories` (`taxomesh/application/service.py`), wrap ONLY the `save_category_parent_link` loop. Keep the parent existence check and the `ValueError` "not a child" validation loop OUTSIDE — the builtin `ValueError` must propagate unchanged.
- [X] T019 [US1] In `reorder_items_in_category` (`taxomesh/application/service.py`), wrap ONLY the `save_item_parent_link` loop. Keep the category existence check and the `ValueError` "not placed in category" validation loop OUTSIDE.
- [X] T020 [US1] In `reparent_category` (`taxomesh/application/service.py`), wrap `delete_category_parent_link` → `add_category_parent` (cycle detection + save) → the `save_category_parent_link` loop. The `add_category_parent` call MUST be inside so a `TaxomeshCyclicDependencyError` rolls back the preceding delete (it still propagates unchanged as a `TaxomeshError`). Keep the three `get_category` checks and sibling computation OUTSIDE.
- [X] T021 [US1] In `reparent_item` (`taxomesh/application/service.py`), wrap `delete_item_parent_link` → the `save_item_parent_link` loop. Keep the `get_item`/`get_category` checks and sibling computation OUTSIDE.
- [X] T022 [US1] Ensure `TaxomeshRepositoryError` is imported in `service.py` (add to existing exceptions import if absent).
- [X] T023 [US1] Run `pytest tests/service/test_atomic_operations.py` — all US1 tests green (Django rollback verified for all five operations; raw errors wrapped, `TaxomeshError`s and pre-write `ValueError`/`ValidationError` passed through unchanged).

**Checkpoint**: User Story 1 fully delivered — the core anti-orphan guarantee holds on the transactional backend. This is the MVP.

---

## Phase 4: User Story 2 — Successful operations behave exactly as before (Priority: P1)

**Goal**: Wrapping introduces zero observable change on the success path, across all backends and for single-write operations.

**Independent Test**: The full existing service/adapter/integration suite passes; the five operations produce identical persisted state to pre-change behavior.

- [X] T024 [P] [US2] Add a success-path regression test in `tests/service/test_atomic_operations.py`: parametrized over all backends, run each of the five operations to success and assert the persisted result (records + ordering + return value) matches the pre-wrapping expectation.
- [X] T025 [US2] Run the full existing suite (`pytest`) across all backend params; confirm every previously-passing service, adapter, CLI, and contrib test still passes (no behavior change for the five ops or any single-write op).

**Checkpoint**: Success-path parity confirmed; no regression.

---

## Phase 5: User Story 3 — Per-backend guarantee is documented and honest (Priority: P2)

**Goal**: The two-tier guarantee is documented in docstrings, and the best-effort (no-op) semantics of file/in-memory backends are asserted by test to match the documentation.

**Independent Test**: Docstrings state the guarantee; a test shows a file/in-memory backend leaves partial state after a mid-operation failure (documented limitation) and that `atomic()` is a working no-op on the success path.

### Tests for User Story 3 (write first)

- [X] T026 [P] [US3] Failing test in `tests/service/test_atomic_operations.py`: on the JSON (and in-memory) backend, inject a mid-operation failure in `create_category`; assert partial state MAY remain (the category persisted without its parent link is NOT rolled back), documenting the best-effort limitation exactly as the docstrings state; and assert the success path is unaffected.

### Implementation for User Story 3

- [X] T027 [US3] Verify/complete the FR-008 docstrings authored in Phase 2 (T003–T006): port `atomic()` documents both tiers; each adapter override documents its specific behavior (Django = full rollback; JSON/YAML = best-effort no-op). Adjust wording so the assertions in T026 and the docstrings agree verbatim on the limitation.
- [X] T028 [US3] Run `pytest tests/service/test_atomic_operations.py -k best_effort` — best-effort semantics test green and consistent with docstrings.

**Checkpoint**: Guarantee documented and asserted; contract is honest per backend.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality gates and optional public-API note.

- [X] T029 Run the full quality gate: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`; fix any lint/format/type issues (line length 119).
- [X] T030 [P] Scope-guardrail review of the diff (FR-009, FR-010): confirm `atomic()` is the **only** method added to `TaxomeshRepositoryBase` (no composite/batch/session/unit-of-work method), and that no cross-boundary (L3) transaction logic spanning consumer entities was introduced. `git diff taxomesh/ports/repository.py` should show exactly one new method.
- [ ] T031 [P] After `/speckit.analyze` passes, propose a README note that custom-backend authors must implement `atomic()` (with the `nullcontext()` example from quickstart.md) — do NOT edit README during implement; only propose post-analyze per project rules.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** must complete before any user story.
- **Phase 3 (US1)** depends on Phase 2. Delivers the MVP.
- **Phase 4 (US2)** depends on Phase 3 (the wrapping must exist to verify success-path parity).
- **Phase 5 (US3)** depends on Phase 2 (adapters + docstrings) and Phase 3 (the failure path for the best-effort demonstration). Can start once T017 (create_category wrap) lands.
- **Phase 6 (Polish)** last.

### Story independence notes

- US1 is the standalone MVP: implementing only Phases 1–3 delivers the anti-orphan guarantee.
- US2 is verification-heavy and rides on US1's implementation.
- US3 is documentation + one best-effort test; independent of US1's Django assertions except that it reuses the failure-injection double from T010.

## Parallel Execution Examples

- **Phase 2 adapters**: T004, T005, T006, T007 touch different files → run in parallel after T003 (port method) lands. T002 (contract test) is [P] and can be written first alongside.
- **Phase 3 tests**: T010–T016 are all [P] (same new test file, independent test functions — coordinate to avoid edit collisions, or write T010 first then T011–T016 in parallel).
- **Implementation T017–T021** all edit `service.py` (same file) → NOT parallel; do sequentially.

## Implementation Strategy

1. **MVP** = Phases 1–3 (US1): the anti-orphan / full-rollback guarantee on Django. Ship-worthy on its own.
2. Add Phase 4 (US2) to certify no success-path regression.
3. Add Phase 5 (US3) for the documented best-effort contract.
4. Phase 6 gates + optional README follow-up after `/speckit.analyze` is clean.
