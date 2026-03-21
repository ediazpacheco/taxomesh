# Tasks: Admin Child Categories Editable Inline

**Input**: Design documents from `/specs/044-child-categories-edit/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, quickstart.md ✅

**TDD**: Tests are mandatory per CLAUDE.md. Every implementation task has a preceding failing test task.

**Organization**: Tasks grouped by user story. All implementation targets two files:
- `taxomesh/contrib/django/admin.py`
- `tests/contrib/django/test_admin.py`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: User story label (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: Confirm existing code matches research findings before writing tests.

- [ ] T001 Read `CategoryParentLinkInline`, `CategoryChildLinkInline`, and `_ReadOnlyInlineMixin` in `taxomesh/contrib/django/admin.py` to verify field names, base classes, and service call signatures match `research.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No new infrastructure is needed. The existing `CategoryParentLinkModel`, `TaxomeshAdminMixin`, and service layer are already in place. Phase 2 is satisfied by Phase 1 completion.

**⚠️ CRITICAL**: T001 must pass before writing any tests.

---

## Phase 3: User Story 1 — Add a Child Category Link (Priority: P1) 🎯 MVP

**Goal**: Admin can add a new child category link (with autocomplete selector + sort index) from the parent's change page. Cycle and duplicate validation surface as form errors.

**Independent Test**: Open any category change page. Use the "Child categories" inline to add a valid child; save; verify the link appears. Attempt to add the same child again; verify a validation error appears. Attempt to add a child that would create a cycle; verify a validation error appears.

### Tests for User Story 1

> **Write these tests FIRST and confirm they FAIL before any implementation**

- [ ] T002 [US1] Write failing `TestCategoryChildLinkForm` class with tests: `test_valid_child_link_form_is_valid`, `test_self_link_raises_validation_error` in `tests/contrib/django/test_admin.py`
- [ ] T003 [US1] Write failing tests in `TestCategoryChildLinkForm`: `test_cycle_raises_validation_error`, `test_duplicate_raises_validation_error` in `tests/contrib/django/test_admin.py` (depends on T002 — add to same class)
- [ ] T004 [US1] Write failing `TestCategoryChildLinkInlineEditable` class with tests: `test_has_add_permission_returns_true`, `test_has_change_permission_returns_true`, `test_fk_name_is_parent_category`, `test_autocomplete_fields_includes_category` in `tests/contrib/django/test_admin.py`
- [ ] T005 [US1] Write failing test `test_save_model_calls_service_add_category_parent` in `TestCategoryChildLinkInlineEditable` in `tests/contrib/django/test_admin.py` (depends on T004 — add to same class)
- [ ] T006 [US1] Write failing test `test_root_category_excluded_from_child_selector` in `TestCategoryChildLinkInlineEditable` in `tests/contrib/django/test_admin.py` (depends on T004)
- [ ] T007 [US1] Confirm all T002–T006 tests fail: `pytest tests/contrib/django/test_admin.py -k "ChildLinkForm or ChildLinkInlineEditable" -v`

### Implementation for User Story 1

- [ ] T008 [US1] Add `CategoryChildLinkForm(forms.ModelForm)` class (after `CategoryParentLinkForm`) with `Meta.model = CategoryParentLinkModel` and `clean()` validating self-link and catching `TaxomeshCyclicDependencyError` from service in `taxomesh/contrib/django/admin.py` (depends on T007)
- [ ] T009 [US1] Replace `CategoryChildLinkInline` body: remove `_ReadOnlyInlineMixin`, add `TaxomeshAdminMixin`, set `form = CategoryChildLinkForm`, `autocomplete_fields = ["category"]`, `extra = 0`, implement `save_model()` calling `svc.add_category_parent(obj.category_id, obj.parent_category_id)`, and `formfield_for_foreignkey()` excluding `ROOT_CATEGORY_NAME` from child selector in `taxomesh/contrib/django/admin.py` (depends on T008)
- [ ] T010 [US1] Run US1 tests and confirm all pass: `pytest tests/contrib/django/test_admin.py -k "ChildLinkForm or ChildLinkInlineEditable" -v`

**Checkpoint**: Admin can now add child links with validation. User Story 1 fully functional.

---

## Phase 4: User Story 2 — Edit Sort Index of Existing Child Link (Priority: P2)

**Goal**: Each child link row exposes an editable `sort_index` field. Saving an edited sort index persists correctly.

**Independent Test**: Open a category change page with an existing child link. Modify the sort index value; save; reload; confirm the new sort index value appears.

### Tests for User Story 2

> **Write these tests FIRST and confirm they FAIL before any implementation**

- [ ] T011 [US2] Write failing tests `test_sort_index_field_is_editable` and `test_sort_index_defaults_to_zero_when_omitted` in `TestCategoryChildLinkInlineEditable` in `tests/contrib/django/test_admin.py`
- [ ] T012 [US2] Confirm T011 tests fail: `pytest tests/contrib/django/test_admin.py -k "sort_index" -v`

### Implementation for User Story 2

- [ ] T013 [US2] Confirm `sort_index` is not listed in `readonly_fields` or excluded from `fields` in `CategoryChildLinkInline`; if hidden, remove the exclusion in `taxomesh/contrib/django/admin.py` (depends on T012)
- [ ] T014 [US2] Run US2 tests and confirm all pass: `pytest tests/contrib/django/test_admin.py -k "sort_index" -v`

**Checkpoint**: Admins can now edit sort index of child links.

---

## Phase 5: User Story 3 — Remove a Child Category Link (Priority: P2)

**Goal**: Admin can mark an existing child link for deletion; saving removes the link permanently.

**Independent Test**: Open a category change page with at least one child link. Check the delete checkbox for that row; save; reload; confirm the child no longer appears.

### Tests for User Story 3

> **Write these tests FIRST and confirm they FAIL before any implementation**

- [ ] T015 [US3] Write failing tests `test_has_delete_permission_returns_true` and `test_delete_model_calls_service_remove_category_parent` in `TestCategoryChildLinkInlineEditable` in `tests/contrib/django/test_admin.py`
- [ ] T016 [US3] Confirm T015 tests fail: `pytest tests/contrib/django/test_admin.py -k "delete_permission or delete_model" -v`

### Implementation for User Story 3

- [ ] T017 [US3] Add `delete_model()` method to `CategoryChildLinkInline` calling `svc.remove_category_parent(obj.category_id, obj.parent_category_id)` in `taxomesh/contrib/django/admin.py` (depends on T016)
- [ ] T018 [US3] Run US3 tests and confirm all pass: `pytest tests/contrib/django/test_admin.py -k "delete_permission or delete_model" -v`

**Checkpoint**: All three user stories are now fully functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T019 [P] Run full linting and formatting check: `ruff check . && ruff format --check .`
- [ ] T020 [P] Run mypy strict type check: `mypy --strict .`
- [ ] T021 Run full test suite with coverage gate: `pytest --cov=taxomesh --cov-fail-under=80`
- [ ] T022 Verify all quickstart.md validation scenarios pass (add child link, edit sort index, remove child link, cycle rejection, duplicate rejection)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Satisfied by Phase 1 — no additional work
- **User Stories (Phase 3–5)**: Depend on Phase 1 completion; US2 and US3 depend on US1's inline being editable
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Start after Phase 1 — independent
- **US2 (P2)**: Inline must be editable (T009 complete) before implementation; tests can be written in parallel
- **US3 (P2)**: Inline must be editable (T009 complete) before implementation; tests can be written in parallel with US2

### Within Each User Story

- Tests MUST be written and confirmed failing before any implementation task
- Form before inline (US1: T008 before T009)
- All changes are in one file; write sequentially to avoid conflicts

### Parallel Opportunities

- T019 (ruff) and T020 (mypy) can run in parallel in Phase 6
- US2 test writing (T011) can begin in parallel with US1 implementation (T008, T009)
- US3 test writing (T015) can begin in parallel with US1 implementation (T008, T009)

---

## Parallel Example: US2 and US3 Test Writing

```bash
# While US1 implementation (T008-T009) is in progress, begin writing tests:
Task T011: Write sort_index tests (US2) in tests/contrib/django/test_admin.py
Task T015: Write delete_model tests (US3) in tests/contrib/django/test_admin.py
# Both can be done while waiting for US1 implementation to land
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Write US1 tests (T002–T006), confirm failure (T007)
3. Implement `CategoryChildLinkForm` (T008)
4. Implement editable `CategoryChildLinkInline` (T009)
5. **STOP and VALIDATE**: Run T010 — all US1 tests pass
6. Demo: Admin can add child links with validation

### Incremental Delivery

1. MVP → US1 complete (admin can add child links)
2. US2 → sort index editable (tests T011–T014)
3. US3 → delete capability (tests T015–T018)
4. Polish → all quality gates pass (T019–T022)

---

## Notes

- No migration tasks — `CategoryParentLinkModel` is unchanged
- All 22 tasks target exactly 2 files; no structural changes needed
- [P] tasks = no file conflicts, can run in parallel
- TDD is mandatory: confirm test failure before each implementation step
- Commit after each checkpoint (T010, T014, T018, T022)
