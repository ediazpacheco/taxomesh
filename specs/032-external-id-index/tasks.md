# Tasks: External-ID Database Indexes & Lookup Promotion

**Input**: Design documents from `/specs/032-external-id-index/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**TDD**: All tests must be written **before** implementation and confirmed **FAILING** before the corresponding implementation task is started.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1 / US2 / US3)
- Exact file paths are in every description

---

## Phase 1: Foundational — TDD Test Suite (MUST FAIL before Phase 2)

**Purpose**: Write all failing tests first. No implementation task in Phase 2+ may start until
the corresponding test in this phase exists and is confirmed FAILING.

**⚠️ CRITICAL**: Run `pytest tests/contrib/django/test_django_repository.py` after each test task
and confirm the new test is collected and **FAILING** before moving to the next phase.

- [x] T001 [US1] Add `test_item_external_id_field_has_db_index` to `TestExternalIdIndex` class in `tests/contrib/django/test_django_repository.py` — assert `ItemModel._meta.get_field("external_id").db_index is True`
- [x] T002 [P] [US2] Add `test_category_external_id_field_has_db_index` to `TestExternalIdIndex` class in `tests/contrib/django/test_django_repository.py` — assert `CategoryModel._meta.get_field("external_id").db_index is True`
- [x] T003 [P] [US1] Add four `list_items_by_external_id` tests to `TestExternalIdLookup` class in `tests/contrib/django/test_django_repository.py`: `test_list_items_by_external_id_no_match`, `test_list_items_by_external_id_single_match`, `test_list_items_by_external_id_duplicate_match`, `test_list_items_by_external_id_blank`
- [x] T004 [P] [US2] Add four `list_categories_by_external_id` tests to `TestExternalIdLookup` class in `tests/contrib/django/test_django_repository.py`: `test_list_categories_by_external_id_no_match`, `test_list_categories_by_external_id_single_match`, `test_list_categories_by_external_id_duplicate_match`, `test_list_categories_by_external_id_blank`

**Checkpoint**: 10 new tests collected, all FAILING. Proceed to Phase 2.

---

## Phase 2: User Story 1 — Fast Item Resolution by external_id (Priority: P1) 🎯 MVP

**Goal**: `ItemModel.external_id` has a database index; `list_items_by_external_id` tests pass.

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py::TestExternalIdIndex::test_item_external_id_field_has_db_index tests/contrib/django/test_django_repository.py::TestExternalIdLookup -k "item"` — all should pass.

### Implementation for User Story 1

- [x] T005 [US1] Add `db_index=True` to `ItemModel.external_id` field in `taxomesh/contrib/django/models.py`

**Checkpoint**: `T001` and `T003` tests pass. `T002` and `T004` still fail (category index not yet added). Migration not yet created — Django will report pending migrations.

---

## Phase 3: User Story 2 — Fast Category Resolution by external_id (Priority: P1)

**Goal**: `CategoryModel.external_id` has a database index; migration `0004` covers both fields; all category lookup tests pass.

**Independent Test**: `pytest tests/contrib/django/test_django_repository.py -k "external_id"` — all 10 new tests pass.

### Implementation for User Story 2

- [x] T006 [US2] Add `db_index=True` to `CategoryModel.external_id` field in `taxomesh/contrib/django/models.py`
- [x] T007 [US2] Create `taxomesh/contrib/django/migrations/0004_external_id_indexes.py` — additive migration with `AlterField` operations for both `CategoryModel.external_id` and `ItemModel.external_id` adding `db_index=True`; depends on `("taxomesh_contrib_django", "0003_item_relation_link")`

**Checkpoint**: All 10 new tests pass. `python manage.py migrate --check` passes (no pending migrations). No existing tests regress.

---

## Phase 4: User Story 3 — Consumer API Documentation (Priority: P2)

**Goal**: README explicitly guides consumers to use the dedicated `external_id` lookup methods.

**Independent Test**: README contains: "list_items_by_external_id", "list_categories_by_external_id", a warning against using `list_items()` / `list_categories()` for point lookups, and a statement that `external_id` is indexed but not unique.

### Implementation for User Story 3

- [x] T008 [US3] Update `README.md` — add an `external_id` lookup guidance subsection covering: use `get_items_by_external_id` / `get_categories_by_external_id` for point lookups; do not use `list_items()` / `list_categories()` with Python filtering; `external_id` is indexed but not unique; result length indicates orphan (0), unique (1), or duplicate (≥ 2) state

**Checkpoint**: README reviewed — all four guidance points present.

---

## Phase 5: Polish & Quality Gates

**Purpose**: Ensure all quality gates pass before proposing a commit.

- [x] T009 Run `ruff check .` — fix any linting issues introduced in T005–T007
- [x] T010 [P] Run `ruff format --check .` — fix any formatting issues
- [x] T011 [P] Run `mypy --strict .` — fix any type errors introduced in T005–T007
- [x] T012 Run `pytest --cov=taxomesh --cov-fail-under=80` — confirm all tests pass and coverage ≥ 80%

**Checkpoint**: All four quality gates green. Ready to propose commit.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Foundational TDD)**: No dependencies — start immediately
- **Phase 2 (US1)**: Depends on T001 + T003 FAILING ✅
- **Phase 3 (US2)**: Depends on Phase 2 complete (T005 done); T006 + T007 depend on each other implicitly since migration must capture both field changes
- **Phase 4 (US3)**: Independent — can start any time after Phase 1; no code dependency
- **Phase 5 (Polish)**: Depends on Phases 2, 3, and 4 complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 1 tests existing and failing
- **US2 (P1)**: Depends on US1 model change (T005) because migration 0004 covers both fields
- **US3 (P2)**: Fully independent — documentation only

### Within Each Phase

- T001–T004 are all parallel (different test methods, no shared state)
- T005 is a prerequisite for T006 (migration must capture both field changes in one operation)
- T006 must complete before T007 (migration generation captures both changes)
- T009–T011 are parallel (independent quality gate commands)

---

## Parallel Opportunities

### Phase 1 (TDD tests — all parallel)

```
Launch simultaneously:
  T001: test_item_external_id_field_has_db_index in test_django_repository.py
  T002: test_category_external_id_field_has_db_index in test_django_repository.py
  T003: 4x list_items_by_external_id tests in test_django_repository.py
  T004: 4x list_categories_by_external_id tests in test_django_repository.py
```

### Phase 4 + Phase 5 (parallel across phases)

```
T008 (README) can run in parallel with T005-T007 — no file conflicts
T009-T011 (quality gates) can all run in parallel
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 1 (write failing tests)
2. Complete Phase 2 (add `db_index=True` to `ItemModel.external_id`)
3. **STOP and VALIDATE**: T001 + T003 tests pass
4. Note: migration is not generated yet — add US2 before deploying

### Full Delivery (recommended — US1 + US2 share one migration)

1. Phase 1: Write all 10 failing tests
2. Phase 2: Add `db_index=True` to `ItemModel.external_id`
3. Phase 3: Add `db_index=True` to `CategoryModel.external_id` + generate migration 0004
4. Phase 4: Update README
5. Phase 5: Quality gates → propose commit

---

## Notes

- `[P]` tasks = different files, no dependencies on each other
- Tests T001–T004 must be confirmed **FAILING** before starting T005
- Migration T007 must be generated **after** both T005 and T006 are applied so a single migration captures both field changes
- `external_id` must remain non-unique — do NOT add `unique=True` to the field or migration
- All test classes (`TestExternalIdIndex`, `TestExternalIdLookup`) go in the existing `tests/contrib/django/test_django_repository.py` — no new test files
