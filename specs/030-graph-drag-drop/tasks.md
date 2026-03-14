# Tasks: Graph Drag-and-Drop Reordering

**Input**: Design documents from `/specs/030-graph-drag-drop/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: TDD is mandatory per CLAUDE.md. Every implementation task has a preceding failing-test task.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no incomplete dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4 from spec.md)
- Exact file paths are included in every description

---

## Phase 1: Setup (No new setup required)

This feature adds no new packages, migrations, or project structure. All changes are additive on existing files.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Expose `sort_index` and `parent_uuid` on every graph entry so the frontend can scope drag operations. All user story JS depends on these data attributes being present.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T001 Add named constants `GRAPH_REORDER_URL_NAME`, `GRAPH_REPARENT_URL_NAME`, `GRAPH_REORDER_PATH`, `GRAPH_REPARENT_PATH`, `DRAG_KIND_ITEM`, `DRAG_KIND_CATEGORY` as `Final[str]` in `taxomesh/contrib/django/admin.py`
- [X] T002 Extend `GraphEntry` TypedDict with two new fields: `sort_index: int` and `parent_uuid: str` in `taxomesh/contrib/django/admin.py` (depends on T001)
- [X] T003 Update `_flatten_graph()` in `taxomesh/contrib/django/admin.py` to accept `root_uuid: str`, populate `sort_index` from the link record, and populate `parent_uuid` (root_uuid for top-level categories, parent category UUID for all others) (depends on T002)
- [X] T004 Update `graph_view()` in `taxomesh/contrib/django/admin.py` to retrieve the ROOT category UUID from the repository and pass it to `_flatten_graph()` (depends on T003)
- [X] T005 Update `graph.html` to emit `data-uuid="{{ entry.uuid }}"`, `data-parent-uuid="{{ entry.parent_uuid }}"`, and `data-sort-index="{{ entry.sort_index }}"` on each `.taxomesh-entry` div (depends on T002)

**Checkpoint**: Graph entries now carry `data-uuid`, `data-parent-uuid`, `data-sort-index` — prerequisite for all DnD JS.

---

## Phase 3: User Story 1 — Reorder Items Within a Category (Priority: P1) 🎯 MVP

**Goal**: Admin can drag items up/down within a category; sort order is persisted via `ItemParentLink.sort_index`.

**Independent Test**: Create a category with 3 items, drag item C above item A in the graph view, reload the page, verify items appear as C → A → B.

### Tests (write first — must FAIL before implementation)

- [X] T006 [P] [US1] Write failing tests for `reorder_items_in_category` (correct sort_index written, error on unknown category, error on UUID not in category) in `tests/service/test_service_reorder_reparent.py` (new file)
- [X] T007 [P] [US1] Write failing tests for `reorder_view` POST with `kind="item"` (200 on valid body, 400 on missing fields, 400 on unknown UUID, 405 on GET) in `tests/contrib/django/test_admin_graph.py`

### Implementation

- [X] T008 [US1] Implement `reorder_items_in_category(self, category_id: UUID, item_ids_in_order: list[UUID]) -> None` in `taxomesh/application/service.py`: load all ItemParentLinks for category, validate all UUIDs present, reassign sort_index 0,1,2,… and call `save_item_parent_link` for each (depends on T006)
- [X] T009 [US1] Implement `reorder_view(self, request: HttpRequest) -> HttpResponse` in `taxomesh/contrib/django/admin.py`: reject non-POST, parse JSON body, validate `kind`/`parent_uuid`/`ordered_uuids`, call `svc.reorder_items_in_category`, return `JsonResponse({"ok": True})` or error (depends on T007, T008)
- [X] T010 [US1] Register `graph/reorder/` URL with name `GRAPH_REORDER_URL_NAME` inside `get_urls()` in `taxomesh/contrib/django/admin.py` (depends on T009)
- [X] T011 [US1] Add drag handle `<span class="taxomesh-drag-handle">⠿</span>` and `draggable="true"` to item entries in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`; add CSS for `.taxomesh-drag-handle` cursor (depends on T005)
- [X] T012 [US1] Add vanilla JS DnD logic for item sibling reorder to `graph.html`: `dragstart` records dragged node UUID/parentUUID/kind; `dragover` shows insertion indicator within same-parent/same-kind siblings; `drop` collects new ordered_uuids list and POSTs to `graph/reorder/` with CSRF token; on 200 updates DOM order (depends on T010, T011)
- [X] T013 [US1] Add loading-state and error-revert JS to `graph.html`: disable all drag handles during in-flight fetch; on error response revert DOM to pre-drag order and display inline error message; clear error on next dragstart (depends on T012)

**Checkpoint**: Item reorder is fully functional. Drag item within category → persisted → visible after reload. Error reverts visually.

---

## Phase 4: User Story 2 — Reorder Categories Among Siblings (Priority: P2)

**Goal**: Admin can drag category nodes up/down among their siblings; sort order is persisted via `CategoryParentLink.sort_index`.

**Independent Test**: Create a parent category with children A, B, C. Drag B above A in the graph, reload, verify order is B → A → C.

### Tests (write first — must FAIL before implementation)

- [X] T014 [P] [US2] Write failing tests for `reorder_subcategories` (correct sort_index written, error on unknown parent, error on UUID not a child of parent) in `tests/service/test_service_reorder_reparent.py`
- [X] T015 [P] [US2] Write failing tests for `reorder_view` POST with `kind="category"` (200 on valid body, 400 cases) in `tests/contrib/django/test_admin_graph.py`

### Implementation

- [X] T016 [US2] Implement `reorder_subcategories(self, parent_id: UUID, category_ids_in_order: list[UUID]) -> None` in `taxomesh/application/service.py`: load CategoryParentLinks for parent, validate all UUIDs present, reassign sort_index 0,1,2,… and call `save_category_parent_link` for each (depends on T014)
- [X] T017 [US2] Extend `reorder_view` in `taxomesh/contrib/django/admin.py` to branch on `kind == DRAG_KIND_CATEGORY` and call `svc.reorder_subcategories`; `kind == DRAG_KIND_ITEM` calls existing `reorder_items_in_category` (depends on T015, T016)
- [X] T018 [US2] Add drag handle `<span class="taxomesh-drag-handle">⠿</span>` and `draggable="true"` to category entries in `graph.html`; extend existing DnD JS to handle `kind="category"` siblings using the same `reorder_view` endpoint (depends on T017)

**Checkpoint**: Category sibling reorder works independently. Item reorder from US1 unaffected.

---

## Phase 5: User Story 3 — Move an Item to a Different Category (Priority: P3)

**Goal**: Admin drags an item and drops it onto a different category; item is reassigned (old link removed, new link created).

**Independent Test**: Create categories A and B, place item X in A. Drag X onto B's node. Reload — X appears under B and not under A.

### Tests (write first — must FAIL before implementation)

- [X] T019 [P] [US3] Write failing tests for `reparent_item` (item moves from old to new category, old link removed, new link created, errors on not-found) in `tests/service/test_service_reorder_reparent.py`
- [X] T020 [P] [US3] Write failing tests for `reparent_view` POST with `kind="item"` (200 on valid body, 400 on same parent, 400 on not-found, 405 on GET) in `tests/contrib/django/test_admin_graph.py`

### Implementation

- [X] T021 [US3] Implement `reparent_item(self, item_id: UUID, old_category_id: UUID, new_category_id: UUID, insert_before_uuid: UUID | None) -> ItemParentLink` in `taxomesh/application/service.py`: call `remove_item_from_category(item_id, old_category_id)`, compute `sort_index` by reading siblings in `new_category_id` and inserting before `insert_before_uuid` (or at end if None), then call `place_item_in_category` and reassign dense sort indices for all siblings; return new link (depends on T019)
- [X] T022 [US3] Implement `reparent_view(self, request: HttpRequest) -> HttpResponse` in `taxomesh/contrib/django/admin.py`: reject non-POST, parse JSON body, validate `kind`/`node_uuid`/`old_parent_uuid`/`new_parent_uuid`/`insert_before_uuid`, reject ROOT, call `svc.reparent_item` for item kind, return `JsonResponse({"ok": True})` or error (depends on T020, T021)
- [X] T023 [US3] Register `graph/reparent/` URL with name `GRAPH_REPARENT_URL_NAME` inside `get_urls()` in `taxomesh/contrib/django/admin.py` (depends on T022)
- [X] T024 [US3] Add cross-parent drop-target detection to the DnD JS in `graph.html`: when dragging an item, entry slots within other categories become highlighted as insertion targets; on drop determine `insert_before_uuid` (the sibling the item lands before, or null if dropped at end) and POST to `graph/reparent/` with `{kind, node_uuid, old_parent_uuid, new_parent_uuid, insert_before_uuid}`; on 200 insert item node at correct DOM position under new parent; on error revert and show message (depends on T023, T013)

**Checkpoint**: Item reparenting works. US1 (item reorder) and US2 (category reorder) remain unaffected.

---

## Phase 6: User Story 4 — Move a Category to a Different Parent (Priority: P4)

**Goal**: Admin drags a category node and drops it onto a different parent; old parent link removed, new parent link created with cycle detection enforced.

**Independent Test**: Create chain A → B → C. Drag B onto a separate root category D. Reload — B is under D, no longer under A. Attempt to drag A onto B → backend returns cycle error, A stays under its original parent.

### Tests (write first — must FAIL before implementation)

- [X] T025 [P] [US4] Write failing tests for `reparent_category` (category moves from old to new parent, cycle detection raises `TaxomeshCyclicDependencyError`, errors on not-found) in `tests/service/test_service_reorder_reparent.py`
- [X] T026 [P] [US4] Write failing tests for `reparent_view` POST with `kind="category"` (200 on valid body, 400 on ROOT node, 400 on cycle, 400 on not-found) in `tests/contrib/django/test_admin_graph.py`

### Implementation

- [X] T027 [US4] Implement `reparent_category(self, category_id: UUID, old_parent_id: UUID, new_parent_id: UUID, insert_before_uuid: UUID | None) -> CategoryParentLink` in `taxomesh/application/service.py`: call `remove_category_parent(category_id, old_parent_id)`, compute `sort_index` by reading siblings in `new_parent_id` and inserting before `insert_before_uuid` (or at end if None), call `add_category_parent` (cycle check runs inside), then reassign dense sort indices for all siblings in new parent; return new link (depends on T025)
- [X] T028 [US4] Extend `reparent_view` in `taxomesh/contrib/django/admin.py` to branch on `kind == DRAG_KIND_CATEGORY`: call `svc.reparent_category` (passing `insert_before_uuid`); catch `TaxomeshCyclicDependencyError` and return HTTP 400 with cycle error message (depends on T026, T027)
- [X] T029 [US4] Add category reparent drop-target detection to the DnD JS in `graph.html`: when dragging a category node, insertion slots within other parent nodes become highlighted; on drop determine `insert_before_uuid` and POST to `graph/reparent/` with `{kind, node_uuid, old_parent_uuid, new_parent_uuid, insert_before_uuid}`; on 200 move category subtree in DOM at correct position; on 400 cycle error display specific message and revert (depends on T028, T024)

**Checkpoint**: All four user stories fully functional. Cycle detection prevents invalid DAG mutations.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T030 [P] Ensure ROOT category node has no drag handle, no `draggable` attribute, and is excluded from all drop-target highlighting in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`
- [X] T031 [P] Add regression test confirming expand/collapse toggling works correctly after a reorder and after a reparent operation in `tests/contrib/django/test_admin_graph.py`
- [X] T032 Run quality gates and fix any failures: `ruff check .`, `ruff format --check .`, `mypy --strict .`, `pytest --cov=taxomesh --cov-fail-under=80`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 2 (Foundational) → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6 (US4) → Phase 7 (Polish)
```

Phase 2 blocks everything. Within Phase 2, tasks are sequential (all touch `admin.py`).

User story phases are ordered by priority but each is independently testable once the previous phase is complete.

### Within-Phase Dependencies

| Phase | Sequential chain |
|-------|-----------------|
| 2 | T001 → T002 → T003 → T004; T005 after T002 |
| 3 | T006 ‖ T007 → T008 ‖ T009 → T010 → T011 → T012 → T013 |
| 4 | T014 ‖ T015 → T016 ‖ T017 → T018 |
| 5 | T019 ‖ T020 → T021 ‖ T022 → T023 → T024 |
| 6 | T025 ‖ T026 → T027 ‖ T028 → T029 |
| 7 | T030 ‖ T031 → T032 |

(`‖` = can run in parallel; `→` = must be sequential)

### Parallel Opportunities Per Phase

**Phase 3 (US1)**:
- T006 and T007 can run in parallel (different test files)
- T008 and T009 can run in parallel after T006/T007 (different files: `service.py` vs `admin.py`)

**Phase 4 (US2)**:
- T014 and T015 can run in parallel (different test files)
- T016 and T017 can run in parallel after T014/T015

**Phase 5 (US3)**:
- T019 and T020 can run in parallel
- T021 and T022 can run in parallel after T019/T020

**Phase 6 (US4)**:
- T025 and T026 can run in parallel
- T027 and T028 can run in parallel after T025/T026

**Phase 7**:
- T030 and T031 can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (CRITICAL)
2. Complete Phase 3: User Story 1 (item reorder)
3. **STOP and VALIDATE**: Drag items within a category → persisted → visible after reload
4. Proceed to US2+ only after US1 is confirmed working

### Incremental Delivery

| Stage | Delivers | Gate |
|-------|---------|------|
| Phase 2 | Data attributes on graph entries | Manual: inspect page source |
| Phase 3 (US1) | Item reorder via drag | pytest test_admin_graph.py + manual drag test |
| Phase 4 (US2) | Category sibling reorder | pytest + manual |
| Phase 5 (US3) | Item reparenting | pytest + manual |
| Phase 6 (US4) | Category reparenting + cycle guard | pytest + manual cycle rejection |
| Phase 7 | Quality gates green | ruff + mypy + pytest ≥ 80% |

---

## Notes

- **TDD is mandatory** (CLAUDE.md): test task must be written and confirmed FAILING before its implementation task begins
- `[P]` tasks touch different files — safe to implement simultaneously
- `tests/service/test_service_reorder_reparent.py` is a new file (create in T006)
- `tests/contrib/django/test_admin_graph.py` is an existing file — add new test classes, do not modify existing tests
- `graph.html` JS additions must preserve all existing expand/collapse and relations-toggle behaviour
- CSRF token for fetch calls: read from `document.cookie` using the pattern already used by Django admin JS
- Commit after each phase checkpoint; propose commit message per CLAUDE.md rules before running `git commit`
