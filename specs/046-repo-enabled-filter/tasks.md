# Tasks: Repository-Level Enabled Filtering

**Input**: Design documents from `specs/046-repo-enabled-filter/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: TDD is mandatory per project constitution. Test tasks precede every implementation task.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on concurrent task)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: No new infrastructure required; this feature modifies existing files only.

- [ ] T001 Verify quality gates pass on `main` before starting: run `ruff check . && ruff format --check . && mypy --strict . && pytest` from repo root

---

## Phase 2: Foundational — Repository Port Contract (Blocking)

**Purpose**: Update the `TaxomeshRepositoryBase` protocol and `InMemoryRepository` test fixture.
All adapters and service tasks depend on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Write failing tests asserting `list_categories(enabled=True)`, `list_categories(enabled=False)`, and `list_categories(enabled=None)` signatures exist and behave correctly on `InMemoryRepository` in `tests/service/conftest.py` — add to new file `tests/service/test_service_enabled_filter.py`
- [ ] T003 Update `TaxomeshRepositoryBase.list_categories` signature to `list_categories(self, *, enabled: bool | None = True) -> list[Category]` with updated docstring in `taxomesh/ports/repository.py`
- [ ] T004 Update `TaxomeshRepositoryBase.list_items` signature to `list_items(self, *, enabled: bool | None = True) -> list[Item]` with updated docstring in `taxomesh/ports/repository.py`
- [ ] T005 Update `InMemoryRepository.list_categories` to accept and apply the `enabled` filter in `tests/service/conftest.py`
- [ ] T006 Update `InMemoryRepository.list_items` to accept and apply the `enabled` filter in `tests/service/conftest.py`
- [ ] T007 Run `mypy --strict .` and `pytest tests/service/test_service_enabled_filter.py` — T002 tests must fail (adapters not yet updated), port type-checks must pass

**Checkpoint**: Port contract updated; InMemoryRepository conformant; mypy clean on port + fixture.

---

## Phase 3: User Story 1 — Filter by Enabled State at Retrieval Time (Priority: P1) 🎯 MVP

**Goal**: `list_categories(enabled=True/False/None)` and `list_items(enabled=True/False/None)` return the correct records from JSON and YAML adapters.

**Independent Test**: Call `list_categories()` on an `InMemoryRepository`, `JsonRepository`, and `YAMLRepository` seeded with both enabled and disabled records; assert only enabled records returned by default.

### Tests

- [ ] T008 [P] [US1] Write failing tests for `JsonRepository.list_categories` enabled filter (`True`/`False`/`None`) in `tests/adapters/repositories/test_json_repository_enabled.py` — include an assertion that the root category never appears in results for any `enabled` value (FR-009)
- [ ] T009 [P] [US1] Write failing tests for `JsonRepository.list_items` enabled filter (`True`/`False`/`None`) in `tests/adapters/repositories/test_json_repository_enabled.py` — include an assertion that the root category never appears in any result (FR-009)
- [ ] T010 [P] [US1] Write failing tests for `YAMLRepository.list_categories` enabled filter (`True`/`False`/`None`) in `tests/adapters/repositories/test_yaml_repository_enabled.py`
- [ ] T011 [P] [US1] Write failing tests for `YAMLRepository.list_items` enabled filter (`True`/`False`/`None`) in `tests/adapters/repositories/test_yaml_repository_enabled.py`

### Implementation

- [ ] T012 [P] [US1] Implement `enabled` filter in `JsonRepository.list_categories`: apply `[c for c in cats if c.enabled == enabled]` when `enabled is not None` in `taxomesh/adapters/repositories/json_repository.py`
- [ ] T013 [P] [US1] Implement `enabled` filter in `JsonRepository.list_items`: same pattern as T012 in `taxomesh/adapters/repositories/json_repository.py`
- [ ] T014 [P] [US1] Implement `enabled` filter in `YAMLRepository.list_categories`: same pattern as T012 in `taxomesh/adapters/repositories/yaml_repository.py`
- [ ] T015 [P] [US1] Implement `enabled` filter in `YAMLRepository.list_items`: same pattern as T012 in `taxomesh/adapters/repositories/yaml_repository.py`
- [ ] T016 [US1] Run `pytest tests/adapters/repositories/test_json_repository_enabled.py tests/adapters/repositories/test_yaml_repository_enabled.py` — all tests must pass

**Checkpoint**: JSON and YAML adapters filter by `enabled`; InMemoryRepository conformant. US1 independently testable.

---

## Phase 4: User Story 2 — Service Layer and All Interfaces Coherent (Priority: P2)

**Goal**: Every service method, CLI command, contrib API handler, and Django admin view defaults to `enabled=True`. The `enabled_only` parameter name is replaced by `enabled` everywhere.

**Independent Test**: Call each public surface (service, CLI, API) without an `enabled` argument; assert disabled records never appear in any result.

### Tests — Service Layer

- [ ] T017 [US2] Write failing tests for `service.list_categories(enabled=...)`, `service.list_items(enabled=...)`, `service.list_categories_by_item(enabled=...)` — covering `True`/`False`/`None` — in `tests/service/test_service_enabled_filter.py`
- [ ] T018 [US2] Write failing tests for `service.search_items(enabled=...)` and `service.search_categories(enabled=...)` renamed parameter (assert `enabled_only` kwarg raises `TypeError`) in `tests/service/test_service_enabled_filter.py`
- [ ] T019 [US2] Write failing tests for `service.get_graph(enabled=...)` — default excludes disabled categories and items; `enabled=None` includes all — in `tests/service/test_service_enabled_filter.py`

### Implementation — Service Layer

- [ ] T020 [US2] Add `enabled: bool | None = True` to `TaxomeshService.list_categories`; pass `enabled=enabled` to `repo.list_categories()`; apply Python-level filter on the `parent_id` path results in `taxomesh/application/service.py`
- [ ] T021 [US2] Add `enabled: bool | None = True` to `TaxomeshService.list_items`; pass `enabled=enabled` to `repo.list_items()`; apply Python-level filter on the `category_id` path results in `taxomesh/application/service.py`
- [ ] T022 [US2] Add `enabled: bool | None = True` to `TaxomeshService.list_categories_by_item`; apply Python-level filter after `get_category()` per link; remove "disabled categories are included; filtering is caller's responsibility" from docstring in `taxomesh/application/service.py`
- [ ] T023 [US2] Rename `enabled_only` → `enabled` in `TaxomeshService.search_items`; update corpus slice to `[sc for sc in corpus if sc.obj.enabled == enabled]`; update `candidates` filter accordingly in `taxomesh/application/service.py`
- [ ] T024 [US2] Rename `enabled_only` → `enabled` in `TaxomeshService.search_categories`; apply same rename as T023 in `taxomesh/application/service.py`
- [ ] T025 [US2] Update `_get_item_corpus` to call `self._repo.list_items(enabled=None)` in `taxomesh/application/service.py`
- [ ] T026 [US2] Update `_get_category_corpus` to call `self._repo.list_categories(enabled=None)` in `taxomesh/application/service.py`
- [ ] T027 [US2] Add `enabled: bool | None = True` to `TaxomeshService.get_graph`; pass `enabled=enabled` to both `repo.list_categories()` and `repo.list_items()` in `taxomesh/application/service.py`
- [ ] T028 [US2] Run `pytest tests/service/test_service_enabled_filter.py` — all service tests must pass

### Tests — CLI

- [ ] T029 [US2] Write failing tests for `--include-disabled` flag on `category list`, `item list`, and `graph` commands in `tests/adapters/cli/test_cli_include_disabled.py`

### Implementation — CLI

- [ ] T030 [US2] Add `include_disabled: bool = typer.Option(False, "--include-disabled", help="Include disabled records in output")` to `category_list`; pass `enabled=None if include_disabled else True` to `svc.list_categories()` in `taxomesh/adapters/cli/main.py`
- [ ] T031 [US2] Add `--include-disabled` flag to `item_list`; pass `enabled=None if include_disabled else True` to `svc.list_items()` in `taxomesh/adapters/cli/main.py`
- [ ] T032 [US2] Add `--include-disabled` flag to `graph_cmd`; pass `enabled=None if include_disabled else True` to `service.get_graph()` and to the `list_items()` call on line ~547 in `taxomesh/adapters/cli/main.py`
- [ ] T033 [US2] Run `pytest tests/adapters/cli/test_cli_include_disabled.py` — all CLI tests must pass

### Tests — Contrib API

- [ ] T034 [P] [US2] Write failing tests for `include_disabled` param on `list_categories`, `list_items`, and `get_graph` handlers in `tests/contrib/test_api_handlers.py`
- [ ] T035 [P] [US2] Write failing tests asserting `SearchItemsRequest.enabled` field exists and `enabled_only` is gone; same for `SearchCategoriesRequest` in `tests/contrib/test_api_schemas.py`

### Implementation — Contrib API

- [ ] T036 [US2] Add `include_disabled: bool = False` param to `list_categories` handler; pass `enabled=None if include_disabled else True` to service in `taxomesh/contrib/api/handlers.py`
- [ ] T037 [US2] Add `include_disabled: bool = False` param to `list_items` handler; same pattern as T036 in `taxomesh/contrib/api/handlers.py`
- [ ] T038 [US2] Add `include_disabled: bool = False` param to `get_graph` handler; same pattern as T036 in `taxomesh/contrib/api/handlers.py`
- [ ] T039 [US2] Update `search_items` handler to pass `enabled=params.enabled` (was `enabled_only=params.enabled_only`) to service in `taxomesh/contrib/api/handlers.py`
- [ ] T040 [US2] Update `search_categories` handler to pass `enabled=params.enabled` (was `enabled_only=params.enabled_only`) to service in `taxomesh/contrib/api/handlers.py`
- [ ] T041 [US2] Rename `enabled_only: bool = True` → `enabled: bool = True` in `SearchItemsRequest` in `taxomesh/contrib/api/schemas.py`
- [ ] T042 [US2] Rename `enabled_only: bool = True` → `enabled: bool = True` in `SearchCategoriesRequest` in `taxomesh/contrib/api/schemas.py`
- [ ] T043 [US2] Run `pytest tests/contrib/test_api_handlers.py tests/contrib/test_api_schemas.py` — all API tests must pass

### Tests — Django Admin

- [ ] T044 [US2] Write failing tests asserting admin internal calls to `repo.list_categories()`, `repo.list_categories()` (import view), `svc.list_categories(parent_id=...)`, and `svc.list_items(category_id=...)` use `enabled=None` in `tests/contrib/django/test_admin_enabled_filter.py`

### Implementation — Django Admin

- [ ] T045 [US2] Update all four admin internal call sites identified in research.md Decision 6 to pass `enabled=None` in `taxomesh/contrib/django/admin.py`
- [ ] T046 [US2] Run `pytest tests/contrib/django/test_admin_enabled_filter.py` — all admin tests must pass

**Checkpoint**: All service methods, CLI commands, API handlers, and admin views apply `enabled=True` by default. Zero `enabled_only` references remain (run `grep -r "enabled_only" taxomesh/`).

---

## Phase 5: User Story 3 — Django Backend Filters at Storage Level (Priority: P3)

**Goal**: `DjangoRepository.list_categories` and `list_items` apply the `enabled` filter via ORM `.filter(enabled=enabled)`, not by fetching all records and filtering in Python.

**Independent Test**: Seed the Django test DB with both enabled and disabled records; call `DjangoRepository.list_categories(enabled=True)`; assert the ORM queryset uses a `WHERE enabled = TRUE` clause (verified via `django.test.utils.CaptureQueriesContext` or `assertNumQueries`).

### Tests

- [ ] T047 [P] [US3] Write failing tests for `DjangoRepository.list_categories(enabled=True/False/None)` asserting ORM-level filtering in `tests/contrib/django/test_django_repository_enabled.py` — include assertion that root category never appears for any `enabled` value (FR-009)
- [ ] T048 [P] [US3] Write failing tests for `DjangoRepository.list_items(enabled=True/False/None)` asserting ORM-level filtering in `tests/contrib/django/test_django_repository_enabled.py`

### Implementation

- [ ] T049 [US3] Implement `enabled` ORM filter in `DjangoRepository.list_categories`: add `if enabled is not None: qs = qs.filter(enabled=enabled)` before the final queryset evaluation in `taxomesh/adapters/repositories/django_repository.py`
- [ ] T050 [US3] Implement `enabled` ORM filter in `DjangoRepository.list_items`: same pattern as T049 in `taxomesh/adapters/repositories/django_repository.py`
- [ ] T051 [US3] Run `pytest tests/contrib/django/test_django_repository_enabled.py` — all Django adapter tests must pass

**Checkpoint**: Django adapter issues `WHERE enabled = <value>` at query time; no full-table fetch for enabled-filtered calls.

---

## Phase 6: User Story 4 — Consistent Behaviour Across All Backends (Priority: P4)

**Goal**: All four repository adapters (JSON, YAML, InMemory, Django) return identical result sets for the same `enabled` argument value given equivalent seed data.

**Independent Test**: Use `tests/service/test_parity_fixture.py` infrastructure; parameterize over all four backends; assert identical list lengths and record IDs for each `enabled` value.

### Tests & Validation

- [ ] T052 [US4] Write cross-backend parity tests for `list_categories(enabled=True)`, `list_categories(enabled=False)`, and `list_categories(enabled=None)` covering all four adapters in `tests/service/test_parity_enabled_filter.py`
- [ ] T053 [US4] Write cross-backend parity tests for `list_items(enabled=True)`, `list_items(enabled=False)`, and `list_items(enabled=None)` covering all four adapters in `tests/service/test_parity_enabled_filter.py`
- [ ] T054 [US4] Run `pytest tests/service/test_parity_enabled_filter.py` — all parity tests must pass; fix any divergences found in adapters

**Checkpoint**: All backends are provably consistent for every `enabled` value.

---

## Phase 7: User Story 5 — Documentation Updated (Priority: P5)

**Goal**: Every public-facing docstring, CLI help text, and API schema description accurately reflects `enabled=True` as the default and explains how to retrieve disabled records.

**Independent Test**: `grep -r "enabled_only" taxomesh/` returns zero hits; each updated docstring includes the phrase "only enabled records are returned by default".

### Implementation

- [ ] T055 [P] [US5] Update docstrings for `list_categories` and `list_items` in `taxomesh/ports/repository.py` — document three-way `enabled` semantics and the `None` = all-records meaning
- [ ] T056 [P] [US5] Update docstrings for `list_categories`, `list_items`, `list_categories_by_item`, `search_items`, `search_categories`, and `get_graph` in `taxomesh/application/service.py` — state `enabled=True` default; remove stale "caller's responsibility" note from `list_categories_by_item`
- [ ] T057 [P] [US5] Update command docstrings and `help=` strings for `category list`, `item list`, and `graph` in `taxomesh/adapters/cli/main.py` — document `--include-disabled` flag
- [ ] T058 [P] [US5] Update docstrings for `list_categories`, `list_items`, `get_graph`, `search_items`, `search_categories` handlers in `taxomesh/contrib/api/handlers.py` and update `SearchItemsRequest` / `SearchCategoriesRequest` field descriptions in `taxomesh/contrib/api/schemas.py`
- [ ] T059 [US5] Update `README.md` — add migration note for the `enabled=True` default change and the `enabled_only` → `enabled` rename in the public API section

**Checkpoint**: `grep -r "enabled_only" taxomesh/` returns zero hits; all docstrings state the new default.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify quality gates, run the full test suite, and confirm all success criteria are met.

- [ ] T060 [P] Run `grep -r "enabled_only" taxomesh/` — must return zero hits (SC-005)
- [ ] T061 [P] Run `ruff check .` — must exit 0
- [ ] T062 [P] Run `ruff format --check .` — must exit 0
- [ ] T063 Run `mypy --strict .` — must exit 0
- [ ] T064 Run `pytest --cov=taxomesh --cov-fail-under=80` — full test suite must pass with ≥ 80% coverage
- [ ] T065 Update existing test files that call `list_categories()`, `list_items()`, `list_categories_by_item()`, `get_graph()`, or search methods with `enabled_only=` and expect disabled records in results — fix assertions to match the new `enabled=True` default (`tests/service/test_service_categories.py`, `tests/service/test_service_items.py`, `tests/service/test_service_graph.py`, `tests/service/test_service_search.py`, `tests/service/test_service_list_categories_by_item.py`, `tests/contrib/test_api_handlers.py`, `tests/contrib/test_api_schemas.py`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2; benefits from Phase 3 (adapters conformant)
- **Phase 5 (US3)**: Depends on Phase 2; independent of Phase 3/4
- **Phase 6 (US4)**: Depends on Phases 3, 4, and 5 all complete
- **Phase 7 (US5)**: Can begin after Phase 4; fully parallelizable tasks within
- **Phase 8 (Polish)**: Depends on all prior phases; T065 must precede T064

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2 (Foundational)
- **US2 (P2)**: Depends on Phase 2; Phase 3 adapters being done avoids mypy complaints
- **US3 (P3)**: Depends on Phase 2; independent of US1/US2
- **US4 (P4)**: Depends on US1 and US3 (all four adapters must be conformant)
- **US5 (P5)**: Depends on US2 (service API finalised before docs)

### Within Each Phase

- Test tasks precede their corresponding implementation tasks
- Parallel [P] tasks within a phase touch different files and may run concurrently
- Run `pytest` on the new test file before moving to the next phase

### Parallel Opportunities

- T008–T011 (adapter tests): all four can be written simultaneously
- T012–T015 (adapter implementations): all four can be implemented simultaneously
- T017–T019 (service tests): all three can be written simultaneously
- T034–T035 (API tests): can be written in parallel
- T047–T048 (Django adapter tests): can be written in parallel
- T055–T058 (documentation tasks): all four fully independent

---

## Parallel Example: Phase 3 (US1)

```bash
# Write all adapter tests simultaneously:
Task: "Write failing tests for JsonRepository.list_categories in test_json_repository_enabled.py"
Task: "Write failing tests for JsonRepository.list_items in test_json_repository_enabled.py"
Task: "Write failing tests for YAMLRepository.list_categories in test_yaml_repository_enabled.py"
Task: "Write failing tests for YAMLRepository.list_items in test_yaml_repository_enabled.py"

# Then implement all adapters simultaneously:
Task: "Implement enabled filter in JsonRepository.list_categories"
Task: "Implement enabled filter in JsonRepository.list_items"
Task: "Implement enabled filter in YAMLRepository.list_categories"
Task: "Implement enabled filter in YAMLRepository.list_items"
```

---

## Implementation Strategy

### MVP First (Phase 2 + Phase 3)

1. Complete Phase 1: Setup check
2. Complete Phase 2: Port + InMemoryRepository (CRITICAL)
3. Complete Phase 3: US1 — JSON + YAML adapter enabled filter
4. **STOP and VALIDATE**: `pytest tests/adapters/repositories/ tests/service/test_service_enabled_filter.py`
5. The core contract is live and testable

### Incremental Delivery

1. Phase 2 (Foundation) → Port contract locked
2. Phase 3 (US1) → JSON/YAML adapters filter correctly
3. Phase 4 (US2) → Service + CLI + API + Admin all coherent
4. Phase 5 (US3) → Django adapter ORM-efficient
5. Phase 6 (US4) → Parity guaranteed across all backends
6. Phase 7 (US5) → Documentation complete
7. Phase 8 (Polish) → Quality gates green → PR ready

---

## Notes

- TDD is mandatory: every test task must run before its implementation task; tests must **fail** first
- `enabled_only` must not appear anywhere in `taxomesh/` when Phase 8 is complete
- The `enabled=None` sentinel is an internal detail — it must not appear in CLI help text or API docs (use "include disabled" language instead)
- Existing tests that break due to the `enabled=True` default change are expected — fix them in T065, not ad-hoc during implementation
- Commit at the end of each phase checkpoint, never mid-phase
