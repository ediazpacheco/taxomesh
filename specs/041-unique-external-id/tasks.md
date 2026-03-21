---

description: "Task list template for feature implementation"
---

# Tasks: Unique External ID (1:1 Constraint)

**Input**: Design documents from `/specs/041-unique-external-id/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: TDD is mandatory per project constitution. Every implementation task is preceded
by a failing-test task. Tests MUST fail before implementation begins.

**Organization**: Tasks are grouped by user story phase. US1 and US2 (both P1 lookups)
share a phase because they are implemented in the same files across all backends.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to
- All paths are relative to the repository root

---

## Phase 1: Setup

**Purpose**: Confirm test directories exist for new test files.

- [ ] T001 Confirm or create `tests/adapters/repositories/` directory for new backend-specific external_id tests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Exception hierarchy, domain model type changes, repository protocol update,
and Django ORM/migration. ALL must be complete before any user story phase begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Exception

- [ ] T002 Write failing tests for `TaxomeshExternalIdConflictError`: assert it exists, subclasses `TaxomeshValidationError`, and includes the conflicting `external_id` value in its message — in `tests/test_exceptions.py`
- [ ] T003 Add `TaxomeshExternalIdConflictError(TaxomeshValidationError)` to `taxomesh/exceptions.py`; export it from `taxomesh/__init__.py`; verify T002 passes

### Domain Models

- [ ] T004 [P] Write failing tests for `Item.external_id`: assert type is `str | None`, default is `None`, `None` input stays `None`, UUID/int input coerced to `str` — in `tests/domain/test_item.py`
- [ ] T005 [P] Write failing tests for `Category.external_id`: same assertions as T004 — in `tests/domain/test_category.py`
- [ ] T006 Update `DEFAULT_ITEM_EXTERNAL_ID` and `DEFAULT_CATEGORY_EXTERNAL_ID` to `Final[str | None] = None` in `taxomesh/domain/constants.py`
- [ ] T007 [P] Update `Item.external_id` field to `Annotated[str | None, Field(max_length=MAX_EXTERNAL_ID_STR_LENGTH)]` with default `None`; update `_coerce_external_id` validator so `None` → `None` and all others → `str` in `taxomesh/domain/models/item.py`; verify T004 passes
- [ ] T008 [P] Update `Category.external_id` field and validator identically to T007 in `taxomesh/domain/models/category.py`; verify T005 passes

### Repository Protocol

- [ ] T009 Replace `list_items_by_external_id` / `list_categories_by_external_id` with `get_item_by_external_id(external_id: str) -> Item | None` and `get_category_by_external_id(external_id: str) -> Category | None` in `taxomesh/ports/repository.py`; update `save_item` / `save_category` docstrings to document `TaxomeshExternalIdConflictError` on duplicate non-None `external_id`

### Django ORM & Migration

- [ ] T010 Write failing tests for Django ORM model changes: `ItemModel.external_id` and `CategoryModel.external_id` are `null=True, unique=True`; migration converts existing `""` → `NULL` before applying constraint — in `tests/contrib/django/test_migrations.py`
- [ ] T011 Update `CategoryModel.external_id` and `ItemModel.external_id` to `CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH, null=True, blank=True, unique=True, default=None)` (remove `db_index=True`) in `taxomesh/contrib/django/models.py`
- [ ] T012 Write migration `taxomesh/contrib/django/migrations/0008_unique_external_id.py`: step 1 — `RunPython` to convert `external_id=""` → `NULL` on both `taxomesh_item` and `taxomesh_category`; step 2 — `AlterField` for `CategoryModel.external_id` (`null=True, unique=True`, no `db_index`); step 3 — `AlterField` for `ItemModel.external_id` identically; include reverse migration; verify T010 passes

- [ ] T051 Update existing `tests/contrib/django/test_django_repository.py`: replace all fixtures and assertions using `external_id=""` with `external_id=None`; ensure existing round-trip tests pass after the domain model default change (these tests will break at T007/T008 if not updated)

**Checkpoint**: Foundation complete — domain models use `str | None`, exception exists, protocol updated, ORM schema and migration ready. User story phases may begin.

---

## Phase 3: User Stories 1 & 2 — Item and Category Lookups (Priority: P1) 🎯 MVP

**Goal**: `get_item_by_external_id` and `get_category_by_external_id` return `T | None`
across all three repository backends and the service layer.

**Independent Test**: Create an Item with `external_id="test-ext"`, call
`service.get_item_by_external_id("test-ext")`, assert the Item is returned.
Call `service.get_item_by_external_id("missing")`, assert `None`. Repeat for Category.

- [ ] T052 [P] Scan `taxomesh/contrib/api/` (handlers, schemas, errors) for any call to `get_items_by_external_id` or `get_categories_by_external_id`; update any found call sites to use `get_item_by_external_id` / `get_category_by_external_id` and adjust callers to handle `T | None` return instead of `list[T]`

### JsonRepository — Lookups

- [ ] T013 [P] [US1] Write failing tests for `JsonRepository.get_item_by_external_id`: found returns Item, not-found returns `None`, UUID/int input coerced correctly — in `tests/adapters/repositories/test_json_repository_external_id.py`
- [ ] T014 [US2] Write failing tests for `JsonRepository.get_category_by_external_id`: found returns Category, not-found returns `None` — in `tests/adapters/repositories/test_json_repository_external_id.py`
- [ ] T015 [US1] Replace `list_items_by_external_id` with `get_item_by_external_id` in `taxomesh/adapters/repositories/json_repository.py`; verify T013 passes
- [ ] T016 [US2] Replace `list_categories_by_external_id` with `get_category_by_external_id` in `taxomesh/adapters/repositories/json_repository.py`; verify T014 passes

### YAMLRepository — Lookups

- [ ] T017 [P] [US1] Write failing tests for `YAMLRepository.get_item_by_external_id` — in `tests/adapters/repositories/test_yaml_repository_external_id.py`
- [ ] T018 [US2] Write failing tests for `YAMLRepository.get_category_by_external_id` — in `tests/adapters/repositories/test_yaml_repository_external_id.py`
- [ ] T019 [US1] Replace `list_items_by_external_id` with `get_item_by_external_id` in `taxomesh/adapters/repositories/yaml_repository.py`; verify T017 passes
- [ ] T020 [US2] Replace `list_categories_by_external_id` with `get_category_by_external_id` in `taxomesh/adapters/repositories/yaml_repository.py`; verify T018 passes

### DjangoRepository — Lookups

- [ ] T021 [P] [US1] Write failing tests for `DjangoRepository.get_item_by_external_id`: found returns Item, not-found returns `None` — in `tests/contrib/django/test_unique_external_id.py`
- [ ] T022 [US2] Write failing tests for `DjangoRepository.get_category_by_external_id`: found returns Category, not-found returns `None` — in `tests/contrib/django/test_unique_external_id.py`
- [ ] T023 [US1] Replace `list_items_by_external_id` with `get_item_by_external_id` in `taxomesh/adapters/repositories/django_repository.py`; verify T021 passes
- [ ] T024 [US2] Replace `list_categories_by_external_id` with `get_category_by_external_id` in `taxomesh/adapters/repositories/django_repository.py`; verify T022 passes

### Service Layer — Lookups

- [ ] T025 [US1] Write failing tests for `TaxomeshService.get_item_by_external_id`: found → Item, not-found → `None`, `None` input → `None` immediately, UUID/int coercion, root Category excluded from category method — replace all tests in `tests/test_service_external_id.py`
- [ ] T026 [US2] Replace `get_items_by_external_id` with `get_item_by_external_id` and `get_categories_by_external_id` with `get_category_by_external_id` in `taxomesh/application/service.py`; add `None` short-circuit (`if external_id is None: return None`) before coercion; keep `@memoize(DEFAULT_CACHE_TTL)`; verify T025 passes

**Checkpoint**: All three backends and the service layer return `T | None` for external_id lookups. US1 and US2 are fully functional.

---

## Phase 4: User Story 3 — Write-time Uniqueness Enforcement (Priority: P1)

**Goal**: Saving a record with a non-None `external_id` already owned by a different record
of the same type raises `TaxomeshExternalIdConflictError`. Re-saving the same record does not.

**Independent Test**: Create Item A with `external_id="dup"`. Save Item B with
`external_id="dup"`, assert `TaxomeshExternalIdConflictError` is raised and B is not stored.
Re-save Item A with the same `external_id`, assert no error.

### JsonRepository — Uniqueness

- [ ] T027 [P] [US3] Write failing tests for `JsonRepository.save_item` conflict: duplicate non-None `external_id` raises `TaxomeshExternalIdConflictError`; re-saving same item (same `item_id`) does not raise; `external_id=None` never conflicts — in `tests/adapters/repositories/test_json_repository_external_id.py`
- [ ] T028 [US3] Write failing tests for `JsonRepository.save_category` conflict — in `tests/adapters/repositories/test_json_repository_external_id.py`
- [ ] T029 [US3] Add uniqueness check to `JsonRepository.save_item` and `save_category`: scan `self._items` / `self._categories` for any record with matching non-None `external_id` excluding the record being saved (by primary key); raise `TaxomeshExternalIdConflictError` on conflict — in `taxomesh/adapters/repositories/json_repository.py`; verify T027, T028 pass

### YAMLRepository — Uniqueness

- [ ] T030 [P] [US3] Write failing tests for `YAMLRepository.save_item` and `save_category` conflict (same as T027/T028 for YAML) — in `tests/adapters/repositories/test_yaml_repository_external_id.py`
- [ ] T031 [US3] Add identical uniqueness check to `YAMLRepository.save_item` and `save_category` in `taxomesh/adapters/repositories/yaml_repository.py`; verify T030 passes

### DjangoRepository — Uniqueness

- [ ] T032 [P] [US3] Write failing tests for `DjangoRepository.save_item` conflict: unique DB constraint violation is caught and raised as `TaxomeshExternalIdConflictError`; re-saving same item does not raise; multiple `NULL` external_ids do not conflict — in `tests/contrib/django/test_unique_external_id.py`
- [ ] T033 [US3] Write failing tests for `DjangoRepository.save_category` conflict — in `tests/contrib/django/test_unique_external_id.py`
- [ ] T034 [US3] Update `DjangoRepository.save_item` and `save_category` in `taxomesh/adapters/repositories/django_repository.py`: catch `IntegrityError` (imported from `django.db`) specifically and raise `TaxomeshExternalIdConflictError`; non-`IntegrityError` `DatabaseError` continues to raise `TaxomeshRepositoryError`; verify T032, T033 pass

**Checkpoint**: All three backends enforce uniqueness. US3 is fully functional. The 1:1 contract is now guaranteed end-to-end.

---

## Phase 5: User Story 4 — None as Absent Value (Priority: P2)

**Goal**: Items and Categories created without `external_id` store and retrieve `None`
(not `""`). Multiple records with `external_id=None` coexist without conflict.

**Independent Test**: Create Item without `external_id`; retrieve it; assert `external_id is None`.
Create 10 Items all with `external_id=None`; assert no `TaxomeshExternalIdConflictError` raised.

- [ ] T035 [P] [US4] Write failing tests for `None` round-trip in `JsonRepository`: save Item with `external_id=None`, retrieve, assert `external_id is None`; save Category with `None`, retrieve, assert `None` — in `tests/adapters/repositories/test_json_repository_external_id.py`
- [ ] T036 [P] [US4] Write failing tests for `None` round-trip in `YAMLRepository` — in `tests/adapters/repositories/test_yaml_repository_external_id.py`
- [ ] T037 [US4] Write failing tests for `None` round-trip in `DjangoRepository` and verify multiple `NULL` values do not trigger unique constraint violation — in `tests/contrib/django/test_unique_external_id.py`
- [ ] T038 [US4] Write failing tests for `TaxomeshService` `None` input: `get_item_by_external_id(None)` returns `None` without calling repository; `get_category_by_external_id(None)` returns `None` — in `tests/test_service_external_id.py`
- [ ] T039 [US4] Verify all T035–T038 tests pass with the domain model and repository changes already made in Phases 2–4; fix any remaining gaps in `None` handling across all three backends

**Checkpoint**: US4 complete. `None` is the correct absent value sentinel in all layers. `""` is no longer a valid `external_id`.

---

## Phase 6: CLI & Django Admin

**Purpose**: Update the two consumer-facing layers that display or accept `external_id`.
Both can proceed in parallel once Phase 5 is complete.

### CLI

- [ ] T040 [P] Write failing tests for `_parse_external_id("")` returning `None`; and for CLI output rendering `None` `external_id` as an empty indicator (not the string `"None"`) — in the existing CLI test file or `tests/adapters/cli/test_cli_external_id.py`
- [ ] T041 [P] Update `_parse_external_id` in `taxomesh/adapters/cli/main.py` to return `str | None` (empty string input → `None`); update all display code that renders `external_id` to show `—` (or equivalent empty indicator) when value is `None`; verify T040 passes

### Django Admin

- [ ] T042 [P] Write failing tests for `_resolve_linked_url(None, ...)` returning `None`; and for admin `list_display` rendering `None` `external_id` as an empty cell — in `tests/contrib/django/test_admin_external_id.py`
- [ ] T043 [P] Update `GraphEntry` TypedDict `external_id` field from `str` to `str | None`; update `_resolve_linked_url` signature to `(external_id: str | None, ...)` and add `None` guard; update any `list_display` callable that renders `external_id` to return `""` when `None`; retain `external_id` in `search_fields` on both Item and Category admin classes (Django handles NULL in icontains searches correctly — see FR-025); verify admin form submits empty `external_id` as NULL (covered by model `null=True, blank=True` from T011; add smoke test if not already in T042) — in `taxomesh/contrib/django/admin.py`; verify T042 passes

**Checkpoint**: CLI and Admin handle `None` correctly. All user stories are complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T044 [P] Update README public API section: document `get_item_by_external_id` and `get_category_by_external_id` with `Item | None` / `Category | None` return type, `None` input semantics, and `TaxomeshExternalIdConflictError` — in `README.md`
- [ ] T045 [P] Update `CLAUDE.md` Active Technologies entries for specs 013 and 021 to reflect `str | None` type, 1:1 constraint, removed list-return semantics, and new exception — in `CLAUDE.md`
- [ ] T046 Update all affected docstrings referencing "orphan", "duplicate signal", "len > 1", `list_items_by_external_id`, or `list_categories_by_external_id` — in `taxomesh/application/service.py`, `taxomesh/ports/repository.py`, all three repository adapters
- [ ] T047 [P] Run `ruff check .` and fix all lint errors
- [ ] T048 [P] Run `ruff format --check .` and fix all formatting issues
- [ ] T049 Run `mypy --strict .` and fix all type errors (pay special attention to `str | None` annotations on `external_id` fields and new `TaxomeshExternalIdConflictError` usage)
- [ ] T050 Run `pytest --cov=taxomesh --cov-fail-under=80` — assert all tests pass and coverage ≥ 80%

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └── Phase 2 (Foundational) — BLOCKS all user story phases
        ├── Phase 3 (US1 + US2: Lookups) — all backends + service
        │     └── Phase 4 (US3: Uniqueness) — all backends
        │           └── Phase 5 (US4: None handling) — verification
        │                 ├── Phase 6a (CLI)   [P]
        │                 └── Phase 6b (Admin) [P]
        │                       └── Phase 7 (Polish)
```

### User Story Dependencies

- **US1 (P1 — Item Lookup)**: Depends on Phase 2 only. No dependency on US2/US3/US4.
- **US2 (P1 — Category Lookup)**: Depends on Phase 2 only. Shares files with US1 (same phase).
- **US3 (P1 — Uniqueness)**: Depends on US1 + US2 being complete (same repository files).
- **US4 (P2 — None Handling)**: Depends on Phase 2 (domain models) and Phase 3 (repository round-trips).

### Parallel Opportunities Within Phases

**Phase 2**:
- T004 + T005 (domain model tests): parallel — different test files
- T007 + T008 (domain model impls): parallel — different source files

**Phase 3**:
- T013 then T014 (JsonRepository lookup tests): sequential within file, T014 after T013
- T017 then T018 (YAMLRepository lookup tests): sequential within file
- T021 then T022 (DjangoRepository lookup tests): sequential within file
- Json + YAML test/impl groups: parallel — completely different files (e.g., T013+T014 parallel with T017+T018)

**Phase 4**:
- T027 then T028 (JsonRepository conflict tests): sequential within file
- T030 (YAML conflict tests): parallel with T027/T028 group (different files)
- T032 then T033 (DjangoRepository conflict tests): sequential within file

**Phase 5**:
- T035 + T036 (None round-trip tests for Json/YAML): parallel

**Phase 6**:
- T040 + T041 (CLI) and T042 + T043 (Admin): fully parallel — different files

**Phase 7**:
- T044 + T045 (documentation): parallel
- T047 + T048 (ruff check + format): parallel

---

## Parallel Example: Phase 3 (Lookups)

```bash
# These test tasks can be launched simultaneously:
Task T013: "JsonRepository.get_item_by_external_id tests"
Task T014: "JsonRepository.get_category_by_external_id tests"
Task T017: "YAMLRepository.get_item_by_external_id tests"
Task T018: "YAMLRepository.get_category_by_external_id tests"
Task T021: "DjangoRepository.get_item_by_external_id tests"
Task T022: "DjangoRepository.get_category_by_external_id tests"

# Then implement backends in parallel:
Task T015 + T016: "JsonRepository lookup impl"
Task T019 + T020: "YAMLRepository lookup impl"
Task T021 + T022: "DjangoRepository lookup impl"
```

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Complete Phase 2: Foundational (exception, models, protocol, ORM)
2. Complete Phase 3: US1 + US2 lookups (all backends + service)
3. **STOP and VALIDATE**: `service.get_item_by_external_id("x")` returns Item or None
4. Proceed to Phase 4 (US3 — uniqueness) and Phase 5 (US4 — None) when ready

### Incremental Delivery

1. Phase 2 → Foundation ready — domain models, exception, protocol, ORM/migration
2. Phase 3 → Lookups work — `get_item/category_by_external_id` across all backends
3. Phase 4 → Writes are safe — `TaxomeshExternalIdConflictError` on duplicate writes
4. Phase 5 → None is clean — no `""` sentinel, no NULL collision
5. Phase 6 → UI updated — CLI and admin handle `None` correctly
6. Phase 7 → Ship — all quality gates green

---

## Notes

- **TDD is mandatory**: Every `T*xx` impl task has a corresponding test task immediately before it. Tests MUST fail before implementation.
- **Commit after each logical group**: After Phase 2 checkpoint, after Phase 3 checkpoint, etc.
- **`mypy --strict`**: The `str | None` type on `external_id` will surface type errors in call sites that assumed `str`. Fix them in the implementation tasks, not in a late cleanup pass.
- **`""` eradication**: After Phase 2 and the migration, `""` should never appear as an `external_id` value. If tests reveal any remaining `""` defaults, fix immediately.
- **`TaxomeshExternalIdConflictError` placement**: Under `TaxomeshValidationError` (same as `TaxomeshDuplicateSlugError`) — see research.md Decision 1.
