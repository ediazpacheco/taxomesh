# Tasks: Framework-Agnostic HTTP API Handlers

**Input**: Design documents from `/specs/028-contrib-api/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: TDD is mandatory per project constitution. Test tasks MUST be completed and FAILING before implementation tasks are started.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in every task description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency change + package skeleton. No user story work can begin until complete.

- [x] T001 Update `pyproject.toml`: remove `fastapi>=0.110` from `[project.dependencies]` and `[project.optional-dependencies.dev]`; add `pydantic>=2.0` to `[project.dependencies]`
- [x] T002 Create `taxomesh/contrib/api/__init__.py` re-exporting `schemas`, `handlers`, `errors` modules

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Test infrastructure that ALL user story test files depend on.

**⚠️ CRITICAL**: No user story test can be written until this phase is complete.

- [x] T003 Create `tests/contrib/conftest.py` with a `service` fixture backed by `InMemoryRepository` (import `InMemoryRepository` from `tests.service.conftest`)

**Checkpoint**: Test fixture available — user story phases can now begin.

---

## Phase 3: User Story 1 — FastAPI Wiring (Priority: P1) 🎯 MVP

**Goal**: Ship `schemas.py`, `handlers.py`, and `errors.py` so that a consuming FastAPI app can wire any taxomesh operation into a route with ≤10 lines of integration code.

**Independent Test**: Run `pytest tests/contrib/` — all tests pass. Confirm `mypy --strict .` reports zero errors on `taxomesh/contrib/api/`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before writing implementation**

- [x] T004 [P] [US1] Write failing tests for `schemas` validation in `tests/contrib/test_api_schemas.py` (8 schema classes: `CreateCategoryRequest`, `UpdateCategoryRequest`, `CreateItemRequest`, `UpdateItemRequest`, `CreateTagRequest`, `UpdateTagRequest`, `AddParentRequest`, `PlaceInCategoryRequest`) — cover valid inputs, `max_length` violations, and default values
- [x] T005 [P] [US1] Write failing tests for `errors.to_tuple` in `tests/contrib/test_api_errors.py` — cover all 5 exception branches (404, 409, 422, 500, base fallback) and verify `{"detail": str(exc)}` body shape
- [x] T006 [P] [US1] Write failing tests for all handlers in `tests/contrib/test_api_handlers.py` — one test class per handler group (categories, items, tags, relationships, graph); cover happy path and not-found cases for each operation

### Implementation for User Story 1

- [x] T007 [US1] Implement `taxomesh/contrib/api/schemas.py` — 8 `pydantic.BaseModel` subclasses with `max_length` constraints imported from `taxomesh.domain.constants`; all string fields annotated via `Annotated[str, Field(max_length=N)]` (depends on T004)
- [x] T008 [US1] Implement `taxomesh/contrib/api/errors.py` — `to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]` with `Final[int]` constants `_HTTP_404`, `_HTTP_409`, `_HTTP_422`, `_HTTP_500`; check `TaxomeshDuplicateSlugError` before `TaxomeshValidationError` (depends on T005)
- [x] T009 [US1] Implement `taxomesh/contrib/api/handlers.py` — 24 module-level functions covering categories (6), items (7), tags (4), relationships (6), graph (1); each accepts `TaxomeshService` as first arg and delegates directly; no business logic (depends on T006, T007, T008)

**Checkpoint**: `pytest tests/contrib/` passes. `mypy --strict .` zero errors. `ruff check .` clean. User Story 1 is fully functional.

---

## Phase 4: User Story 2 — Django Wiring Validation (Priority: P2)

**Goal**: Confirm that the same `schemas`, `handlers`, and `errors` artefacts work in a Django view with no taxomesh code changes. US2 requires no new source files — the existing test suite already validates framework-agnosticism via `InMemoryRepository` (no FastAPI dependency in tests).

**Independent Test**: Inspect `tests/contrib/test_api_handlers.py` — handlers are called with plain Python (no FastAPI `TestClient`). Confirm no import from `fastapi` appears anywhere in `taxomesh/contrib/api/`. Confirm `pip show taxomesh` does not list `fastapi` under `Requires`.

### Validation for User Story 2

- [x] T010 [US2] Verify `taxomesh/contrib/api/handlers.py`, `schemas.py`, and `errors.py` contain no imports from `fastapi`, `django`, or any HTTP framework — grep check; fix if any found
- [x] T011 [US2] Verify `pip show taxomesh` (or `uv pip show taxomesh`) no longer lists `fastapi` as a requirement — confirm `pyproject.toml` change from T001 is correct

**Checkpoint**: No framework imports in `taxomesh/contrib/api/`. FastAPI is absent from dependency listing. User Story 2 validated.

---

## Phase 5: User Story 3 — README HTTP API Integration Section (Priority: P3)

**Goal**: Add a prominent "HTTP API integration" section to `README.md` with complete FastAPI and Django wiring examples, the exception-to-status mapping table, and a note that `pydantic` (not `fastapi`) is the runtime dependency.

**Independent Test**: Read only the "HTTP API integration" README section. Confirm a developer can copy either the FastAPI or Django snippet and run it against a fresh `TaxomeshService` without reading source code.

### Implementation for User Story 3

- [x] T012 [US3] Update `README.md`: add "HTTP API integration" section after the existing "Python API" section, containing:
  - Intro paragraph explaining taxomesh ships no server
  - Complete FastAPI wiring example (import, route, schema, handler, `errors.to_tuple`)
  - Complete Django view wiring example (import, view, `model_validate_json`, handler, `errors.to_tuple`)
  - Exception-to-HTTP-status mapping table (all 5 entries from `errors.py`)
  - Installation note: `pydantic` is the direct dep; `fastapi` is not required
- [x] T013 [US3] Update the "Architecture" section of `README.md` to list `contrib/api/` as an adapter layer alongside `contrib/django/`

**Checkpoint**: README self-contained. Copy-paste examples are runnable. User Story 3 complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates across all stories.

- [x] T014 [P] Run `ruff check . && ruff format --check .` — fix any lint or formatting issues
- [x] T015 [P] Run `mypy --strict .` — fix any type errors in new files
- [x] T016 Run `pytest --cov=taxomesh --cov-fail-under=80` — confirm coverage ≥ 80% and all tests pass
- [x] T017 [P] Validate `specs/028-contrib-api/` artefacts are committed: `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/api-contract.md`, `quickstart.md`, `checklists/requirements.md`

---

## Phase 7: Clarification Follow-up (post /speckit.clarify 2026-03-10)

**Purpose**: Implement FR-007 clarification — extend `service.update_item()` to accept and propagate `external_id`.

**Note**: Tasks in this phase have no `[US]` label because they are spec-driven amendments to previously delivered User Story 1 artefacts, not a new user story. They are treated as corrective work within US1 scope.

- [x] T018 Add failing tests for `external_id` in `UpdateItemRequest` (`tests/contrib/test_api_schemas.py`) and `handlers.update_item` (`tests/contrib/test_api_handlers.py`)
- [x] T019 Restore `external_id: Annotated[str, Field(...)] | None = None` in `UpdateItemRequest` (`taxomesh/contrib/api/schemas.py`)
- [x] T020 Extend `TaxomeshService.update_item()` with `external_id: str | None = None` parameter and apply it when non-`None` (`taxomesh/application/service.py`)
- [x] T021 Pass `external_id=body.external_id` from `handlers.update_item` to the service (`taxomesh/contrib/api/handlers.py`)
- [x] T022 Re-run quality gates: `ruff check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80` — all pass (660 tests, 93% coverage)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — blocks all test writing
- **US1 (Phase 3)**: Depends on Phase 2 — tests written first (T004–T006), then implementation (T007–T009)
- **US2 (Phase 4)**: Depends on Phase 3 completion — validation only, no new source
- **US3 (Phase 5)**: Depends on Phase 3 (must know the final API surface before writing docs)
- **Polish (Phase 6)**: Depends on all implementation phases complete

### User Story Dependencies

- **US1 (P1)**: Can start immediately after Foundational — no dependencies on US2/US3
- **US2 (P2)**: Validation only; depends on US1 (same artefacts)
- **US3 (P3)**: Depends on US1 (needs confirmed API surface for doc examples)

### Within Phase 3 (US1)

1. T004, T005, T006 — write tests in parallel (different files) → all MUST FAIL
2. T007 — implement `schemas.py` (depends on T004 failing)
3. T008 — implement `errors.py` (depends on T005 failing; parallel with T007)
4. T009 — implement `handlers.py` (depends on T006 failing + T007 + T008)

### Parallel Opportunities

- T004, T005, T006 — all test files are independent; write in parallel
- T007, T008 — `schemas.py` and `errors.py` are independent; implement in parallel
- T010, T011 — US2 validation tasks are independent; check in parallel
- T014, T015 — linting and type-checking are independent; run in parallel
- T014, T015, T017 — all can run after T016 gate passes

---

## Parallel Example: User Story 1 (Phase 3)

```bash
# Step 1: Write tests in parallel (T004, T005, T006 — different files)
Task: "Write failing schema tests in tests/contrib/test_api_schemas.py"       # T004
Task: "Write failing error tests in tests/contrib/test_api_errors.py"         # T005
Task: "Write failing handler tests in tests/contrib/test_api_handlers.py"     # T006

# Step 2: Implement schemas and errors in parallel (independent files)
Task: "Implement taxomesh/contrib/api/schemas.py"  # T007
Task: "Implement taxomesh/contrib/api/errors.py"   # T008

# Step 3: Implement handlers (depends on T007 + T008)
Task: "Implement taxomesh/contrib/api/handlers.py"  # T009
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`pyproject.toml` + `__init__.py`)
2. Complete Phase 2: Foundational (`tests/contrib/conftest.py`)
3. Complete Phase 3: US1 tests → schemas → errors → handlers
4. **STOP and VALIDATE**: `pytest tests/contrib/` passes, `mypy --strict .` clean
5. US1 fully functional and independently testable

### Incremental Delivery

1. Setup + Foundational → skeleton ready
2. US1 (Phase 3) → handlers/schemas/errors shipped → validate → deployable
3. US2 (Phase 4) → framework-agnosticism confirmed → no regressions
4. US3 (Phase 5) → README updated → feature discoverable
5. Polish (Phase 6) → quality gates green → PR ready

---

## Notes

- [P] tasks operate on different files with no cross-dependencies
- Story labels map tasks to spec.md user stories for traceability
- TDD is mandatory: test files MUST exist and FAIL before implementation files are touched
- `InMemoryRepository` lives in `tests/service/conftest.py`; import it from there in `tests/contrib/conftest.py`
- No HTTP server, no FastAPI test client: tests use plain Python function calls
- Run quality gates (T014–T016) after EVERY fix, not just once
