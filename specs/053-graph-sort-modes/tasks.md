# Tasks: Pluggable Graph Sort Modes

**Input**: Design documents from `/specs/053-graph-sort-modes/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: TDD is mandatory per CLAUDE.md — all test tasks MUST be written and confirmed failing before their corresponding implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: No new project or tooling setup is required. This phase is intentionally empty —
the feature modifies existing files within an established project.

*(No tasks — proceed to Phase 2)*

---

## Phase 2: Foundational — Extract shared TypedDicts (blocking prerequisite)

**Purpose**: Move `GraphEntry` and `RelationEntry` from `admin.py` to a new `graph_types.py`
module. This must be complete before `graph_sort.py` can be created, since the sort callables
must reference `GraphEntry` without creating a circular import.

**⚠️ CRITICAL**: All Phase 3+ work is blocked until this phase is complete.

- [x] T001 Write regression test confirming `GraphEntry` and `RelationEntry` are still importable from `taxomesh.contrib.django.admin` after the move in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T002 Create `taxomesh/contrib/django/graph_types.py` with `GraphEntry` and `RelationEntry` TypedDicts moved verbatim from `admin.py`
- [x] T003 Update `taxomesh/contrib/django/admin.py` to import `GraphEntry` and `RelationEntry` from `graph_types` (remove the TypedDict bodies; keep re-export or direct import)

**Checkpoint**: `mypy --strict .` and `pytest` must pass with zero behaviour change before proceeding.

---

## Phase 3: User Story 1 — Sort selector in the admin graph (Priority: P1) 🎯 MVP

**Goal**: Admin user can switch the graph sort order via a `<select>` toolbar. Both the root view and the lazy-load children AJAX endpoint respect the active sort mode.

**Independent Test**: Navigate to `/admin/…/graph/`, change the sort selector, verify entries reorder. Expand a category, verify children use the same sort mode.

### Tests for User Story 1 ⚠️ Write first — confirm failing before T010

- [x] T004 [US1] Write test `test_sort_index_asc_builtin` — verify `sort_index_asc` returns entries in ascending `sort_index` order in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T005 [P] [US1] Write test `test_sort_index_desc_builtin` — verify `sort_index_desc` returns entries in descending `sort_index` order in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T006 [P] [US1] Write test `test_default_sort_modes_registry` — verify `DEFAULT_SORT_MODES` has exactly 2 entries with keys `sort_index_asc` and `sort_index_desc` in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T007 [US1] Write test `test_graph_view_default_sort` — verify GET `/graph/` with no `sort_by` param returns entries sorted by `sort_index` ascending in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T008 [P] [US1] Write test `test_graph_view_sort_desc` — verify GET `/graph/?sort_by=sort_index_desc` returns entries sorted descending in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T009 [P] [US1] Write test `test_graph_children_sort_propagated` — verify GET `/graph/children/?parent_uuid=…&sort_by=sort_index_desc` applies descending sort to child entries in `tests/contrib/django/test_admin_graph_sort_modes.py`

### Implementation for User Story 1

- [x] T010 [US1] Create `taxomesh/contrib/django/graph_sort.py` with `SortModeFn`, `SortMode` type aliases, `DEFAULT_SORT_MODE: Final[str]`, `sort_index_asc`, `sort_index_desc` callables, and `DEFAULT_SORT_MODES: Final[list[SortMode]]`
- [x] T011 [US1] Add `sort_modes: list[SortMode]` class attribute and `_resolve_sort_fn` method to the graph admin mixin in `taxomesh/contrib/django/admin.py` (depends on T010)
- [x] T012 [US1] Integrate `sort_by` query param reading and sort application in `graph_view` in `taxomesh/contrib/django/admin.py`; add `sort_by` and `sort_mode_options` (list of `{"key", "label"}` dicts) to template context (depends on T011)
- [x] T013 [US1] Integrate `sort_by` query param reading and sort application in `graph_children_view` in `taxomesh/contrib/django/admin.py` (depends on T011)
- [x] T014 [US1] Add sort selector `<form method="get">` toolbar above the graph container using `sort_mode_options` context in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`; add `data-sort-by="{{ sort_by }}"` attribute to `<div id="taxomesh-graph">` (depends on T012)
- [x] T015 [US1] Update JS `fetch` call for children AJAX to read `graph.dataset.sortBy` and append `&sort_by=…` to the request URL in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html` (depends on T014)

**Checkpoint**: All T004–T009 tests must now pass. US1 is fully functional and independently testable.

---

## Phase 4: User Story 2 — Consumer registers a custom sort mode (Priority: P2)

**Goal**: A consumer subclass can append a `(key, label, callable)` 3-tuple to `sort_modes`; the custom mode appears in the UI and its callable is invoked when selected. taxomesh internals are not modified.

**Independent Test**: Define a subclass with a custom sort mode; verify it appears in `sort_mode_options` context and that selecting it causes `_resolve_sort_fn` to return the consumer's callable.

### Tests for User Story 2 ⚠️ Write first — confirm failing before T019

- [x] T016 [US2] Write test `test_resolve_sort_fn_known_key` — verify `_resolve_sort_fn("sort_index_desc")` returns the `sort_index_desc` callable (built-in registry lookup) in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T016b [US2] Write test `test_consumer_sort_mode_appears_in_context` — verify that a subclass with a custom `sort_modes` entry produces `sort_mode_options` containing the custom label in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T017 [P] [US2] Write test `test_consumer_sort_callable_invoked` — verify `_resolve_sort_fn` returns the consumer's callable when its key is the active `sort_by` in `tests/contrib/django/test_admin_graph_sort_modes.py`
- [x] T018 [P] [US2] Write test `test_resolve_sort_fn_unknown_key_fallback` — verify `_resolve_sort_fn("nonexistent")` returns the `sort_index_asc` callable (first registered mode) in `tests/contrib/django/test_admin_graph_sort_modes.py`

### Implementation for User Story 2

- [x] T019 [US2] Verify `_resolve_sort_fn` (T011) already handles the unknown-key fallback and consumer extension correctly — no code change expected; task is to run T016–T018 to green. If any fail, fix `_resolve_sort_fn` in `taxomesh/contrib/django/admin.py`

**Checkpoint**: All T016–T018 tests must pass. Consumer extension works without modifying taxomesh internals.

---

## Phase 5: User Story 3 — Default behavior unchanged (Priority: P3)

**Goal**: An existing consumer with no `sort_modes` override sees graph entries sorted by `sort_index` ascending — identical to pre-feature behavior. No configuration change required.

**Independent Test**: Run graph view with no `sort_by` query param; confirm entry order matches `sort_index` ascending.

### Tests for User Story 3 ⚠️ Write first — confirm failing before implementation

- [x] T020 [US3] Write test `test_no_regression_default_order` — verify that with no `sort_by` param the graph view entry order is `sort_index` ascending (same as pre-feature contract) in `tests/contrib/django/test_admin_graph_sort_modes.py`

### Implementation for User Story 3

- [x] T021 [US3] No code change expected — US3 is covered by the `DEFAULT_SORT_MODE` fallback in T012/T013. Task is to run T020 to green. If it fails, adjust the fallback logic in `taxomesh/contrib/django/admin.py`

**Checkpoint**: All T020 tests pass. No regression from pre-feature behaviour.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T022 Run full quality gates: `ruff check .` + `ruff format --check .` + `mypy --strict .` + `pytest --cov=taxomesh --cov-fail-under=80` — fix any issues found
- [x] T023 [P] Verify SC-005 agnosticism: `grep -r "relevance\|content_relevance" taxomesh/` must return zero matches — taxomesh source contains no reference to consumer-specific sort concepts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Foundational completion — BLOCKED until T001–T003 pass
- **US2 (Phase 4)**: Depends on US1 completion (T010–T015 must be done — consumer extension builds on the `sort_modes` attribute and `_resolve_sort_fn`)
- **US3 (Phase 5)**: Depends on US1 completion (same underlying mechanism)
- **Polish (Phase 6)**: Depends on all user story phases passing

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational. No dependency on US2 or US3.
- **US2 (P2)**: Logically depends on US1 (`sort_modes` attr and `_resolve_sort_fn` established in US1).
- **US3 (P3)**: Logically depends on US1 (tests the default fallback path introduced in US1).

### Within Each User Story

- Tests MUST be written and confirmed failing before implementation begins
- T010 (`graph_sort.py`) must precede T011 (`sort_modes` attr on admin)
- T011 must precede T012 and T013 (view integration)
- T012 must precede T014 (template needs context vars from view)
- T014 must precede T015 (JS reads `data-sort-by` set by T014)

### Parallel Opportunities

Within Phase 3 tests: T005 + T006 + T008 + T009 can all be written in parallel (same file, no dependency between them)
Within Phase 4 tests: T017 + T018 can be written in parallel
Within Phase 3 implementation: T010 can proceed as soon as T002–T003 are done

---

## Parallel Example: User Story 1 Tests

```bash
# Write all of these in the same session — all go in the same test file,
# all test the same module (graph_sort.py + admin.py views):
T004: test_sort_index_asc_builtin
T005: test_sort_index_desc_builtin       ← parallel with T004
T006: test_default_sort_modes_registry   ← parallel with T004, T005
T007: test_graph_view_default_sort
T008: test_graph_view_sort_desc          ← parallel with T007
T009: test_graph_children_sort_propagated ← parallel with T007, T008
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 2: Foundational (T001–T003) — ~30 min
2. Write failing tests T004–T009
3. Implement T010–T015
4. **STOP and VALIDATE**: Run pytest + browser smoke test — sort selector works end-to-end
5. US2 and US3 are incremental additions on top

### Incremental Delivery

1. Foundation + US1 → sort selector works for all users (default consumer behaviour)
2. US2 tests + verification → consumer extension is proven correct
3. US3 regression → explicit backward-compat guarantee
4. Polish → quality gate sign-off

---

## Notes

- [P] tasks are in the same file but have no ordering dependency on each other
- All test tasks are written in a single new file: `tests/contrib/django/test_admin_graph_sort_modes.py`
- No new migrations, no new Django models — purely in-process types and view logic
- `graph_types.py` extraction (Phase 2) is the only refactor; it must not change any observable behaviour
- `sort_mode_options` (list of dicts) is passed to the template instead of raw `sort_modes` (list of 3-tuples) because Django templates cannot unpack tuples in `{% for %}` loops
