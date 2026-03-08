# Tasks: Unified __str__ + Django Admin Graph Links

**Input**: Design documents from `/specs/022-unified-str-admin-links/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**Note**: This is a retroactive tasks file — all tasks are already implemented and verified.
Tasks are marked complete. Checked boxes reflect actual implementation status.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project structure needed — this feature touches existing files only.

- [x] T001 Confirm Django admin URL names for CategoryModel and item_id change pages (research.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No blocking foundational changes — `__str__` updates are self-contained.

*(No foundational tasks required for this feature.)*

---

## Phase 3: User Story 1 — Consistent human-readable labels (Priority: P1) 🎯 MVP

**Goal**: `Category.__str__` and `Item.__str__` become the single source of truth for
human-readable representation, with conditional slug/ext_id segments.

**Independent Test**: `pytest tests/domain/test_models.py tests/domain/test_slug_field.py tests/adapters/cli/test_graph_output.py -v`

### Tests for User Story 1

- [x] T002 [P] [US1] Add `TestCategory.__str__` tests (4 cases) in `tests/domain/test_models.py`
- [x] T003 [P] [US1] Add `TestItem.__str__` tests (3 cases) in `tests/domain/test_models.py`
- [x] T004 [P] [US1] Update stale `TestItemStr` tests in `tests/domain/test_slug_field.py` to match new format
- [x] T005 [P] [US1] Update stale `TestCategoryStr` tests in `tests/domain/test_slug_field.py` to match new format
- [x] T006 [US1] Rename and invert `test_category_external_id_not_shown_in_graph` → `test_category_external_id_shown_in_graph` in `tests/adapters/cli/test_graph_output.py`

### Implementation for User Story 1

- [x] T007 [P] [US1] Update `Category.__str__` to conditional slug/ext_id format in `taxomesh/domain/models/category.py`
- [x] T008 [P] [US1] Update `Item.__str__` to conditional slug/ext_id format in `taxomesh/domain/models/item.py`

**Checkpoint**: `pytest tests/domain/ tests/adapters/cli/test_graph_output.py` → all pass ✅

---

## Phase 4: User Story 2 — Django admin graph links to change pages (Priority: P2)

**Goal**: Each label in the Django admin graph view is a clickable link to the change page
for that category or item.

**Independent Test**: Load the graph view; verify each label renders as `<a href="...">`.

### Tests for User Story 2

- [x] T009 [P] [US2] Add `TestGraphAdminView.test_graph_view_renders_anchor_links` in `tests/contrib/django/test_admin.py` (SC-002)

### Implementation for User Story 2

- [x] T010 [US2] Simplify `_flatten_graph` in `taxomesh/contrib/django/admin.py` — call `str(cat)` / `str(item)`, remove per-field extraction, remove `slug`/`external_id`/`indent_em` keys
- [x] T011 [US2] Update `graph.html` template: wrap each label in `<a>` tag with Django admin change-page URL; remove `taxomesh-uuid`, `taxomesh-ext` spans and unused CSS in `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html`

**Checkpoint**: `pytest tests/contrib/django/ -v` → all pass ✅

---

## Phase 5: User Story 3 — Simplified admin graph rendering (Priority: P3)

**Goal**: `_flatten_graph` returns entries with `name = str(obj)`, and no `slug`, `external_id`,
or `indent_em` keys.

**Independent Test**: `pytest tests/contrib/django/test_admin.py::TestFlattenGraph -v`

### Tests for User Story 3

- [x] T012 [P] [US3] Add `TestFlattenGraph.test_entry_schema_has_no_legacy_keys` in `tests/contrib/django/test_admin.py` (SC-003)
- [x] T013 [P] [US3] Add `TestFlattenGraph.test_entry_name_equals_str_of_domain_object` in `tests/contrib/django/test_admin.py` (FR-007)

*(Implementation covered by T010 above — US3 shares the same change.)*

**Checkpoint**: `pytest tests/contrib/django/test_admin.py::TestFlattenGraph` → all pass ✅

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T014 Run `ruff check .` and `ruff format --check .` — clean ✅
- [x] T015 Run `mypy --strict .` — clean ✅
- [x] T016 Run `pytest --cov=taxomesh --cov-fail-under=80` — 598 tests pass, 92% coverage ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 3 (US1)**: Depends on Phase 1 — foundational skip (no Phase 2 needed)
- **Phase 4 (US2)**: Depends on Phase 3 (uses `str()` from updated models)
- **Phase 5 (US3)**: Covered by Phase 4 implementation
- **Phase 6 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: Independent — domain models only
- **US2 (P2)**: Depends on US1 — `_flatten_graph` must call `str()` from updated models
- **US3 (P3)**: Covered by US2 implementation — no additional work

### Parallel Opportunities

- T002, T003, T004, T005, T006 — all test updates can run in parallel (different files)
- T007, T008 — `category.py` and `item.py` updates can run in parallel
- T010, T011 — admin.py and graph.html can run in parallel (different files)
- T012, T013 — `TestFlattenGraph` tests can run in parallel
- T014, T015, T016 — quality gate checks can run in parallel

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Update `Category.__str__` and `Item.__str__` (T007, T008)
2. Update tests (T002–T006)
3. Validate: `pytest tests/domain/ tests/adapters/cli/`

### Full Delivery (All Stories)

1. US1 complete → US2 (T009–T011) → US3 tests (T012–T013) → quality gates (T014–T016)

---

## Notes

- All tasks are retroactively marked complete — implementation preceded spec.
- No new files created; all changes are in-place edits to existing files.
- CLI adapter (`taxomesh/adapters/cli/main.py`) required **zero changes** — it already called `str()`.
