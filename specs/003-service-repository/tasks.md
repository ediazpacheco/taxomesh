# Tasks: Service Layer and Pluggable Storage (003-service-repository)

**Input**: `specs/003-service-repository/` — plan.md, spec.md, data-model.md, contracts/python-api.md, research.md, quickstart.md
**Branch**: `003-service-repository`

**Organization**: Tasks are grouped by user story (US1–US6 from spec.md) to enable
independent implementation and testing of each story. US4 (custom backend) is
validated implicitly by US1–US3 tests, which all use `InMemoryRepository` without inheritance.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-flight tasks)
- **[Story]**: Which user story this task belongs to
- Write tests before running implementation for each story

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create all package directories and empty `__init__.py` stub files so
Python can resolve every new module path. No logic is added here.

- [x] T001 Create package skeleton — `__init__.py` stubs for `taxomesh/ports/`, `taxomesh/application/`, `taxomesh/adapters/`, `taxomesh/adapters/repositories/`, and `tests/service/`

**Checkpoint**: All new module paths resolve; `import taxomesh.ports` succeeds without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure that every user story depends on.
No user story work can begin until this phase is complete.

- [x] T002 [P] Create `taxomesh/exceptions.py` — 8-class `TaxomeshError` hierarchy: `TaxomeshError`, `TaxomeshNotFoundError`, `TaxomeshCategoryNotFoundError`, `TaxomeshItemNotFoundError`, `TaxomeshTagNotFoundError`, `TaxomeshValidationError`, `TaxomeshCyclicDependencyError`, `TaxomeshRepositoryError`; Google docstrings on module and each class
- [x] T003 [P] Create `taxomesh/ports/repository.py` — `TaxomeshRepositoryBase` as `typing.Protocol` (no `@runtime_checkable`): 15 methods — category (save/get/list/delete), item (save/get/list/delete), tag (save/get/list), tag-item association (assign_tag, remove_tag), category parent links (save_category_parent_link, list_category_parent_links); Google docstrings on module, class, and all methods
- [x] T004 Create `taxomesh/domain/dag.py` — `check_no_cycle(category_id, parent_id, existing_links)` using DFS to detect cycles before any parent link is persisted; `_can_reach` helper; imports `CategoryParentLink` from domain models and `TaxomeshCyclicDependencyError` from exceptions; Google docstrings on module and all functions
- [x] T005 Create `taxomesh/application/service.py` — `TaxomeshService` skeleton: module docstring, class docstring, `__init__(self, repository: TaxomeshRepositoryBase | None = None)` that lazy-imports `JsonRepository` and stores `self._repo`; no service methods yet
- [x] T006 Create `tests/service/conftest.py` — `InMemoryRepository` (implements all 15 Protocol methods with no inheritance, including `save_category_parent_link` and `list_category_parent_links`); `service` pytest fixture returning `TaxomeshService(repository=InMemoryRepository())`; `tmp_json_path` pytest fixture (tmp_path-backed `.json` path, for US5)

**Checkpoint**: `uv run pytest tests/service/` collects 0 tests without errors; mypy passes on new files.

---

## Phase 3: User Story 1 — Category management (Priority: P1) 🎯 MVP

**Goal**: A developer can create, retrieve, list, and delete categories exclusively through
`TaxomeshService`. All not-found conditions raise typed errors.

**Independent Test**: Construct a service with `InMemoryRepository`, run create → get → list → delete, verify outcomes without inspecting storage internals.

- [x] T007 [P] [US1] Write `tests/service/test_service_categories.py` — tests covering all 6 acceptance scenarios: happy-path create/get/list/delete, `TaxomeshCategoryNotFoundError` on get of missing, `TaxomeshCategoryNotFoundError` on delete of missing; use `service` fixture from conftest
- [x] T008 [US1] Add category methods to `taxomesh/application/service.py` — `create_category(name, description, metadata)`, `get_category(category_id)`, `list_categories()`, `delete_category(category_id)`; generate `uuid4()` for `category_id` in `create_category`; Google docstrings on all methods

**Checkpoint**: `uv run pytest tests/service/test_service_categories.py` passes; US1 is independently functional.

---

## Phase 4: User Story 2 — Item management (Priority: P1)

**Goal**: A developer can create, retrieve, list, and delete items (with external IDs of type
`UUID | str | int`) exclusively through `TaxomeshService`.

**Independent Test**: Construct a service with `InMemoryRepository`, create items with varied `external_id` types, verify retrieve/list/delete outcomes and not-found errors.

- [x] T009 [P] [US2] Write `tests/service/test_service_items.py` — tests covering all 6 acceptance scenarios: happy-path create/get/list/delete with `ExternalId` variants (UUID, str, int), `TaxomeshItemNotFoundError` on get/delete of missing; use `service` fixture
- [x] T010 [US2] Add item methods to `taxomesh/application/service.py` — `create_item(external_id, metadata)`, `get_item(item_id)`, `list_items()`, `delete_item(item_id)`; `item_id` auto-generated by `Item` model; Google docstrings

**Checkpoint**: `uv run pytest tests/service/test_service_items.py` passes; US2 is independently functional.

---

## Phase 5: User Story 3 — Tag management (Priority: P2)

**Goal**: A developer can create tags and assign/remove them from items. Assignment is
idempotent; removal of a non-existent association is a no-op. Not-found conditions raise typed errors.

**Independent Test**: Construct a service, create a tag and an item, assign the tag, verify idempotent assign, remove the tag, verify no-op remove; verify not-found errors for missing entities.

- [x] T011 [P] [US3] Write `tests/service/test_service_tags.py` — tests covering all 5 acceptance scenarios: create tag, assign tag to item (success), idempotent assign (no duplicate, no error), remove tag (success), `TaxomeshTagNotFoundError` / `TaxomeshItemNotFoundError` on assign/remove with missing entity; use `service` fixture
- [x] T012 [US3] Add tag methods to `taxomesh/application/service.py` — `create_tag(name, metadata)`, `assign_tag(tag_id, item_id)`, `remove_tag(tag_id, item_id)`; generate `uuid4()` for `tag_id`; validate tag and item existence before association; Google docstrings

**Checkpoint**: `uv run pytest tests/service/test_service_tags.py` passes; US3 is independently functional.

---

## Phase 6: User Story 4 — Custom storage backend (Priority: P2)

**Goal**: Confirm that `TaxomeshService` accepts any Protocol-conforming object at
construction with no inheritance required, and that all storage is delegated to the backend.

**Independent Test**: The `InMemoryRepository` used in all prior tests has no `TaxomeshRepositoryBase` in its MRO — this is the structural typing proof. Add an explicit assertion and a delegation test.

- [x] T013 [US4] Write `tests/service/test_custom_backend.py` — assert `InMemoryRepository` is NOT a subclass of any taxomesh class; assert that `TaxomeshService(repository=InMemoryRepository())` delegates all writes to the provided backend (create an item, verify the item appears in the InMemoryRepository's internal state)

**Checkpoint**: `uv run pytest tests/service/test_custom_backend.py` passes.

---

## Phase 7: User Story 5 — JSON persistence across restarts (Priority: P2)

**Goal**: Data survives process restarts when `JsonRepository` is used. Atomic writes ensure
the file is never in a corrupt partial state after a write.

**Independent Test**: Write data via a `TaxomeshService` backed by `JsonRepository`, destroy the service object, create a new service reading the same file, verify all records are present.

- [x] T014 [P] [US5] Write `tests/service/test_json_repository.py` — tests covering all 4 acceptance scenarios: auto-create file on init (missing file), persistence across restart (write + re-load), flush-after-write (file reflects each mutation), corrupt-file error (`TaxomeshRepositoryError` raised at construction); use `tmp_json_path` fixture
- [x] T015 [P] [US5] Create `taxomesh/adapters/repositories/json_repository.py` — `JsonRepository`: in-memory dicts for categories/items/tags and lists for links (`_links`, `_category_parent_links`); `__init__` creates or loads from file, raises `TaxomeshRepositoryError` on parse error; `_flush()` writes atomically via `tempfile.mkstemp(dir=path.parent, suffix=".tmp")` + `os.fsync(fd)` + `os.replace()`; all 15 Protocol methods mutate in-memory state then call `_flush()`; JSON key `"category_parent_links"` for parent links; Google docstrings on module, class, `_flush`, and all public methods

**Checkpoint**: `uv run pytest tests/service/test_json_repository.py` passes; no temp files left behind after tests.

---

## Phase 8: User Story 6 — Category parent relationships with DAG integrity (Priority: P1)

**Goal**: A developer can record parent–child relationships between categories. The service
enforces that no cycle is ever introduced into the category graph.

**Independent Test**: Construct a service with `InMemoryRepository`, add valid parent links,
attempt to close cycles of lengths 1, 2, and 3, and verify `TaxomeshCyclicDependencyError` in all cases. Verify that both categories must exist.

- [x] T016 [P] [US6] Add DAG tests to `tests/service/test_service_categories.py` — tests for all 5 acceptance scenarios: happy-path link creation, 2-node cycle, 3-node cycle, self-loop, missing category raises `TaxomeshCategoryNotFoundError`; use `service` fixture
- [x] T017 [US6] Add `add_category_parent(category_id, parent_id, sort_index=0)` to `taxomesh/application/service.py` — validate both categories exist; call `check_no_cycle(category_id, parent_id, self._repo.list_category_parent_links())`; call `self._repo.save_category_parent_link(link)` and return the `CategoryParentLink`; Google docstring
- [x] T018 [US6] Add category parent link persistence test to `tests/service/test_json_repository.py` — verify that `add_category_parent` links survive a `JsonRepository` process restart (write a link via one service instance, reload from file, confirm the link is present in `list_category_parent_links()`); use `tmp_json_path` fixture

**Checkpoint**: `uv run pytest tests/service/` passes; all DAG-related cycle paths tested end-to-end.

---

## Phase 9: Polish & Integration

**Purpose**: Expose the public surface, validate all quality gates, and prepare commits.

- [x] T019 [P] Update `taxomesh/__init__.py` — add imports: `TaxomeshService` from `application.service`; all 8 exception classes from `exceptions`; update `__all__` with full list; module docstring if not present
- [x] T020 [P] Write `tests/test_exceptions.py` — 10 tests covering exception hierarchy membership, raise/catch behaviour, message preservation, and mutual exclusivity of sibling classes; includes `TaxomeshCyclicDependencyError` hierarchy and integration with `add_category_parent`
- [x] T021 Run all quality gates and confirm they pass:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy --strict .`
  - `uv run pytest --cov=taxomesh --cov-fail-under=80`
- [ ] T022 Propose commits — spec artifacts commit (`specs/003-service-repository/`) and source code commit (all new/modified `taxomesh/` files and `tests/` files)

**Checkpoint**: All four quality gates green; coverage ≥ 80%; ready to merge.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
  - T002, T003, T004 are parallel (different files)
  - T005 depends on T002 + T003 + T004
  - T006 depends on T003 + T005
- **US1–US3, US6 (Phases 3–5, 8)**: All depend on Phase 2 completion
  - Tests [P] and implementation can proceed in parallel within each story (different files)
  - US1 → US2 → US3 must be sequential for `service.py` (same file, sequential appends)
  - US6 tests [P] can run alongside other test files; US6 service method sequential after US3
- **US4 (Phase 6)**: Depends on Phase 2 + at least US1 tests in place
- **US5 (Phase 7)**: Depends on Phase 2; test (T014) and implementation (T015) are parallel
- **Polish (Phase 9)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: After Foundational — no story dependencies
- **US2 (P1)**: After US1 (both add to `service.py`; must be sequential for that file)
- **US3 (P2)**: After US2 (same reason)
- **US4 (P2)**: After Foundational; adds a test only — can run alongside US3
- **US5 (P2)**: After Foundational; independent of US1–US4
- **US6 (P1)**: After US1 (both add to `service.py`); tests parallel; requires `domain/dag.py`

### Parallel Opportunities

```bash
# Phase 2 — parallel start:
T002  # taxomesh/exceptions.py
T003  # taxomesh/ports/repository.py
T004  # taxomesh/domain/dag.py

# Within US1 — parallel (different files):
T007  # tests/service/test_service_categories.py
T008  # taxomesh/application/service.py (categories)

# Within US5 — parallel (different files):
T014  # tests/service/test_json_repository.py
T015  # taxomesh/adapters/repositories/json_repository.py
```

---

## Implementation Strategy

### MVP (User Stories 1 + 2 + 6 — core taxonomy functionality)

1. Phase 1: Setup
2. Phase 2: Foundational (including `domain/dag.py`)
3. Phase 3: US1 (categories)
4. Phase 4: US2 (items)
5. Phase 8: US6 (category parent links + DAG integrity)
6. **STOP and validate**: stories work independently via `InMemoryRepository`
7. Phase 9: Quality gates + commit

### Full Delivery

1. Setup → Foundational → US1 → US2 → US3 → US4 → US5 → US6 → Polish
2. Each user story is independently testable after its phase completes

---

## Notes

- `[P]` tasks touch different files and have no dependency on in-flight tasks in the same phase
- `InMemoryRepository` in `conftest.py` has **no** `TaxomeshRepositoryBase` in its MRO — this is the proof of structural typing (Principle III)
- `JsonRepository` is lazy-imported inside `TaxomeshService.__init__` so US1–US4 tests never trigger the import
- `check_no_cycle` in `domain/dag.py` is pure (no I/O, no side effects) — passes all existing links, not a subset
- Google docstrings are required on every module and public method (Constitution v1.2.0)
- `mypy --strict` must pass at every checkpoint — do not defer type errors
