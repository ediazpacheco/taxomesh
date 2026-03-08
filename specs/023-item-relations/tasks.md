# Tasks: Item-to-Item Relations (ItemRelationLink)

**Input**: Design documents from `/specs/023-item-relations/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per project constitution. Every implementation task has a
preceding test task. Write the test first, verify it fails, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Baseline Verification)

**Purpose**: Confirm the existing quality gates pass before any changes are introduced.
This provides a clean baseline and catches any pre-existing issues.

- [x] T001 Run full quality gate suite (`ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`) and confirm all pass before any changes

**Checkpoint**: All gates green — safe to begin foundational work

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain infrastructure shared by all user stories. Nothing in Phase 3+ can
start until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T002 Add `TaxomeshRelationError(TaxomeshValidationError)` leaf exception to `taxomesh/exceptions.py`
- [x] T003 [P] Export `TaxomeshRelationError` in `taxomesh/__init__.py` (add to `__all__`)
- [x] T004 [P] Add `DIRECTION_OUTGOING: Final[str]`, `DIRECTION_INCOMING: Final[str]`, and `RELATION_TYPE_MAX_LENGTH: Final[int]` constants to `taxomesh/domain/constants.py`
- [x] T005 Write failing unit tests for `ItemRelationLink` domain model validation (self-relation rejection, empty `relation_type` rejection, valid construction, and **case normalisation**: `"COVERS"` is stored and returned as `"covers"`; `"  Covers  "` stripped+lowercased becomes `"covers"`) in `tests/unit/test_item_relation_link_model.py` — **verify tests FAIL before T006**
- [x] T006 Create `ItemRelationLink` Pydantic model with field validators and `model_validator` enforcing: (1) no self-relation, (2) `relation_type` normalised to lowercase via `.strip().lower()` before non-emptiness check (FR-004b), (3) non-empty after normalisation in `taxomesh/domain/models/item_relation_link.py` — run T005 tests and confirm they pass
- [x] T007 Export `ItemRelationLink` from `taxomesh/domain/models/__init__.py`
- [x] T008 Add `save_item_relation_link`, `list_item_relation_links`, and `delete_item_relation_link` method stubs (with `...`) to `TaxomeshRepositoryBase` protocol in `taxomesh/ports/repository.py`

**Checkpoint**: Foundation ready — domain model, exception, constants, and protocol stubs
all exist. User story phases can now begin.

---

## Phase 3: User Stories 1 & 2 — Service API: Relate and Query (Priority: P1) 🎯 MVP

**Goal**: Enable creating directed relations between two items and querying them by item,
direction, and optional type filter. This is the full core API (`relate_items`,
`list_item_relations`, `list_related_items`).

**Independent Test**: Create two items, call `service.relate_items(...)`, then verify the
relation is returned by `service.list_item_relations(...)` and the related item is returned
by `service.list_related_items(...)`.

### Tests for User Stories 1 & 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (T010–T015)**

- [x] T009 [US1] Write failing integration tests covering: upsert semantics, outgoing/incoming direction filtering, `relation_type` filter, non-existent item raises `TaxomeshItemNotFoundError`, self-relation raises `TaxomeshRelationError`, empty `relation_type` raises `TaxomeshRelationError`, **case normalisation** (`relate_items(..., "COVERS")` stores `"covers"`; subsequent `list_item_relations(..., relation_type="covers")` returns it) in `tests/integration/test_service_item_relations.py` — **verify tests FAIL before T015**

### Implementation for User Stories 1 & 2

- [x] T010 [P] [US1] Add `_item_relation_links: list[ItemRelationLink]` in-memory store, implement `save_item_relation_link` (upsert on triple key; `relation_type` is already normalised to lowercase by the domain model before reaching the repository) and `list_item_relation_links` (filter by direction + optional type), and update `_to_dict` / `_from_dict` serialization to include `"item_relation_links"` key (missing key on load → empty list for backward compat) in `taxomesh/adapters/repositories/json_repository.py`
- [x] T011 [P] [US1] Add same `_item_relation_links` store, implement `save_item_relation_link` (upsert on triple key; `relation_type` already normalised by domain model) and `list_item_relation_links`, and update YAML serialization to include `item_relation_links` key (missing key on load → empty list for backward compat) in `taxomesh/adapters/repositories/yaml_repository.py`
- [x] T012 [US1] Add `ItemRelationLinkModel` Django ORM model with `source_item` FK (CASCADE, `related_name="outgoing_relations"`), `target_item` FK (CASCADE, `related_name="incoming_relations"`), `relation_type` CharField, `sort_index` IntegerField (default 0), `metadata` JSONField (default dict), `unique_together = [("source_item", "target_item", "relation_type")]`, and `ITEM_RELATION_LINK_TABLE` table name constant to `taxomesh/contrib/django/models.py`
- [x] T013 [US1] Create Django migration for `ItemRelationLinkModel` in `taxomesh/contrib/django/migrations/0003_item_relation_link.py`
- [x] T014 [US1] Implement `save_item_relation_link` (upsert via `update_or_create` on triple key; `relation_type` is already normalised to lowercase by the domain model before reaching the repository) and `list_item_relation_links` (filter on `source_item_id` or `target_item_id` by direction) in `taxomesh/adapters/repositories/django_repository.py`
- [x] T015 [US1] Implement `relate_items`, `list_item_relations`, and `list_related_items` on `TaxomeshService` in `taxomesh/application/service.py` — validate both items exist before persisting; raise `TaxomeshItemNotFoundError` if not found; run T009 tests and confirm they pass

**Checkpoint**: US1 & US2 fully functional. `relate_items`, `list_item_relations`, and
`list_related_items` work against all three backends.

---

## Phase 4: User Story 3 — Remove a Relation (Priority: P2)

**Goal**: Enable removing a specific directed relation by its unique triple
`(source_item_id, target_item_id, relation_type)`.

**Independent Test**: Create a relation, call `service.remove_item_relation(...)`, verify
the relation is no longer returned by `list_item_relations`. Also verify removing a
non-existent relation raises `TaxomeshRelationError`.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (T017–T020)**

- [x] T016 [US3] Add failing tests for `remove_item_relation`: successful deletion, relation no longer appears in list after deletion, removing non-existent triple raises `TaxomeshRelationError` in `tests/integration/test_service_item_relations.py` — **verify tests FAIL before T020**

### Implementation for User Story 3

- [x] T017 [P] [US3] Implement `delete_item_relation_link` (remove matching triple from `_item_relation_links`, return `True`/`False`) in `taxomesh/adapters/repositories/json_repository.py`
- [x] T018 [P] [US3] Implement `delete_item_relation_link` in `taxomesh/adapters/repositories/yaml_repository.py` (same pattern as T017)
- [x] T019 [US3] Implement `delete_item_relation_link` (use Django `filter(...).delete()` on triple) in `taxomesh/adapters/repositories/django_repository.py`
- [x] T020 [US3] Implement `remove_item_relation` on `TaxomeshService` in `taxomesh/application/service.py` — raises `TaxomeshRelationError` if relation not found; run T016 tests and confirm they pass

**Checkpoint**: US3 complete. Full CRUD cycle works for item relations.

---

## Phase 5: User Story 4 — Cascade Delete on Item Deletion (Priority: P2)

**Goal**: Ensure all relations where a deleted item appears as source or target are
automatically removed when `delete_item` is called.

**Independent Test**: Create item A with outgoing relations to B and incoming relations
from C. Delete A. Verify `list_item_relations(A)` returns empty, and querying B or C for
relations involving A returns empty.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (T022–T023)**

- [x] T021 [US4] Add failing cascade tests: delete source item removes outgoing relations, delete target item removes incoming relations, unrelated items' relations are unaffected in `tests/integration/test_service_item_relations.py` — **verify tests FAIL before T022–T023**

### Implementation for User Story 4

- [x] T022 [P] [US4] Update `delete_item` in `taxomesh/adapters/repositories/json_repository.py` to filter out entries from `_item_relation_links` where `source_item_id == item_id OR target_item_id == item_id` before persisting
- [x] T023 [P] [US4] Update `delete_item` in `taxomesh/adapters/repositories/yaml_repository.py` with the same cascade filter pattern as T022
- (Django cascade is already handled by `on_delete=CASCADE` on both FKs added in T012 — no extra task required)
- [x] T024 [US4] Verify cascade: run T021 tests against all three backends and confirm they pass; verify no regressions in existing `delete_item` tests

**Checkpoint**: US4 complete. Referential integrity is maintained across all backends.

---

## Phase 6: User Story 5 — Persistence Round-trip Tests (Priority: P2)

**Goal**: Verify that relations created in each backend survive a full
serialize → reload cycle with all field values intact.

**Independent Test**: Create relations, trigger a save, instantiate a fresh repository
from the same file/database, and assert all fields match exactly.

### Tests for User Story 5

- [x] T025 [P] [US5] Write JSON backend round-trip tests: create relations, reload `JsonRepository` from the same file path, assert all five fields (`source_item_id`, `target_item_id`, `relation_type`, `sort_index`, `metadata`) match; also assert old files without `"item_relation_links"` load as empty list in `tests/integration/test_json_repository_relations.py`
- [x] T026 [P] [US5] Write YAML backend round-trip tests (same scenarios as T025) in `tests/integration/test_yaml_repository_relations.py`
- [x] T027 [US5] Write Django backend persistence tests: create relations via `DjangoRepository`, query them via ORM, assert fields and unique constraint enforcement in `tests/integration/test_django_repository_relations.py`

**Checkpoint**: US5 complete. Persistence verified for all three backends.

---

## Phase 7: User Story 6 — CLI (Priority: P3)

**Goal**: Expose relation management through a `taxomesh relation` command group with
four subcommands: `add`, `list`, `related`, `delete`.

**Independent Test**: Run each of the four CLI commands in sequence using a temporary
repository; verify correct Rich table output for `list`/`related` and confirmation
messages for `add`/`delete`.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (T029)**

- [x] T028 [US6] Write failing CLI tests using Typer's `CliRunner` or subprocess: `relation add` creates a relation, `relation list` returns tabular output, `relation list --direction incoming` works, `relation related` resolves items, `relation delete` removes the relation in `tests/integration/test_cli_relations.py` — **verify tests FAIL before T029**

### Implementation for User Story 6

- [x] T029 [US6] Add `relation_app = typer.Typer()`, implement `add` (with `--sort-index INT` and repeatable `--metadata KEY=VALUE` option declared as `List[str]`, split on first `=`, merged into `dict[str, str]`), `list` (with `--type TEXT` and `--direction TEXT` options, Rich table output), `related` (with `--type TEXT` and `--direction TEXT` options), `delete` subcommands, and wire with `app.add_typer(relation_app, name="relation")` in `taxomesh/adapters/cli/main.py`; run T028 tests and confirm they pass

**Checkpoint**: US6 complete. All four CLI subcommands are functional.

---

## Phase 8: User Story 7 — Django Admin (Priority: P3)

**Goal**: Surface relation management in Django admin. Outgoing relations editable inline
on source item; incoming relations visible read-only on target item. All writes through
the service layer. Self-relations blocked with a clear validation error.

**Independent Test**: Open an item in Django admin, add an outgoing relation via inline,
save, verify it is persisted. Attempt a self-relation and confirm the admin rejects it.

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (T031–T033)**

- [x] T030 [US7] Write failing Django admin tests: `ItemRelationLinkModelAdmin` registered and list view loads, outgoing inline saves relation via service layer, incoming inline is read-only, self-relation submission returns validation error in `tests/contrib/test_django_admin_relations.py` — **verify tests FAIL before T031–T033**

### Implementation for User Story 7

- [x] T031 [US7] Register `ItemRelationLinkModelAdmin` for `ItemRelationLinkModel` with `list_display = ("source_item", "target_item", "relation_type", "sort_index")`, `search_fields`, and appropriate `list_filter` in `taxomesh/contrib/django/admin.py`
- [x] T032 [US7] Add `OutgoingRelationInline(TaxomeshAdminMixin, admin.TabularInline)` (editable, `fk_name="source_item"`) and `IncomingRelationInline(TaxomeshAdminMixin, admin.TabularInline)` (read-only, `fk_name="target_item"`, `extra=0`, `can_delete=False`, all `readonly_fields`) to `taxomesh/contrib/django/admin.py`; add both to `ItemModelAdmin.inlines`
- [x] T033 [US7] Implement `save_formset` override on `OutgoingRelationInline` (or custom inline form) to route all writes through `TaxomeshService.relate_items` / `remove_item_relation`, and add a `clean` method blocking self-relations with a user-readable `ValidationError` in `taxomesh/contrib/django/admin.py`; run T030 tests and confirm they pass

**Checkpoint**: US7 complete. Django admin surfaces item relations correctly.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates and final quality gate verification.

- [x] T034 [P] Update `README.md` to: document `ItemRelationLink` with Python API examples; add CLI examples for all four `relation` commands; add a Django admin note; add a "when to use categories vs item placement vs tags vs item relations" section
- [x] T035 Run full quality gate suite (`ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`) and confirm all pass with zero errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — run immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **Phase 3 (US1+US2, P1)**: Depends on Phase 2 — start here for MVP
- **Phase 4 (US3, P2)**: Depends on Phase 3 (needs `relate_items` and backends to exist)
- **Phase 5 (US4, P2)**: Depends on Phase 3 (needs backends and service to exist)
- **Phase 6 (US5, P2)**: Depends on Phase 3 (backends must be implemented and serializing)
- **Phase 7 (US6, P3)**: Depends on Phase 3 (CLI wraps service API)
- **Phase 8 (US7, P3)**: Depends on Phase 3 (admin wraps service API) and Phase 4 (needs delete)
- **Phase 9 (Polish)**: Depends on all desired user story phases being complete

### User Story Dependencies

- **US1+US2 (P1)**: Start after Phase 2 — no story dependencies
- **US3 (P2)**: Depends on US1+US2 (needs `relate_items` and backend stores to delete from)
- **US4 (P2)**: Depends on US1+US2 (needs the relation store to exist in backends)
- **US5 (P2)**: Depends on US1+US2 (needs serialization to be implemented)
- **US6 (P3)**: Depends on US1+US2 (wraps service methods); benefits from US3 being complete
- **US7 (P3)**: Depends on US1+US2 and US3 (admin needs full CRUD)

### Within Each Phase

1. Write test task → verify it **fails** → implement → verify it **passes**
2. Within US1+US2: T010/T011 [P] (JSON + YAML backends) can run in parallel; T012 → T013 → T014 are sequential (model → migration → repository); T015 (service) comes last
3. Within US3: T017/T018 [P] (JSON + YAML) can run in parallel; T019 (Django) and T020 (service) are sequential
4. Within US4: T022/T023 [P] can run in parallel (different files)
5. Within US5: T025/T026 [P] can run in parallel; T027 is separate
6. T034 (README) can run in parallel with T035 (quality gates) — different files

---

## Parallel Execution Examples

### Phase 2 (Foundational) — parallel opportunities

```
Immediately parallelizable after T002:
  - T003: Export exception in __init__.py
  - T004: Add constants to domain/constants.py

Sequential chain:
  T002 → T003/T004 [parallel] → T005 → T006 → T007 → T008
```

### Phase 3 (US1+US2) — parallel opportunities

```
After T009 (tests written):
  - T010: json_repository.py  ← parallel
  - T011: yaml_repository.py  ← parallel

Sequential chain:
  T012 → T013 → T014 (model → migration → django_repository)

Final:
  T015: service.py (depends on T010, T011, T014 all complete)
```

### Phase 4–5 (US3+US4) — parallel opportunities

```
US3:  T017 (json) ← parallel with → T018 (yaml)
      Then: T019 (django) → T020 (service)

US4:  T022 (json) ← parallel with → T023 (yaml)
      Then: T024 (verify)

Phases 4 and 5 can run concurrently if two developers available.
```

### Phase 6 (US5) — all tests in parallel

```
  T025 (json round-trip) ← parallel
  T026 (yaml round-trip) ← parallel
  T027 (django persistence) — separate
```

---

## Implementation Strategy

### MVP First (US1+US2 Only)

1. Complete Phase 1: Baseline verification
2. Complete Phase 2: Foundational (domain model, exception, constants, protocol)
3. Complete Phase 3: US1+US2 (service API + all backends)
4. **STOP and VALIDATE**: `service.relate_items` + `service.list_item_relations` + `service.list_related_items` all work
5. Library is already useful for callers — can be released as preview

### Incremental Delivery

1. Phase 1+2 → Foundation ready
2. Phase 3 → MVP: relate + list → validate independently
3. Phase 4 → Add: remove relation → validate independently
4. Phase 5 → Add: cascade delete → validate independently
5. Phase 6 → Add: persistence tests → validate serialization
6. Phase 7 → Add: CLI → validate independently
7. Phase 8 → Add: Django admin → validate independently
8. Phase 9 → README + quality gates → ready for merge

### Parallel Team Strategy

With two developers after Phase 2 completes:

- **Developer A**: Phase 3 (US1+US2) → Phase 4 (US3) → Phase 7 (US6 CLI)
- **Developer B**: Phase 5 (US4 cascade) → Phase 6 (US5 persistence tests) → Phase 8 (US7 admin)

Both developers run Phase 9 together.

---

## Notes

- [P] tasks operate on different files — no edit conflicts
- TDD is mandatory: every test task must FAIL before its implementation task starts
- `delete_item_relation_link` in Django backend returns `bool` from the repository protocol
  but Django ORM returns a `(count, dict)` tuple — unwrap correctly
- The JSON/YAML `_item_relation_links` list stores `ItemRelationLink` objects in memory;
  serialization converts UUIDs to strings (consistent with existing link serialization)
- `IncomingRelationInline` must set `readonly_fields` to all model fields so Django admin
  does not show save/delete controls
- Commit after each phase checkpoint, not necessarily after every task
- Run `pytest --cov=taxomesh --cov-fail-under=80` after Phase 6 to confirm coverage gate
  before proceeding to Phase 7+8
