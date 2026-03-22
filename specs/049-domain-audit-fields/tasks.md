# Tasks: Domain Audit Fields (created_at, updated_at, version)

**Input**: Design documents from `specs/049-domain-audit-fields/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per CLAUDE.md — test tasks are included. Each test task MUST be run
and confirmed FAILING (where specified) before its corresponding implementation task begins.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 1: Setup

**Purpose**: No new project infrastructure required — stdlib `datetime` is the only new dependency.
All existing toolchain and package configuration remains unchanged.

- [ ] T001 Confirm no new runtime packages are needed: verify `datetime` and `timezone` are stdlib imports available in `taxomesh/domain/constants.py` and `taxomesh/application/service.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add audit fields to domain models, Django ORM models, and migration — required before
either user story can be implemented or tested.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Add `AUDIT_EPOCH: Final[datetime]` and `DEFAULT_VERSION: Final[int] = 0` constants to `taxomesh/domain/constants.py`; import `datetime` and `timezone` from stdlib at top of file
- [ ] T003 [P] Add `created_at: datetime`, `updated_at: datetime` (both default to `AUDIT_EPOCH`), and `version: Annotated[int, Field(ge=0)]` (default `DEFAULT_VERSION`) fields to `Category` in `taxomesh/domain/models/category.py`; import `datetime` from stdlib and new constants from `taxomesh.domain.constants`
- [ ] T004 [P] Add `created_at: datetime`, `updated_at: datetime` (both default to `AUDIT_EPOCH`), and `version: Annotated[int, Field(ge=0)]` (default `DEFAULT_VERSION`) fields to `Item` in `taxomesh/domain/models/item.py`; same imports as T003
- [ ] T005 [P] Add `created_at = models.DateTimeField(...)`, `updated_at = models.DateTimeField(...)`, and `version = models.IntegerField(default=0)` columns to `CategoryModel` and `ItemModel` in `taxomesh/contrib/django/models.py`; use `AUDIT_EPOCH` as the field `default` for both datetime columns
- [ ] T006 Create Django migration `taxomesh/contrib/django/migrations/0009_audit_fields.py` adding the three columns to `taxomesh_category` and `taxomesh_item` tables (depends on T005)
- [ ] T007 Update `DjangoRepository._row_to_category()` to pass `created_at`, `updated_at`, `version` from the ORM row to the `Category` constructor, and update `save_category()` to include the three fields in the `defaults` dict for `update_or_create` in `taxomesh/adapters/repositories/django_repository.py` (depends on T003, T005)
- [ ] T008 Update `DjangoRepository._row_to_item()` and `save_item()` in `taxomesh/adapters/repositories/django_repository.py` with the same three-field changes as T007 (depends on T004, T005)

**Checkpoint**: All three fields exist on `Category`, `Item`, `CategoryModel`, and `ItemModel`.
Django migration is ready. Repositories persist and restore the fields. No service stamping yet —
both user stories can now begin.

---

## Phase 3: User Story 1 — Inspect Creation and Modification Timestamps (Priority: P1) 🎯 MVP

**Goal**: `create_category` / `create_item` set `created_at == updated_at == UTC now`. `update_category` /
`update_item` advance `updated_at` to the new UTC now; `created_at` is unchanged. All backends
persist and restore both timestamps faithfully.

**Independent Test**: Create a category, verify `created_at == updated_at` and both are recent
UTC datetimes; update it, verify `updated_at >= created_at`. Deserialize a legacy JSON dict
without `created_at` — verify it loads without error and `created_at == AUDIT_EPOCH`.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before T010

- [ ] T009 [US1] Write failing tests in `tests/test_audit_fields_service.py`:
  - `test_create_category_timestamps_set()` — asserts `created_at == updated_at`, both are UTC-aware datetimes, both are recent (within 5s of test start)
  - `test_update_category_advances_updated_at()` — asserts `updated_at >= pre_update_updated_at` (per SC-002; allows equality to tolerate fast clocks), and `created_at` is unchanged from the value at creation
  - `test_create_item_timestamps_set()` — same as category
  - `test_update_item_advances_updated_at()` — same as category
  - Run `pytest tests/test_audit_fields_service.py` → confirm FAIL (service does not stamp yet)

### Implementation for User Story 1

- [ ] T010 [US1] In `taxomesh/application/service.py` — update `create_category()`: capture `now = datetime.now(tz=timezone.utc)`; pass `created_at=now, updated_at=now` when constructing `Category`; update `update_category()`: capture `now` and assign `category.updated_at = now` before `save_category()` (depends on T009); run `pytest tests/test_audit_fields_service.py` → confirm PASS
- [ ] T011 [US1] In `taxomesh/application/service.py` — apply the same changes as T010 to `create_item()` and `update_item()` (same file, depends on T010); run `pytest tests/test_audit_fields_service.py` → confirm all timestamp tests PASS
- [ ] T012 [P] [US1] Write and verify test in `tests/test_audit_fields_domain.py`:
  - `test_category_legacy_deserialization_missing_timestamps()` — constructs `Category.model_validate({"category_id": ..., "name": "X"})` (no `created_at`/`updated_at`) and asserts both fields equal `AUDIT_EPOCH`
  - `test_item_legacy_deserialization_missing_timestamps()` — same for `Item`
  - Run `pytest tests/test_audit_fields_domain.py` → confirm PASS (model defaults apply without service involvement)
- [ ] T013 [P] [US1] Write and verify Django round-trip test in `tests/test_audit_fields_django.py`:
  - `test_django_category_timestamps_roundtrip()` — saves a `Category` with explicit `created_at`/`updated_at` via `DjangoRepository.save_category()`, reloads via `get_category()`, asserts timestamps are equal
  - `test_django_item_timestamps_roundtrip()` — same for `Item`
  - Run `pytest tests/test_audit_fields_django.py` → confirm PASS
- [ ] T014 [P] [US1] Write and verify JSON persistence round-trip test in `tests/test_audit_fields_service.py`:
  - `test_json_category_timestamps_roundtrip()` — uses service backed by `JsonRepository` with `tmp_path`; creates a category, reloads the same `JsonRepository` from the same path, retrieves the category, asserts `created_at` and `updated_at` are preserved (covers FR-012 and SC-001 for JSON backend)
  - `test_json_item_timestamps_roundtrip()` — same for `Item`
  - Run `pytest tests/test_audit_fields_service.py` → confirm PASS

**Checkpoint**: User Story 1 fully functional. `created_at` / `updated_at` are stamped by the
service, persisted by all backends (JSON verified + Django verified), and legacy records
deserialize cleanly.

---

## Phase 4: User Story 2 — Track Modification Count via Version (Priority: P2)

**Goal**: `create_category` / `create_item` set `version = 0`. Each call to `update_category` /
`update_item` increments `version` by exactly 1. Version persists through round-trips and
is recoverable from storage for all backends.

**Independent Test**: Create a category — assert `version == 0`. Call `update_category` twice —
assert `version == 2`. Deserialize a legacy JSON dict without `version` — assert `version == 0`.

### Tests for User Story 2 ⚠️ Write FIRST — partial FAIL expected before T016

> **Note**: After Phase 2, the model's `DEFAULT_VERSION = 0` is already in place.
> `test_create_*_version_is_zero()` tests will therefore **PASS immediately** — they verify the
> correct model default, not service behavior. Only `test_update_*_increments_version()` will
> **FAIL** until T016/T017 implement the service increment. Run both groups and confirm this
> split behavior before proceeding.

- [ ] T015 [US2] Write tests in `tests/test_audit_fields_service.py`:
  - `test_create_category_version_is_zero()` — asserts `category.version == 0`; **expected to PASS** immediately (model default); confirms default is correctly wired
  - `test_update_category_increments_version()` — asserts `version` becomes `1` after first update, `2` after second; **expected to FAIL** (service does not increment yet)
  - `test_create_item_version_is_zero()` — **expected to PASS** immediately
  - `test_update_item_increments_version()` — **expected to FAIL**
  - Run `pytest tests/test_audit_fields_service.py -k version` → confirm create-tests PASS, update-increment tests FAIL

### Implementation for User Story 2

- [ ] T016 [US2] In `taxomesh/application/service.py` — `create_category()` already produces `version=0` via model default; add `category.version += 1` to `update_category()` before `save_category()` (depends on T015); run `pytest tests/test_audit_fields_service.py -k version` → confirm Category version tests all PASS
- [ ] T017 [US2] In `taxomesh/application/service.py` — add `item.version += 1` to `update_item()` before `save_item()` (same file, depends on T016); run `pytest tests/test_audit_fields_service.py` → confirm all version tests PASS
- [ ] T018 [P] [US2] Write and verify test in `tests/test_audit_fields_domain.py`:
  - `test_category_legacy_deserialization_missing_version()` — `Category.model_validate({"category_id": ..., "name": "X"})` asserts `version == 0`
  - `test_item_legacy_deserialization_missing_version()` — same
  - Run `pytest tests/test_audit_fields_domain.py` → confirm PASS
- [ ] T019 [P] [US2] Write and verify Django round-trip test in `tests/test_audit_fields_django.py`:
  - `test_django_category_version_roundtrip()` — saves a `Category` with `version=3`, reloads, asserts `version == 3`
  - `test_django_item_version_roundtrip()` — same
  - Run `pytest tests/test_audit_fields_django.py` → confirm PASS
- [ ] T020 [P] [US2] Write and verify JSON persistence round-trip test in `tests/test_audit_fields_service.py`:
  - `test_json_category_version_roundtrip()` — uses service backed by `JsonRepository` with `tmp_path`; updates a category twice, reloads the repository from disk, asserts `version == 2` (covers FR-012 and SC-001 for JSON backend)
  - `test_json_item_version_roundtrip()` — same for `Item`
  - Run `pytest tests/test_audit_fields_service.py` → confirm PASS

**Checkpoint**: User Stories 1 AND 2 both fully functional and independently tested across
all repository backends.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, invariant coverage, edge-case verification.

- [ ] T021 Add edge-case test to `tests/test_audit_fields_service.py`:
  - `test_structural_operations_do_not_bump_version()` — creates an item, assigns it to a category (structural), reloads item, asserts `version == 0` and `updated_at == created_at`
  - Run `pytest tests/test_audit_fields_service.py` → confirm PASS
- [ ] T022 Add invariant test to `tests/test_audit_fields_service.py`:
  - `test_created_at_never_changes_after_multiple_updates()` — captures `original_created_at` at creation, performs 3 updates, asserts `created_at` equals `original_created_at` throughout
  - Run `pytest tests/test_audit_fields_service.py` → confirm PASS
- [ ] T023 Run full quality gate suite: `ruff check .` → `ruff format --check .` → `mypy --strict .` → `pytest --cov=taxomesh --cov-fail-under=80`; fix any failures before proceeding

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS both user stories
  - T002 → T003, T004, T005 (T003 and T004 parallel; T005 parallel with T003/T004 but targets different file)
  - T005 → T006 (migration requires ORM model definition)
  - T003, T005 → T007 (repository needs both domain model and ORM model)
  - T004, T005 → T008
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion — T009 → T010 → T011 (sequential); T012, T013, T014 parallel with T010/T011
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion — T015 → T016 → T017 (sequential); T018, T019, T020 parallel with T016/T017
- **Polish (Phase 5)**: Depends on Phase 3 and Phase 4 completion — T021 → T022 → T023 (sequential; all write to same file)

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational (Phase 2) — no dependency on US2
- **US2 (P2)**: Starts after Foundational (Phase 2) — no dependency on US1 (but shares `service.py`; sequential in practice for a single developer)

### Parallel Opportunities

Within Phase 2: T003, T004, T005 can be run in parallel (different files — domain models and Django models have no cross-dependency at authoring time).

Within Phase 3: T012 (legacy deserialization tests), T013 (Django round-trip tests), and T014 (JSON round-trip tests) can be worked after Phase 2 independently of T010/T011.

Within Phase 4: T018, T019, T020 can be worked in parallel after T015.

---

## Parallel Example: Phase 2 (Foundational)

```text
# After T002 (constants) is done, these three can proceed in parallel:
Task T003: Add fields to Category model     → taxomesh/domain/models/category.py
Task T004: Add fields to Item model         → taxomesh/domain/models/item.py
Task T005: Add columns to Django ORM models → taxomesh/contrib/django/models.py

# After T005:
Task T006: Django migration 0009            → taxomesh/contrib/django/migrations/

# After T003 + T005:
Task T007: DjangoRepository Category methods → taxomesh/adapters/repositories/django_repository.py

# After T004 + T005:
Task T008: DjangoRepository Item methods     → taxomesh/adapters/repositories/django_repository.py
# Note: T007 and T008 are the same file — execute sequentially
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002–T008) — CRITICAL, blocks all work
3. Complete Phase 3: User Story 1 (T009–T014) — timestamps working end-to-end across all backends
4. **STOP and VALIDATE**: run `pytest tests/test_audit_fields_service.py tests/test_audit_fields_domain.py tests/test_audit_fields_django.py`
5. Demo: create/update a category and inspect timestamps

### Incremental Delivery

1. Phase 1 + Phase 2 → model layer ready (no service behavior yet)
2. Phase 3 → timestamps working across all backends → MVP demo
3. Phase 4 → version tracking added → full feature
4. Phase 5 → quality gates green → ready for PR

---

## Notes

- [P] tasks target different files; no shared-state conflicts
- TDD required: implementation tasks are preceded by test tasks; update-tests must FAIL before implementation
- US2 create-version tests will PASS before implementation (model default = 0); only update-increment tests fail (see T015 note)
- `service.py` changes in T010, T011, T016, T017 all touch the same file — execute strictly sequentially
- T021 and T022 both write to `tests/test_audit_fields_service.py` — execute sequentially
- Django migration (T006) must be generated after ORM model changes (T005) are complete
- JSON and YAML repositories need no code changes — Pydantic handles `datetime` serialization automatically
- Commit after each phase checkpoint (Phase 2, Phase 3, Phase 4, Phase 5)
