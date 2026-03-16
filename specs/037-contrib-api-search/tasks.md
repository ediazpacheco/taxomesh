# Tasks: HTTP Search Support for contrib.api

**Input**: Design documents from `/specs/037-contrib-api-search/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per CLAUDE.md — test tasks are included in every user story phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Foundational (Blocking Prerequisite)

**Purpose**: Add the `MAX_SEARCH_QUERY_LENGTH` domain constant that all new schemas depend on. Must complete before any user story work begins.

**⚠️ CRITICAL**: No schema task can begin until T001 is complete.

- [ ] T001 Add `MAX_SEARCH_QUERY_LENGTH: Final[int] = 500` to `taxomesh/domain/constants.py` near the other `MAX_*` string-length constants

**Checkpoint**: Constant available — user story schema work can now begin.

---

## Phase 2: User Story 1 — Search Items via HTTP (Priority: P1) 🎯 MVP

**Goal**: Expose `search_items` as a validated, framework-agnostic handler backed by a `SearchItemsRequest` schema.

**Independent Test**: `search_items(service, SearchItemsRequest(q="troilo"))` returns a ranked `list[Item]` drawn from the service; calling with `q=""` returns `[]`; calling with an unknown `category_id` raises `TaxomeshCategoryNotFoundError`.

### Tests for User Story 1 ⚠️ Write and confirm FAIL before implementation

- [ ] T002 [P] [US1] Add failing tests for `SearchItemsRequest` schema (required `q`, max-length rejection, all defaults, UUID/None `category_id`) in `tests/contrib/test_api_schemas.py`
- [ ] T003 [P] [US1] Add failing tests for `search_items` handler (matching query, `enabled_only=True` filtering, blank `q` → `[]`, `limit` respected, `TaxomeshCategoryNotFoundError` propagation) in `tests/contrib/test_api_handlers.py`

### Implementation for User Story 1

- [ ] T004 [US1] Add `SearchItemsRequest` schema to `taxomesh/contrib/api/schemas.py` with `q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]`, `limit: int = DEFAULT_SEARCH_LIMIT`, `category_id: UUID | None = None`, `recursive: bool = False`, `enabled_only: bool = True`, `fuzzy: bool = True` (imports: `MAX_SEARCH_QUERY_LENGTH` from `taxomesh.domain.constants`, `DEFAULT_SEARCH_LIMIT` from `taxomesh.application.search`)
- [ ] T005 [US1] Add `search_items(service: TaxomeshService, params: SearchItemsRequest) -> list[Item]` handler to `taxomesh/contrib/api/handlers.py`, delegating all params as kwargs to `service.search_items()` with no exception handling

**Checkpoint**: Run `pytest tests/contrib/test_api_schemas.py tests/contrib/test_api_handlers.py -k "search_item"` — all tests green.

---

## Phase 3: User Story 2 — Search Categories via HTTP (Priority: P2)

**Goal**: Expose `search_categories` as a validated, framework-agnostic handler backed by a `SearchCategoriesRequest` schema.

**Independent Test**: `search_categories(service, SearchCategoriesRequest(q="jazz"))` returns a ranked `list[Category]` from the service; `q=""` returns `[]`; `parent_id` filters to direct children of the given parent.

### Tests for User Story 2 ⚠️ Write and confirm FAIL before implementation

- [ ] T006 [P] [US2] Add failing tests for `SearchCategoriesRequest` schema (required `q`, max-length rejection, all defaults, UUID/None `parent_id`) in `tests/contrib/test_api_schemas.py`
- [ ] T007 [P] [US2] Add failing tests for `search_categories` handler (matching query, blank `q` → `[]`, `limit` respected, `enabled_only` filtering, `parent_id` scoping) in `tests/contrib/test_api_handlers.py`

### Implementation for User Story 2

- [ ] T008 [US2] Add `SearchCategoriesRequest` schema to `taxomesh/contrib/api/schemas.py` with `q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]`, `limit: int = DEFAULT_SEARCH_LIMIT`, `parent_id: UUID | None = None`, `enabled_only: bool = True`, `fuzzy: bool = True`
- [ ] T009 [US2] Add `search_categories(service: TaxomeshService, params: SearchCategoriesRequest) -> list[Category]` handler to `taxomesh/contrib/api/handlers.py`, delegating all params as kwargs to `service.search_categories()` with no exception handling

**Checkpoint**: Run `pytest tests/contrib/test_api_schemas.py tests/contrib/test_api_handlers.py -k "search_categor"` — all tests green.

---

## Phase 4: User Story 3 — Serialize Search Results (Priority: P3)

**Goal**: Provide `items_to_list` and `categories_to_list` as pure serializer functions that convert domain-model lists to JSON-serializable plain dicts.

**Independent Test**: `items_to_list([item])` returns a list of one dict where `item_id` is a string (not a `UUID`); `items_to_list([])` returns `[]`. Same for `categories_to_list`.

### Tests for User Story 3 ⚠️ Write and confirm FAIL before implementation

- [ ] T010 [US3] Add failing tests for `items_to_list` (non-empty list → list of dicts with string UUID, empty list → `[]`) and `categories_to_list` (same contract) in `tests/contrib/test_api_serializers.py`

### Implementation for User Story 3

- [ ] T011 [US3] Add `items_to_list(items: list[Item]) -> list[dict[str, Any]]` to `taxomesh/contrib/api/serializers.py` using `[item.model_dump(mode="json") for item in items]`
- [ ] T012 [US3] Add `categories_to_list(categories: list[Category]) -> list[dict[str, Any]]` to `taxomesh/contrib/api/serializers.py` using `[cat.model_dump(mode="json") for cat in categories]`

**Checkpoint**: Run `pytest tests/contrib/test_api_serializers.py` — all tests green.

---

## Phase 5: Polish & Quality Gates

**Purpose**: Verify all quality gates pass end-to-end before proposing the PR.

- [ ] T013 Run `ruff check .` and fix any linting errors across all modified files
- [ ] T014 [P] Run `ruff format --check .` and fix any formatting issues
- [ ] T015 [P] Run `mypy --strict .` and fix any type errors (pay attention to `list[dict[str, Any]]` return types and `Any` justification comments)
- [ ] T016 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm coverage ≥ 80% with all tests passing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational)**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on T001 (constant must exist before schemas can import it)
- **Phase 3 (US2)**: Depends on T001 only — independent of Phase 2; can start after T001 completes
- **Phase 4 (US3)**: No dependency on Phase 2 or 3 — independent; can start at any time (serializers don't import schemas or handlers)
- **Phase 5 (Polish)**: Depends on all previous phases complete

### User Story Dependencies

- **User Story 1 (P1)**: Blocked only by T001; no dependency on US2, US3
- **User Story 2 (P2)**: Blocked only by T001; no dependency on US1, US3
- **User Story 3 (P3)**: No blockers; fully independent

### Within Each User Story

1. Write failing tests first (T00x marked [P] within story = can be written simultaneously)
2. Confirm tests fail
3. Implement (schema before handler; serializers have no ordering constraint)
4. Confirm tests pass

### Parallel Opportunities

- T002 and T003 can be written in parallel (different test files)
- T006 and T007 can be written in parallel (different test files)
- T004 (schema) and T003-test work can overlap if schema is written to a fresh section without running tests
- T013, T014, T015 (quality gates) can be checked in parallel (read-only operations)

---

## Parallel Example: User Story 1

```bash
# After T001 completes, launch both test tasks simultaneously:
Task A: "Add failing SearchItemsRequest schema tests in tests/contrib/test_api_schemas.py"
Task B: "Add failing search_items handler tests in tests/contrib/test_api_handlers.py"

# After A and B confirm failing, proceed sequentially:
Task C: "Add SearchItemsRequest schema to taxomesh/contrib/api/schemas.py"
Task D: "Add search_items handler to taxomesh/contrib/api/handlers.py"
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Complete Phase 1: T001
2. Complete Phase 2: T002 → T003 → T004 → T005
3. **STOP and VALIDATE**: `pytest tests/contrib/ -k "search_item"` all green

### Incremental Delivery

1. T001 (constant) → unlocks all stories
2. US1 (T002–T005) → item search end-to-end
3. US2 (T006–T009) → category search end-to-end
4. US3 (T010–T012) → serializers complete
5. Polish (T013–T016) → PR-ready

---

## Notes

- `[P]` tasks within a story phase target different files — safe to parallelize
- Test tasks (`T002`, `T003`, `T006`, `T007`, `T010`) extend existing files — do NOT create new test files
- `DEFAULT_SEARCH_LIMIT` is imported from `taxomesh.application.search`, not redefined
- `Any` in serializer return types is justified (heterogeneous JSON dict) — add inline comment `# Any: heterogeneous JSON dict`
- All handlers must propagate service exceptions without catching or wrapping them
