# Tasks: Category Fields, Models Refactor, CLI Output & Service Cache

**Input**: Design documents from `/specs/011-category-models-cli/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-output.md, quickstart.md

**Tests**: TDD is mandatory per project constitution. Every implementation task has a corresponding test task.

**Organization**: Tasks are grouped by user story (US1–US5) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup needed — this feature modifies existing files and adds new packages.

*No tasks — project infrastructure already exists.*

---

## Phase 2: Foundational (Models Directory Refactor — US2)

**Purpose**: Refactor `models.py` into `models/` package BEFORE any model changes. This is User Story 2 but must complete first because US1 adds fields to Category inside the new package structure.

**Goal**: Each model class in its own module under `taxomesh/domain/models/`. All existing imports preserved.

**Independent Test**: All existing tests pass. `from taxomesh.domain.models import X` resolves for every public class.

### Tests for Foundational Phase ⚠️

> **NOTE: Write these tests FIRST, ensure they PASS (this is a refactor — existing behavior preserved)**

- [x] T001 [US2] Write test verifying all public names are importable from `taxomesh.domain.models` in `tests/domain/test_models_package.py` — import `ModelBase`, `Item`, `Category`, `Tag`, `CategoryParentLink`, `ItemParentLink`, `ItemTagLink` and assert they are classes (FR-006)

### Implementation for Foundational Phase

- [x] T002 [US2] Create `taxomesh/domain/models/` package directory with `__init__.py` (empty initially)
- [x] T003 [P] [US2] Create `taxomesh/domain/models/base.py` — move `ModelBase` class from `models.py`
- [x] T004 [P] [US2] Create `taxomesh/domain/models/item.py` — move `Item` class, import `ModelBase` from `.base` and `ExternalId` from `taxomesh.domain.types`
- [x] T005 [P] [US2] Create `taxomesh/domain/models/category.py` — move `Category` class (current fields only, no new fields yet), import `ModelBase` from `.base`
- [x] T006 [P] [US2] Create `taxomesh/domain/models/tag.py` — move `Tag` class, import `ModelBase` from `.base`
- [x] T007 [P] [US2] Create `taxomesh/domain/models/category_parent_link.py` — move `CategoryParentLink` class, import `ModelBase` from `.base`
- [x] T008 [P] [US2] Create `taxomesh/domain/models/item_parent_link.py` — move `ItemParentLink` class, import `ModelBase` from `.base`
- [x] T009 [P] [US2] Create `taxomesh/domain/models/item_tag_link.py` — move `ItemTagLink` class, import `ModelBase` from `.base`
- [x] T010 [US2] Update `taxomesh/domain/models/__init__.py` — re-export all public names: `ModelBase`, `Item`, `Category`, `Tag`, `CategoryParentLink`, `ItemParentLink`, `ItemTagLink` (FR-006)
- [x] T011 [US2] Delete `taxomesh/domain/models.py` (the old single-file module, now replaced by the package)
- [x] T012 [US2] Run all existing tests and verify they pass — zero import errors across the codebase (SC-002, SC-006)

**Checkpoint**: Models refactor complete. All existing imports resolve. All existing tests pass.

---

## Phase 3: User Story 1 — Category Enabled & External ID Fields (Priority: P1) 🎯 MVP

**Goal**: `Category` model gains `enabled: bool = True` and `external_id: ExternalId = ""`.

**Independent Test**: Create a category with `external_id="genre-rock"`, verify defaults. Load legacy store, verify backward compatibility.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T013 [P] [US1] Write test for `Category` default fields — create with only `category_id` + `name`, assert `enabled is True` and `external_id == ""` in `tests/domain/test_models.py` (FR-001, FR-002)
- [x] T014 [P] [US1] Write test for `Category` explicit fields — create with `enabled=False, external_id="genre-rock"`, assert values persist in `tests/domain/test_models.py` (FR-001, FR-002)
- [x] T015 [P] [US1] Write test for backward compatibility — deserialize a Category dict without `enabled` or `external_id` keys via `Category.model_validate()`, assert defaults apply in `tests/domain/test_models.py` (FR-004)
- [x] T016 [P] [US1] Write test for round-trip persistence — create a Category with `enabled=False, external_id="genre-rock"`, serialize via `model_dump()`, deserialize via `model_validate()`, assert both fields survive the round-trip in `tests/domain/test_models.py` (FR-003)

### Implementation for User Story 1

- [x] T017 [US1] Add `enabled: bool = True` and `external_id: ExternalId = ""` fields to `Category` in `taxomesh/domain/models/category.py` — import `ExternalId` from `taxomesh.domain.types` (FR-001, FR-002)
- [x] T018 [US1] Run US1 tests and verify they pass

**Checkpoint**: Category model has both new fields. Legacy stores load with correct defaults. All tests pass.

---

## Phase 4: User Story 3 — CLI Colored Enabled Icons (Priority: P3)

**Goal**: Replace `enabled=True`/`enabled=False` text with green `✓` / red `✗` icons for both items and categories.

**Independent Test**: Run `taxomesh graph` with mixed enabled/disabled items and categories, verify icons and no `enabled=<value>` text.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T019 [US3] Create `tests/adapters/__init__.py` and `tests/adapters/cli/__init__.py` (test package setup for CLI graph output tests)
- [x] T020 [P] [US3] Write test for enabled item icon — call `_add_graph_node()` with an enabled item, assert output contains `✓` and does NOT contain `enabled=True` in `tests/adapters/cli/test_graph_output.py` (FR-007, FR-009)
- [x] T021 [P] [US3] Write test for disabled item icon — call `_add_graph_node()` with a disabled item, assert output contains `✗` and does NOT contain `enabled=False` in `tests/adapters/cli/test_graph_output.py` (FR-007, FR-009)
- [x] T022 [P] [US3] Write test for enabled category icon — call `_add_graph_node()` with an enabled category, assert output contains `✓` in `tests/adapters/cli/test_graph_output.py` (FR-008)
- [x] T023 [P] [US3] Write test for disabled category icon — call `_add_graph_node()` with a disabled category, assert output contains `✗` in `tests/adapters/cli/test_graph_output.py` (FR-008)

### Implementation for User Story 3

- [x] T024 [US3] Define named constants `ENABLED_ICON` and `DISABLED_ICON` (e.g. `"✓"` and `"✗"`) in `taxomesh/adapters/cli/main.py` using `Final[str]` (Principle X)
- [x] T025 [US3] Update `_add_graph_node()` in `taxomesh/adapters/cli/main.py` — replace `enabled={item.enabled}` text with `[green]{ENABLED_ICON}[/green]` or `[red]{DISABLED_ICON}[/red]` for items. Add same icon for categories. (FR-007, FR-008, FR-009)
- [x] T026 [US3] Run US3 tests and verify they pass

**Checkpoint**: Graph output shows colored icons instead of `enabled=<value>` text for both items and categories.

---

## Phase 5: User Story 4 — CLI External ID Display for Categories (Priority: P4)

**Purpose**: MUST run after US3 (both modify `_add_graph_node()` in the same file — sequential execution required).

**Note**: FR-010 requires `external_id` for both items AND categories. Item `external_id` display is pre-existing behavior (implemented before this feature). This phase adds the same treatment to categories only.

**Goal**: Show `external_id` for categories in graph output. Omit when empty.

**Independent Test**: Run `taxomesh graph` with categories that have `external_id` values and some without, verify display.

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T027 [P] [US4] Write test for category with `external_id` — call `_add_graph_node()` with `external_id="genre-rock"`, assert `genre-rock` appears in output in `tests/adapters/cli/test_graph_output.py` (FR-010)
- [x] T028 [P] [US4] Write test for category with empty `external_id` — call `_add_graph_node()` with `external_id=""`, assert no blank/broken identifier in output in `tests/adapters/cli/test_graph_output.py` (FR-011)

### Implementation for User Story 4

- [x] T029 [US4] Update `_add_graph_node()` in `taxomesh/adapters/cli/main.py` — add `[yellow]{external_id}[/yellow]` to category branch label when `external_id` is non-empty, omit when empty (FR-010, FR-011)
- [x] T030 [US4] Run US4 tests and verify they pass

**Checkpoint**: Graph output shows `external_id` for categories (omitted when empty) and items.

---

## Phase 6: User Story 5 — Memoize Utility & Service Cache (Priority: P5)

**Goal**: Add `memoize(ttl)` decorator with TTL + cache registry. Apply to all read-only service methods. Write operations clear entire cache.

**Independent Test**: Call a read-only service method twice within TTL, verify repository called once. Call write method, verify cache cleared. Wait for TTL, verify cache expired.

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T031 [US5] Create `tests/utils/__init__.py` (test package setup for utils tests)
- [x] T032 [P] [US5] Write test for `memoize` cache hit — decorate a counter function with `memoize(ttl=5)`, call twice with same args, assert function executed once in `tests/utils/test_memoize.py` (FR-012, FR-013)
- [x] T033 [P] [US5] Write test for `memoize` TTL expiry — decorate a function with `memoize(ttl=0.1)`, call, sleep 0.2s, call again, assert function executed twice in `tests/utils/test_memoize.py` (FR-013)
- [x] T034 [P] [US5] Write test for `memoize` different args — decorate a function, call with arg "a" then arg "b", assert function executed twice (independent cache per args) in `tests/utils/test_memoize.py` (FR-012)
- [x] T035 [P] [US5] Write test for `memoize` unhashable args — decorate a function, call with a list arg, assert no error and function executes (cache skipped) in `tests/utils/test_memoize.py`
- [x] T036 [P] [US5] Write test for `clear_all_caches()` — decorate two functions, call both, call `clear_all_caches()`, call both again, assert both re-executed in `tests/utils/test_memoize.py` (FR-017)
- [x] T037 [P] [US5] Write test for `clear_cache` per-function — decorate a function, call it, call `wrapper.clear_cache()`, call again, assert function re-executed in `tests/utils/test_memoize.py`
- [x] T038 [P] [US5] Write test for service `get_category` caching — mock repository, call `get_category()` twice with same UUID, assert repository method called once in `tests/service/test_service_cache.py` (FR-014, SC-007)
- [x] T039 [P] [US5] Write test for service cache invalidation on write — mock repository, call `get_category()` (cached), call `create_category()`, call `get_category()` again, assert repository called twice total in `tests/service/test_service_cache.py` (FR-017, SC-009)
- [x] T040 [P] [US5] Write test for service `list_categories`, `get_item`, `list_items`, `list_tags`, `get_graph` caching — mock repository, call each twice, assert each repository method called once in `tests/service/test_service_cache.py` (FR-014)

### Implementation for User Story 5

- [x] T041 [US5] Create `taxomesh/utils/__init__.py` (empty package marker)
- [x] T042 [US5] Create `taxomesh/utils/memoize.py` — implement `memoize(ttl)` closure-based decorator with `time.monotonic`, cache dict in closure, `clear_cache` attribute on wrapper, module-level `_cache_registry` list, and `clear_all_caches()` function. Type with `ParamSpec`/`TypeVar` for mypy strict. (FR-012, FR-013, FR-016)
- [x] T043 [US5] Add `DEFAULT_CACHE_TTL: Final[int] = 5` constant to `taxomesh/application/service.py` (FR-015, Principle X)
- [x] T044 [US5] Decorate all read-only methods on `TaxomeshService` with `@memoize(DEFAULT_CACHE_TTL)` — `get_category`, `list_categories`, `get_item`, `list_items`, `list_tags`, `get_graph` in `taxomesh/application/service.py` (FR-014)
- [x] T045 [US5] Add `clear_all_caches()` call at the end of all 13 write methods on `TaxomeshService` in `taxomesh/application/service.py` — `create_category`, `update_category`, `delete_category`, `create_item`, `update_item`, `delete_item`, `create_tag`, `update_tag`, `delete_tag`, `assign_tag`, `remove_tag`, `add_category_parent`, `place_item_in_category` (FR-017)
- [x] T046 [US5] Run US5 tests and verify they pass

**Checkpoint**: All read-only service methods are cached with 5s TTL. All write methods invalidate the entire cache. Memoize utility is reusable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and full test suite validation.

- [x] T047 Run full quality gate suite: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`
- [x] T048 Verify `taxomesh graph` output shows correct icons, `external_id` for categories, and no `enabled=<value>` text (SC-003, SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: N/A — no setup tasks.
- **Phase 2 (Foundational / US2)**: Models refactor. MUST complete before US1 (US1 adds fields to the refactored Category module).
- **Phase 3 (US1)**: Depends on Phase 2. Category field additions.
- **Phase 4 (US3)**: Depends on US1 (categories need `enabled` field). CLI icon changes.
- **Phase 5 (US4)**: Depends on US3 (both modify `_add_graph_node()` — must be sequential). CLI external_id display.
- **Phase 6 (US5)**: Independent of US3/US4 but logically after US1. Memoize + service cache. Can run in parallel with US3/US4.
- **Phase 7 (Polish)**: Depends on all user stories complete.

### User Story Dependencies

- **US2 (P2 — Foundational)**: No dependencies. Must complete first (structural refactor).
- **US1 (P1)**: Depends on US2 (adds fields to refactored `category.py`).
- **US3 (P3)**: Depends on US1 (categories need `enabled` for icon display).
- **US4 (P4)**: Depends on US3 (both modify `_add_graph_node()` — sequential execution required).
- **US5 (P5)**: Depends on US1 (service methods must work with new fields). Can run in parallel with US3/US4.

### Parallel Opportunities

- T003–T009 can all run in parallel (separate model modules, no dependencies)
- T013–T016 can all run in parallel (separate test cases)
- T020–T023 can all run in parallel (separate test cases in same file)
- T027, T028 can run in parallel (separate test cases)
- T032–T040 can all run in parallel (separate test cases across two files)
- US5 can run in parallel with US3/US4 after US1

---

## Parallel Example: User Story 5

```bash
# Launch all tests for US5 together (TDD — write failing tests):
Task: "Test memoize cache hit in tests/utils/test_memoize.py"
Task: "Test memoize TTL expiry in tests/utils/test_memoize.py"
Task: "Test memoize different args in tests/utils/test_memoize.py"
Task: "Test memoize unhashable args in tests/utils/test_memoize.py"
Task: "Test clear_all_caches in tests/utils/test_memoize.py"
Task: "Test service get_category caching in tests/service/test_service_cache.py"
Task: "Test service cache invalidation in tests/service/test_service_cache.py"
Task: "Test all read-only service caching in tests/service/test_service_cache.py"
```

---

## Implementation Strategy

### MVP First (US2 + US1)

1. Complete Phase 2 (US2 — models refactor)
2. Complete Phase 3 (US1 — Category fields)
3. **STOP and VALIDATE**: Run T012 + T018 — all tests pass
4. Category model has `enabled` and `external_id` with backward compatibility

### Incremental Delivery

1. US2 (T001–T012) → Models refactored → Foundation ready
2. US1 (T013–T018) → Category fields added → MVP!
3. US3 (T019–T026) → Colored icons in CLI
4. US4 (T027–T030) → External ID display for categories (after US3)
5. US5 (T031–T046) → Memoize + service cache + invalidation
6. T047–T048 → Full quality gates pass

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD is mandatory: write failing tests before implementation
- US2 is done first (foundational) even though it's P2 priority — US1 depends on the refactored package structure
- US3 and US4 MUST be sequential (both modify `_add_graph_node()` in the same file) — US3 first, then US4
- US5 is independent of CLI changes but depends on service methods working correctly with new Category fields
