# Tasks: Service Slug Lookup Methods

**Input**: Design documents from `specs/020-slug-lookup/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution — test tasks are included and MUST
be written and confirmed failing before the corresponding implementation task runs.

**Organization**: Tasks are grouped by user story. Both stories are P1 and touch the same
two files, so they are executed sequentially (US1 → US2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify no new infrastructure is required.

No setup tasks — the project structure, repository protocol (`get_category_by_slug`,
`get_item_by_slug`), exception hierarchy, and `@memoize` decorator are all already in
place. Phase 2 (Foundational) is also empty for the same reason.

**Checkpoint**: Proceed directly to user story phases.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core prerequisites for both user stories.

No foundational tasks — all blocking prerequisites exist:
- `TaxomeshRepositoryBase.get_category_by_slug` and `get_item_by_slug` already declared in
  `taxomesh/ports/repository.py`.
- All concrete adapters already implement both methods.
- `InMemoryRepository` in `tests/service/conftest.py` already implements both methods.
- `TaxomeshCategoryNotFoundError` and `TaxomeshItemNotFoundError` already exist in
  `taxomesh/exceptions.py`.

**Checkpoint**: Foundation ready — user story phases can begin immediately.

---

## Phase 3: User Story 1 — Look Up Category by Slug (Priority: P1) 🎯 MVP

**Goal**: `TaxomeshService.get_category_by_slug(slug)` returns the matching `Category`
or raises `TaxomeshCategoryNotFoundError`.

**Independent Test**: Create a category with `slug="books"`, call
`service.get_category_by_slug("books")`, assert the returned object matches. Call with
`"missing"` and assert `TaxomeshCategoryNotFoundError` is raised.

### Tests for User Story 1

> ⚠️ **Write these tests FIRST — confirm they FAIL before starting T002**

- [x] T001 [US1] Add `TestGetCategoryBySlug` class with three test methods to `tests/service/test_service_slug.py`:
  - `test_get_category_by_slug_returns_category` — create category with slug, assert returned object matches
  - `test_get_category_by_slug_not_found_raises` — call with non-existent slug, assert `TaxomeshCategoryNotFoundError`
  - `test_get_category_by_slug_empty_slug_raises` — call with `""`, assert `TaxomeshCategoryNotFoundError`

### Implementation for User Story 1

- [x] T002 [US1] Add `get_category_by_slug(self, slug: str) -> Category` method to `TaxomeshService` in `taxomesh/application/service.py` (after `update_category`), decorated with `@memoize(DEFAULT_CACHE_TTL)`; delegates to `self._repo.get_category_by_slug(slug)`; raises `TaxomeshCategoryNotFoundError` if result is `None`

**Checkpoint**: Run `pytest tests/service/test_service_slug.py::TestGetCategoryBySlug` — all 3 tests must pass.

---

## Phase 4: User Story 2 — Look Up Item by Slug (Priority: P1)

**Goal**: `TaxomeshService.get_item_by_slug(slug)` returns the matching `Item`
or raises `TaxomeshItemNotFoundError`.

**Independent Test**: Create an item with `slug="widget"`, call
`service.get_item_by_slug("widget")`, assert the returned object matches. Call with
`"missing"` and assert `TaxomeshItemNotFoundError` is raised.

### Tests for User Story 2

> ⚠️ **Write these tests FIRST — confirm they FAIL before starting T004**

- [x] T003 [US2] Add `TestGetItemBySlug` class with three test methods to `tests/service/test_service_slug.py`:
  - `test_get_item_by_slug_returns_item` — create item with slug, assert returned object matches
  - `test_get_item_by_slug_not_found_raises` — call with non-existent slug, assert `TaxomeshItemNotFoundError`
  - `test_get_item_by_slug_empty_slug_raises` — call with `""`, assert `TaxomeshItemNotFoundError`

### Implementation for User Story 2

- [x] T004 [US2] Add `get_item_by_slug(self, slug: str) -> Item` method to `TaxomeshService` in `taxomesh/application/service.py` (after `update_item`), decorated with `@memoize(DEFAULT_CACHE_TTL)`; delegates to `self._repo.get_item_by_slug(slug)`; raises `TaxomeshItemNotFoundError` if result is `None`

**Checkpoint**: Run `pytest tests/service/test_service_slug.py::TestGetItemBySlug` — all 3 tests must pass.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T005 Run full quality gate suite from repo root and confirm all pass:
  - `pytest tests/service/test_service_slug.py` — all 6 new tests pass
  - `ruff check .`
  - `ruff format --check .`
  - `mypy --strict .`
  - `pytest --cov=taxomesh --cov-fail-under=80`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: N/A — no tasks
- **Foundational (Phase 2)**: N/A — no tasks
- **User Story 1 (Phase 3)**: Can start immediately — T001 → T002 (sequential, same files)
- **User Story 2 (Phase 4)**: Depends on Phase 3 completion (same files — service.py + test_service_slug.py)
- **Polish (Phase 5)**: Depends on Phase 3 + Phase 4 completion

### User Story Dependencies

- **US1 (Phase 3)**: No dependencies — start immediately
- **US2 (Phase 4)**: Starts after US1 completes (same files; sequential to avoid conflicts)

### Within Each Story

- Test task (T001 / T003) MUST run before its implementation task (T002 / T004)
- Confirm tests FAIL before writing implementation

### Parallel Opportunities

Both stories touch the same two files (`service.py` and `test_service_slug.py`), so
they cannot be parallelised. The execution order is strictly T001 → T002 → T003 → T004 → T005.

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. T001 — write failing tests for category slug lookup
2. T002 — implement `get_category_by_slug`
3. Validate: `pytest tests/service/test_service_slug.py::TestGetCategoryBySlug`
4. Both stories are P1 and small — continue to Phase 4 immediately

### Full Feature

1. T001 → T002 → T003 → T004 → T005
2. Total: 5 tasks, ~15–20 lines of new code across 2 files

---

## Notes

- No new files are created — only `taxomesh/application/service.py` and
  `tests/service/test_service_slug.py` are modified.
- The `service` fixture from `tests/service/conftest.py` (InMemoryRepository) is reused
  directly in all new tests.
- Both new methods follow the exact same pattern as `get_category` / `get_item` —
  delegate to repo, raise on None, decorate with `@memoize`.
