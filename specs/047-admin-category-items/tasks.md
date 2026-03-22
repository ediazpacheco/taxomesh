# Tasks: Category Items Inline on Admin Change Page

**Input**: Design documents from `specs/047-admin-category-items/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**TDD**: Test tasks are mandatory per project constitution. Write each test task first and confirm it fails before implementing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all descriptions

---

## Phase 1: Setup

No new files, no migrations, no dependencies to install. This feature is a pure addition to an existing module.

**Checkpoint**: No setup required — proceed to user story phases.

---

## Phase 3: User Story 1 — View Items in a Category (Priority: P1) 🎯 MVP

**Goal**: An admin opening a category change page sees all items assigned to that category in a tabular inline section.

**Independent Test**: Navigate to a category change page in the Django admin; an "Items" inline section renders with the correct items. Verified via unit tests asserting the inline class is registered and its queryset filters by category.

### Tests for User Story 1 ⚠️ Write these FIRST — confirm they FAIL before implementing

- [x] T001 [US1] Write failing test asserting `CategoryItemLinkInline` is registered in `CategoryModelAdmin.inlines` in `tests/contrib/django/test_admin.py` (class `TestCategoryItemLinkInline`)
- [x] T002 [US1] Write failing test asserting `CategoryItemLinkInline.get_queryset()` filtered by category returns only items linked to that category in `tests/contrib/django/test_admin.py`
- [x] T003 [US1] Write failing tests asserting `CategoryItemLinkInline` uses `autocomplete_fields = ["item"]` and does not define a `fields` or `exclude` attribute that hides `sort_index` (verifying FR-002: sort_index is editable) in `tests/contrib/django/test_admin.py`

### Implementation for User Story 1

- [x] T004 [US1] Add `CategoryItemLinkInline(TaxomeshAdminMixin, admin.TabularInline)` class skeleton to `taxomesh/contrib/django/admin.py` in the "Item inlines" section — set `model = ItemParentLinkModel`, `fk_name = "category"`, `extra = 0`, `verbose_name = "Item"`, `verbose_name_plural = "Items"`, `autocomplete_fields = ["item"]`; include Google-style docstring
- [x] T005 [US1] Add `CategoryItemLinkInline` to `CategoryModelAdmin.inlines` in `taxomesh/contrib/django/admin.py`
- [x] T006 [US1] Run `pytest tests/contrib/django/test_admin.py::TestCategoryItemLinkInline -x` and confirm T001–T003 pass

**Checkpoint**: Category change page shows an Items inline section. US1 is independently functional.

---

## Phase 4: User Story 2 — Add an Existing Item to a Category (Priority: P2)

**Goal**: An admin can select an existing item from the inline's add row and save; the item–category link is created via the service layer.

**Independent Test**: Call `save_model` on the inline with a new `ItemParentLinkModel` instance; assert `TaxomeshService.place_item_in_category` was called with the correct arguments. Separately: assert duplicate adds produce a validation error.

### Tests for User Story 2 ⚠️ Write these FIRST — confirm they FAIL before implementing

- [x] T007 [US2] Write failing test asserting `CategoryItemLinkInline.save_model()` calls `svc.place_item_in_category(item_id, category_id, sort_index)` in `tests/contrib/django/test_admin.py`
- [x] T008 [P] [US2] Write failing test asserting that adding the same item to the same category twice produces a `ValidationError` (ORM-level unique_together) in `tests/contrib/django/test_admin.py`

### Implementation for User Story 2

- [x] T009 [US2] Implement `save_model(self, request, obj, form, change)` on `CategoryItemLinkInline` in `taxomesh/contrib/django/admin.py` — call `self._make_service().place_item_in_category(obj.item_id, obj.category_id, obj.sort_index)`; catch `TaxomeshError` and surface via `self.message_user(..., level=messages.ERROR)`; include Google-style docstring
- [x] T010 [US2] Run `pytest tests/contrib/django/test_admin.py::TestCategoryItemLinkInline -x` and confirm T007–T008 pass

**Checkpoint**: Items can be added to a category from the category change page via the inline. Duplicates are rejected. US2 is independently functional.

---

## Phase 5: User Story 3 — Remove an Item from a Category (Priority: P3)

**Goal**: An admin can delete an item–category link from the inline; the link is removed via the service layer and the item record is preserved.

**Independent Test**: Call `delete_model` on the inline with an existing `ItemParentLinkModel` instance; assert `TaxomeshService.remove_item_from_category` was called and the `ItemModel` record still exists.

### Tests for User Story 3 ⚠️ Write these FIRST — confirm they FAIL before implementing

- [x] T011 [US3] Write failing test asserting `CategoryItemLinkInline.delete_model()` calls `svc.remove_item_from_category(item_id, category_id)` in `tests/contrib/django/test_admin.py`
- [x] T012 [US3] Write failing test asserting that after delete, the `ItemModel` record still exists in the database in `tests/contrib/django/test_admin.py`

### Implementation for User Story 3

- [x] T013 [US3] Implement `delete_model(self, request, obj)` on `CategoryItemLinkInline` in `taxomesh/contrib/django/admin.py` — call `self._make_service().remove_item_from_category(obj.item_id, obj.category_id)`; include Google-style docstring
- [x] T014 [US3] Run `pytest tests/contrib/django/test_admin.py::TestCategoryItemLinkInline -x` and confirm T011–T012 pass

**Checkpoint**: Items can be removed from a category without deleting the item record. All three user stories are fully functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T015 [P] Run `ruff check taxomesh/contrib/django/admin.py tests/contrib/django/test_admin.py` and fix any lint errors
- [x] T016 [P] Run `ruff format --check taxomesh/contrib/django/admin.py tests/contrib/django/test_admin.py` and fix any formatting issues
- [x] T017 Run `mypy --strict taxomesh/contrib/django/admin.py` and resolve any type errors
- [x] T018 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm all tests pass with coverage ≥ 80%

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 3 (US1)**: No dependencies — can start immediately
- **Phase 4 (US2)**: Depends on T004+T005 (class must exist before save_model is added)
- **Phase 5 (US3)**: Depends on T004+T005 (class must exist before delete_model is added)
- **Phase 6 (Polish)**: Depends on all implementation tasks being complete

### User Story Dependencies

- **US1 (P1)**: No dependencies on other stories; delivers MVP (inline renders items)
- **US2 (P2)**: Depends on US1 (class skeleton must exist); adds save_model
- **US3 (P3)**: Depends on US1 (class skeleton must exist); adds delete_model; US2 and US3 are independent of each other once the skeleton exists

### Within Each User Story

Tests MUST be written and confirmed FAILING before implementation. Each story adds incrementally to the same class in `admin.py`.

### Parallel Opportunities

- T002 and T003 (both test-writing tasks for US1) can be written in parallel
- T007 and T008 (test-writing tasks for US2) can be written in parallel
- T011 and T012 (test-writing tasks for US3) can be written in parallel
- T015 and T016 (ruff check and format) can run in parallel
- Once US1 class skeleton (T004+T005) is done, US2 and US3 implementation tasks can be worked in parallel by different developers

---

## Parallel Example: User Story 1

```bash
# Write both structural tests in parallel:
Task: T002 — get_queryset test
Task: T003 — autocomplete_fields test

# Then implement (T004 + T005 sequentially), then run:
pytest tests/contrib/django/test_admin.py::TestCategoryItemLinkInline -x
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Write T001–T003 (failing tests)
2. Implement T004–T005 (class skeleton + inlines registration)
3. Run T006 — confirm US1 tests pass
4. **STOP and VALIDATE**: Category change page shows items inline

### Incremental Delivery

1. US1 → Items inline visible on category change page
2. US2 → Items can be added from category change page
3. US3 → Items can be removed from category change page
4. Polish → Quality gates clean

---

## Notes

- All implementation is in a single class in `taxomesh/contrib/django/admin.py`
- All tests go in the existing `tests/contrib/django/test_admin.py`
- No migrations, no new models, no new service methods
- `fk_name = "category"` is the critical setting — Django uses it to filter the inline queryset by the current `CategoryModel` instance
- The pattern mirrors `CategoryChildLinkInline` (044-child-categories-edit) exactly, substituting `ItemParentLinkModel` and the `item` FK
