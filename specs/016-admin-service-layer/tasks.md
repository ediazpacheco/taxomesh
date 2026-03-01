# Tasks: Admin Service Layer

**Input**: Design documents from `/specs/016-admin-service-layer/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ quickstart.md ✅

**Tests**: Included — TDD is mandatory (CLAUDE.md). Every implementation task is preceded by a failing-test task.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are relative to the repository root

---

## Phase 1: Setup

**Purpose**: Create the new test file that will receive all admin service-routing tests across all user stories. No source-code changes yet.

- [x] T001 Create empty test module `tests/contrib/django/test_admin_service_routing.py` with module docstring and `pytest.mark.django_db` marker

**Checkpoint**: New test file exists; `pytest tests/contrib/django/test_admin_service_routing.py` collects 0 tests and exits green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New repository Protocol methods, all adapter implementations, and new service methods that US1–US4 all depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Repository Protocol

- [x] T002 Add `delete_category_parent_link(category_id: UUID, parent_category_id: UUID) -> bool` and `delete_item_parent_link(item_id: UUID, category_id: UUID) -> bool` to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py` (with Google-style docstrings)

### Repository Implementations (parallel after T002)

- [x] T003 [P] Implement `delete_category_parent_link` and `delete_item_parent_link` in `taxomesh/adapters/repositories/django_repository.py`
- [x] T004 [P] Implement `delete_category_parent_link` and `delete_item_parent_link` in `taxomesh/adapters/repositories/json_repository.py`
- [x] T005 [P] Implement `delete_category_parent_link` and `delete_item_parent_link` in `taxomesh/adapters/repositories/yaml_repository.py`

### Service Methods — Tests First (parallel after T003–T005)

- [x] T006 [P] Write failing tests for `remove_category_parent` (valid removal, non-existent link is no-op, non-existent category raises `TaxomeshCategoryNotFoundError`) in `tests/service/test_category_parent_upsert.py`
- [x] T007 [P] Write failing tests for `remove_item_from_category` (valid removal, non-existent placement is no-op, non-existent item raises `TaxomeshItemNotFoundError`) in `tests/service/test_item_parent_upsert.py`

### Service Methods — Implementation (after T006/T007)

- [x] T008 Implement `remove_category_parent(category_id: UUID, parent_id: UUID) -> None` in `taxomesh/application/service.py` — verify T006 tests pass
- [x] T009 Implement `remove_item_from_category(item_id: UUID, category_id: UUID) -> None` in `taxomesh/application/service.py` — verify T007 tests pass

**Checkpoint**: `pytest tests/service/test_category_parent_upsert.py tests/service/test_item_parent_upsert.py` is fully green. `mypy --strict .` passes.

---

## Phase 3: User Story 1 — Cycle Detection via Parent-Link Inline (Priority: P1) 🎯 MVP

**Goal**: Admins can manage `CategoryParentLink` rows via an inline on the Category detail page. Attempting to add a link that creates a cycle surfaces a form-level validation error; no data is written.

**Independent Test**: Navigate to any Category in the admin, use the parent-link inline to submit a cycle, and confirm a validation error is displayed and the relationship is unchanged.

### Tests for US1 (write first — must FAIL before T012)

- [x] T010 [US1] Write failing tests for `CategoryParentLinkInline`:
  - Inline appears on Category change page
  - Submitting a cyclic parent raises `forms.ValidationError` in `clean()` and no link is created
  - Submitting a valid parent via inline calls `service.add_category_parent()` and persists the link
  - Deleting a parent row via inline calls `service.remove_category_parent()`
  — in `tests/contrib/django/test_admin_service_routing.py`

### Implementation for US1

- [x] T011 [US1] Add `_make_service() -> TaxomeshService` private method to `CategoryModelAdmin` in `taxomesh/contrib/django/admin.py` (returns `TaxomeshService(repository=DjangoRepository())`)
- [x] T012 [US1] Implement `CategoryParentLinkInline(TabularInline)` class in `taxomesh/contrib/django/admin.py`:
  - `model = CategoryParentLinkModel`
  - `form = CategoryParentLinkForm` — custom `ModelForm` with `clean()` that calls `check_no_cycle()` from `taxomesh.domain.dag` (read-only, domain-direct) and has an explicit self-reference guard; catches `TaxomeshCyclicDependencyError` and raises `forms.ValidationError`
  - ORM write for add operations is performed natively by Django's formset save after `clean()` passes (`save_model()` is never called by Django's inline formset path for add)
  - `delete_model()` override: calls `service.remove_category_parent(obj.category_id, obj.parent_category_id)`; does NOT call `super()`
- [x] T013 [US1] Add `CategoryParentLinkInline` to `CategoryModelAdmin.inlines` in `taxomesh/contrib/django/admin.py`
- [x] T014 [US1] Run `pytest tests/contrib/django/test_admin_service_routing.py -k "parent_link"` and confirm T010 tests pass

**Checkpoint**: T010 tests are green. Cycle detection works end-to-end in the admin.

---

## Phase 4: User Story 2 — Category CRUD Through Service (Priority: P2)

**Goal**: Every create, update, delete, and bulk-delete on Category records in the admin goes through `TaxomeshService`. Validation errors from the service are surfaced as admin message-level alerts.

**Independent Test**: Patch `TaxomeshService` to a mock and trigger each admin operation (POST to add, POST to change, delete, bulk-delete action); confirm the correct service method is called and no ORM save/delete is invoked directly.

### Tests for US2 (write first — must FAIL before T016–T019)

- [x] T015 [US2] Write failing tests for `CategoryModelAdmin` service routing:
  - `save_model` with `change=False` calls `service.create_category(name=..., ...)`
  - `save_model` with `change=True` calls `service.update_category(category_id, ...)`
  - `delete_model` calls `service.delete_category(category_id)`
  - `delete_queryset` calls `service.delete_category()` once per object in queryset
  - `TaxomeshValidationError` in `save_model` → error surfaced via `message_user(ERROR)`, no ORM write
  - `TaxomeshError` in `delete_model` → error surfaced via `message_user(ERROR)`, no ORM delete
  — in `tests/contrib/django/test_admin_service_routing.py`

### Implementation for US2

- [x] T016 [US2] Override `save_model(request, obj, form, change)` on `CategoryModelAdmin` in `taxomesh/contrib/django/admin.py`:
  - If `not change`: call `svc.create_category(name=obj.name, description=obj.description, enabled=obj.enabled, external_id=obj.external_id)`
  - If `change`: call `svc.update_category(obj.category_id, name=obj.name, description=obj.description, enabled=obj.enabled, external_id=obj.external_id)`
  - Catch `TaxomeshValidationError` → `self.message_user(request, str(exc), level=messages.ERROR)`
  - Do NOT call `super().save_model()`
- [x] T017 [US2] Override `delete_model(request, obj)` on `CategoryModelAdmin` in `taxomesh/contrib/django/admin.py`:
  - Call `svc.delete_category(obj.category_id)`
  - Catch `TaxomeshError` → `self.message_user(request, str(exc), level=messages.ERROR)`
  - Do NOT call `super().delete_model()`
- [x] T018 [US2] Override `delete_queryset(request, queryset)` on `CategoryModelAdmin` in `taxomesh/contrib/django/admin.py`:
  - Iterate over queryset; call `svc.delete_category(obj.category_id)` per object
  - Collect errors; report all via `self.message_user(request, ..., level=messages.ERROR)`
  - Do NOT call `super().delete_queryset()`
- [x] T019 [US2] Run `pytest tests/contrib/django/test_admin_service_routing.py -k "category_model_admin"` and confirm T015 tests pass

**Checkpoint**: T015 tests are green. Category CRUD fully routes through the service.

---

## Phase 5: User Stories 3 & 4 — Item/Tag CRUD + Inlines (Priority: P3)

**Goal (US3)**: Every create, update, delete, and bulk-delete on Item and Tag records goes through `TaxomeshService`.
**Goal (US4)**: Item detail page has `ItemParentLink` and `ItemTagLink` inlines; all inline mutations route through the service.

**Independent Test (US3)**: Patch `TaxomeshService` to a mock; trigger each admin operation on Item and Tag; confirm correct service method is called.
**Independent Test (US4)**: Use the inlines on the Item detail page to add/remove a category placement and tag assignment; confirm service methods are called.

### Tests for US3 (parallel — write first, must FAIL)

- [x] T020 [P] [US3] Write failing tests for `ItemModelAdmin` service routing:
  - `save_model` create/update calls `service.create_item()` / `service.update_item()`
  - `delete_model` calls `service.delete_item(item_id)`
  - `delete_queryset` calls `service.delete_item()` per object
  - `TaxomeshError` in any hook → `message_user(ERROR)`, no ORM write
  — in `tests/contrib/django/test_admin_service_routing.py`
- [x] T021 [P] [US3] Write failing tests for `TagModelAdmin` service routing:
  - `save_model` create/update calls `service.create_tag()` / `service.update_tag()`
  - `delete_model` calls `service.delete_tag(tag_id)`
  - `delete_queryset` calls `service.delete_tag()` per object
  — in `tests/contrib/django/test_admin_service_routing.py`

### Tests for US4 (parallel — write first, must FAIL)

- [x] T022 [P] [US4] Write failing tests for `ItemParentLinkInline`:
  - `save_model` calls `service.place_item_in_category(item_id, category_id, sort_index)`
  - `delete_model` calls `service.remove_item_from_category(item_id, category_id)`
  — in `tests/contrib/django/test_admin_service_routing.py`
- [x] T023 [P] [US4] Write failing tests for `ItemTagLinkInline`:
  - `save_model` calls `service.assign_tag(tag_id, item_id)`
  - `delete_model` calls `service.remove_tag(tag_id, item_id)`
  — in `tests/contrib/django/test_admin_service_routing.py`

### Implementation for US3 (parallel after T020/T021)

- [x] T024 [P] [US3] Add `_make_service()` to `ItemModelAdmin`; override `save_model`, `delete_model`, `delete_queryset` in `taxomesh/contrib/django/admin.py` (same pattern as T016–T018 for Category, using `create_item`/`update_item`/`delete_item`) — verify T020 tests pass
- [x] T025 [P] [US3] Add `_make_service()` to `TagModelAdmin`; override `save_model`, `delete_model`, `delete_queryset` in `taxomesh/contrib/django/admin.py` (using `create_tag`/`update_tag`/`delete_tag`) — verify T021 tests pass

### Implementation for US4 (after T022/T023)

- [x] T026 [US4] Implement `ItemParentLinkInline(TabularInline)` in `taxomesh/contrib/django/admin.py`:
  - `model = ItemParentLinkModel`
  - `save_model()`: calls `service.place_item_in_category(obj.item_id, obj.category_id, obj.sort_index)`; catches `TaxomeshError` → `message_user(ERROR)`; does NOT call `super()`
  - `delete_model()`: calls `service.remove_item_from_category(obj.item_id, obj.category_id)`; does NOT call `super()`
- [x] T027 [US4] Implement `ItemTagLinkInline(TabularInline)` in `taxomesh/contrib/django/admin.py`:
  - `model = ItemTagLinkModel`
  - `save_model()`: calls `service.assign_tag(obj.tag_id, obj.item_id)`; catches `TaxomeshError` → `message_user(ERROR)`; does NOT call `super()`
  - `delete_model()`: calls `service.remove_tag(obj.tag_id, obj.item_id)`; does NOT call `super()`
- [x] T028 [US4] Add `ItemParentLinkInline` and `ItemTagLinkInline` to `ItemModelAdmin.inlines` in `taxomesh/contrib/django/admin.py`
- [x] T029 [US4] Run `pytest tests/contrib/django/test_admin_service_routing.py -k "item"` and confirm T022/T023 tests pass

**Checkpoint**: All US3/US4 tests green. Item and Tag CRUD plus both Item inlines fully route through the service.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Quality gate verification, coverage confirmation, and spec success-criteria review.

- [x] T030 Run `mypy --strict .` and resolve all type errors introduced by new code in `taxomesh/ports/repository.py`, `taxomesh/application/service.py`, and `taxomesh/contrib/django/admin.py`
- [x] T031 Run `ruff check . && ruff format --check .` and fix any lint/format violations
- [x] T032 Run `pytest --cov=taxomesh --cov-fail-under=80` and confirm coverage gate passes; if coverage drops, add targeted tests to `tests/contrib/django/test_admin_service_routing.py` — also verify SC-003: confirm no previously-passing test was deleted without a replacement covering the same behaviour
- [x] T033 [P] Verify SC-001: review `test_admin_service_routing.py` to confirm 100% of mutation paths (create, update, delete, bulk-delete, all inline ops) have a test asserting the service method was called — cross-check against `test_admin.py` to confirm SC-003 (no test deleted without replacement) is satisfied
- [x] T034 [P] Verify SC-002: confirm a cycle-detection test is present and demonstrates zero data written on cycle attempt
- [x] T035 [P] Verify SC-005: confirm at least one test per admin class covers `TaxomeshError` resulting in a `message_user(ERROR)` call, not an unhandled exception
- [x] T036 [P] Verify FR-014 (root category hidden from admin): confirm `TestRootCategoryHidden` in `tests/contrib/django/test_admin.py` covers `get_queryset()` excluding root from changelist and `formfield_for_foreignkey()` excluding root from parent_category dropdown — both tests green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
  - T002 → T003, T004, T005 (parallel)
  - T003/T004/T005 → T006, T007 (parallel)
  - T006 → T008; T007 → T009
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: Depends on Phase 2 completion; independent of Phase 3
- **Phase 5 (US3+US4)**: Depends on Phase 2 completion; independent of Phases 3–4
- **Phase 6 (Polish)**: Depends on all desired user story phases being complete

### User Story Dependencies

- **US1 (P1)**: Phase 2 → T010 → T011 → T012 → T013 → T014
- **US2 (P2)**: Phase 2 → T015 → T016 → T017 → T018 → T019
- **US3 (P3)**: Phase 2 → T020/T021 → T024/T025 (parallel within US3)
- **US4 (P3)**: Phase 2 → T022/T023 → T026 → T027 → T028 → T029

### Within Each Phase

- Test tasks MUST be written and confirmed FAILING before implementation tasks start
- Implementation tasks run sequentially within a user story
- After each implementation task, run the failing tests to verify they now pass

### Parallel Opportunities

- T003, T004, T005 (repo implementations) can all run in parallel
- T006, T007 (failing test authoring) can run in parallel after T003–T005
- T008, T009 (service implementations) can run in parallel after T006/T007 respectively
- T020, T021, T022, T023 (failing test authoring for US3/US4) can all run in parallel
- T024, T025 (ItemModelAdmin + TagModelAdmin implementations) can run in parallel
- T033, T034, T035 (success-criteria verification) can run in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# After T002 completes — run these together:
Task T003: "Implement delete methods in django_repository.py"
Task T004: "Implement delete methods in json_repository.py"
Task T005: "Implement delete methods in yaml_repository.py"

# After T003–T005 complete — run these together:
Task T006: "Write failing tests for remove_category_parent"
Task T007: "Write failing tests for remove_item_from_category"
```

## Parallel Example: Phase 5 (US3 + US4)

```bash
# All four failing-test tasks can be authored simultaneously:
Task T020: "Write failing tests for ItemModelAdmin"
Task T021: "Write failing tests for TagModelAdmin"
Task T022: "Write failing tests for ItemParentLinkInline"
Task T023: "Write failing tests for ItemTagLinkInline"
```

---

## Implementation Strategy

### MVP First (US1 Only — Cycle Detection)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: US1 (CategoryParentLinkInline with cycle detection)
4. **STOP and VALIDATE**: `pytest tests/contrib/django/test_admin_service_routing.py -k "parent_link"` passes
5. Cycle detection is now enforced in the admin ✅

### Incremental Delivery

1. Setup + Foundational → service delete methods available
2. US1 → cycle detection enforced → MVP
3. US2 → all Category mutations through service
4. US3 + US4 → Item/Tag mutations + inlines through service
5. Polish → quality gates green → ready for PR

---

## Notes

- [P] tasks operate on different files or independent test functions — safe to parallelise
- Every test task must be written and confirmed FAILING before the paired implementation task starts (TDD mandatory per CLAUDE.md)
- Do NOT call `super().save_model()`, `super().delete_model()`, or `super().delete_queryset()` in overrides — the service call replaces the ORM call entirely
- Patch target for all admin tests: `taxomesh.contrib.django.admin.TaxomeshService`
- `CategoryParentLinkInline` uses `CategoryParentLinkForm` with `clean()` that calls `check_no_cycle()` (domain-level, read-only) and a self-reference guard — the ORM write is Django's native formset save after `clean()` passes; `save_model()` on the inline is dead code in Django's formset path and is not used
- Commit after each checkpoint, not after each individual task
- **Django inline FK fix (post-implement fix for FR-001/FR-002)**: `CategoryModelAdmin.save_model` and `ItemModelAdmin.save_model` were updated on create to sync the service-returned PK back to the Django ORM instance (`obj.pk = domain_obj.pk`, `obj._state.adding = False`). Django 4.0+ raises `ValueError` if an inline formset tries to FK-reference a parent instance that has never been through `obj.save()`. Since the service bypasses `obj.save()`, this sync is required. Covered by `test_save_model_create_syncs_obj_state` in `test_admin_service_routing.py`.
- **`CategoryModel.__str__` (out-of-cycle cosmetic fix)**: A `__str__` method returning `"<name> (<category_id>)"` was added to `CategoryModel` to improve admin dropdown readability. No business-rule implications; documented in spec.md Assumptions.
- **Mixin extraction (post-implement fix)**: Tasks T011/T024/T025 described adding `_make_service()` to each admin class individually. After the first implementation pass, `/speckit.analyze` identified this as a Constitution XI violation (near-identical classes must extract a shared mixin). `TaxomeshAdminMixin` was extracted and all six classes now inherit from it. T011/T024/T025 are marked complete because the method exists and works; the mixin is the final form.
- **Cycle detection bug fix (post-implement correctness fix for FR-009/SC-002)**: `InlineModelAdmin.save_model()` is never called by Django's inline formset save flow — it was dead code. The real pre-save hook is `ModelForm.clean()`. `CategoryParentLinkForm` was added with `clean()` performing self-reference and cycle checks; the inline sets `form = CategoryParentLinkForm`. Tests live in `TestCategoryParentLinkForm` in `test_admin_service_routing.py`. An explicit self-reference guard (`category_id == parent_id`) was also added to `service.add_category_parent()` for a clear error message at the service layer.
- **`ROOT_CATEGORY_NAME` moved to domain constants**: Relocated from `taxomesh/application/service.py` to `taxomesh/domain/constants.py`. All callers updated. No behaviour change.
- **`Category.is_root` property**: Added read-only `is_root: bool` property to the `Category` domain model (`self.name == ROOT_CATEGORY_NAME`). Tests in `tests/domain/test_models.py`.
- **Root category hidden from admin (out-of-cycle UX fix)**: `CategoryModelAdmin.get_queryset()` now excludes the root category from the changelist. `CategoryParentLinkInline.formfield_for_foreignkey()` now excludes root from the `parent_category` dropdown. Tests in `TestRootCategoryHidden` in `tests/contrib/django/test_admin.py`.
