# Tasks: Admin Metadata Fields

**Input**: Design documents from `/specs/019-admin-metadata-fields/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**TDD**: Test tasks are included per CLAUDE.md mandatory TDD policy — every failing test must be
written and confirmed failing before the corresponding implementation task runs.

**Organization**: Tasks grouped by user story. Phase 2 (Foundational) blocks both user stories
because `update_category` and `update_item` must accept `metadata` before the admin save paths work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)

---

## Phase 2: Foundational — Service Layer Metadata Support

**Purpose**: Extend `TaxomeshService.update_category` and `TaxomeshService.update_item` to
accept a `metadata` parameter. Both user stories depend on this — without it, admin saves
silently discard metadata edits.

**⚠️ CRITICAL**: No user story admin work can begin until this phase is complete.

### Tests (write first — confirm FAIL before implementation)

- [x] T001 [P] Write failing test for `update_category` with metadata in `tests/service/test_service_categories.py` — assert that calling `update_category(category_id=..., metadata={"key": "value"})` persists the new metadata and that calling with `metadata=None` leaves existing metadata unchanged
- [x] T002 [P] Write failing test for `update_item` with metadata in `tests/service/test_service_items.py` — assert that calling `update_item(item_id=..., metadata={"key": "value"})` persists the new metadata and that calling with `metadata=None` leaves existing metadata unchanged

### Implementation

- [x] T003 Implement `metadata: dict[str, Any] | None = None` parameter on `TaxomeshService.update_category` in `taxomesh/application/service.py` — when not None, replace `category.metadata` before calling `self._repo.save_category(category)`; when None, leave `category.metadata` unchanged
- [x] T004 Implement `metadata: dict[str, Any] | None = None` parameter on `TaxomeshService.update_item` in `taxomesh/application/service.py` — when not None, replace `item.metadata` before calling `self._repo.save_item(item)`; when None, leave `item.metadata` unchanged

**Checkpoint**: `pytest tests/service/test_service_categories.py tests/service/test_service_items.py` passes. Foundation ready.

---

## Phase 3: User Story 1 — Category Metadata in Admin (Priority: P1) 🎯 MVP

**Goal**: `CategoryModelAdmin` exposes a `metadata` field on the detail page; admin saves
route metadata through the service layer.

**Independent Test**: Instantiate `CategoryModelAdmin(CategoryModel, AdminSite())` and assert
`"metadata" in admin_obj.fields`; call `save_model` on a mock and assert the service receives
`metadata=obj.metadata`.

### Tests (write first — confirm FAIL before implementation)

- [x] T005 [US1] Write failing tests for Category admin metadata in `tests/contrib/django/test_admin.py`:
  - `test_category_admin_fields_includes_metadata`: assert `"metadata" in CategoryModelAdmin(CategoryModel, AdminSite()).fields`
  - `test_category_admin_save_model_passes_metadata_on_update`: mock `_make_service`, call `save_model(change=True)` with `obj.metadata = {"x": 1}`, assert `svc.update_category` was called with `metadata={"x": 1}`
  - `test_category_admin_save_model_passes_metadata_on_create`: mock `_make_service`, call `save_model(change=False)` with `obj.metadata = {"x": 1}`, assert `svc.create_category` was called with `metadata={"x": 1}`

### Implementation

- [x] T006 [US1] Add `"metadata"` at the end of `CategoryModelAdmin.fields` tuple in `taxomesh/contrib/django/admin.py` — change `fields = ("name", "slug", "description", "enabled", "external_id")` to `fields = ("name", "slug", "description", "enabled", "external_id", "metadata")`
- [x] T007 [US1] Update `CategoryModelAdmin.save_model` in `taxomesh/contrib/django/admin.py` — pass `metadata=obj.metadata` in both the `svc.create_category(...)` call (on create) and the `svc.update_category(...)` call (on change)

**Checkpoint**: `pytest tests/contrib/django/test_admin.py` passes for all category metadata tests. US1 complete.

---

## Phase 4: User Story 2 — Item Metadata in Admin (Priority: P2)

**Goal**: `ItemModelAdmin` exposes a `metadata` field on the detail page; admin saves route
metadata through the service layer.

**Independent Test**: Instantiate `ItemModelAdmin(ItemModel, AdminSite())` and assert
`"metadata" in admin_obj.fields`; call `save_model` on a mock and assert the service receives
`metadata=obj.metadata`.

### Tests (write first — confirm FAIL before implementation)

- [x] T008 [US2] Write failing tests for Item admin metadata in `tests/contrib/django/test_admin.py`:
  - `test_item_admin_fields_includes_metadata`: assert `"metadata" in ItemModelAdmin(ItemModel, AdminSite()).fields`
  - `test_item_admin_save_model_passes_metadata_on_update`: mock `_make_service`, call `save_model(change=True)` with `obj.metadata = {"x": 1}`, assert `svc.update_item` was called with `metadata={"x": 1}`
  - `test_item_admin_save_model_passes_metadata_on_create`: mock `_make_service`, call `save_model(change=False)` with `obj.metadata = {"x": 1}`, assert `svc.create_item` was called with `metadata={"x": 1}`

### Implementation

- [x] T009 [US2] Add `"metadata"` at the end of `ItemModelAdmin.fields` tuple in `taxomesh/contrib/django/admin.py` — change `fields = ("name", "external_id", "slug", "enabled")` to `fields = ("name", "external_id", "slug", "enabled", "metadata")`
- [x] T010 [US2] Update `ItemModelAdmin.save_model` in `taxomesh/contrib/django/admin.py` — pass `metadata=obj.metadata` in both the `svc.create_item(...)` call (on create) and the `svc.update_item(...)` call (on change)

**Checkpoint**: `pytest tests/contrib/django/test_admin.py` passes for all item metadata tests. US2 complete.

---

## Phase 5: Polish & Quality Gates

**Purpose**: Verify all quality gates pass end-to-end.

- [x] T011 Run full quality gate suite from repo root: `ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80` — all must pass with zero errors

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — start immediately
- **US1 (Phase 3)**: Depends on Phase 2 completion (T003 + T004 done)
- **US2 (Phase 4)**: Depends on Phase 2 completion (T003 + T004 done); can run in parallel with US1 since they edit different admin class regions
- **Polish (Phase 5)**: Depends on all prior phases complete

### Within Phase 2

```
T001 [P] ─┐
           ├─→ T003 ─→ T004
T002 [P] ─┘
```

T001 and T002 are parallel (different test files).
T003 and T004 are sequential (same file: service.py).

### Within Phase 3 (US1)

```
T005 → T006 → T007
```

All sequential: T005 writes failing tests, T006/T007 make them pass (same file: admin.py).

### Within Phase 4 (US2)

```
T008 → T009 → T010
```

All sequential: T008 writes failing tests, T009/T010 make them pass (same file: admin.py).

### Parallel Opportunities

- T001 ∥ T002 (Phase 2 tests — different files)
- Phase 3 (US1) ∥ Phase 4 (US2) — both depend on Phase 2; US1 and US2 touch different class
  definitions within admin.py but for solo implementation, run sequentially to avoid conflicts

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 2: Foundational (T001 → T002 → T003 → T004)
2. Complete Phase 3: US1 (T005 → T006 → T007)
3. **STOP AND VALIDATE**: `pytest tests/contrib/django/test_admin.py -k metadata`
4. If passing: Category metadata is live

### Full Delivery

1. Phase 2 → Phase 3 → Phase 4 → Phase 5
2. Each phase checkpoint validates incrementally

---

## Notes

- [P] = different files, no shared incomplete dependencies
- TDD is mandatory per CLAUDE.md — confirm each test FAILS before the implementation task
- T003 and T004 edit the same file (service.py) → run sequentially
- T006/T007 and T009/T010 edit the same file (admin.py) → run sequentially within each story
- Mark each task `[X]` in this file as it completes
