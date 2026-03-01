# Implementation Plan: Admin Service Layer

**Branch**: `016-admin-service-layer` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/016-admin-service-layer/spec.md`

## Summary

Refactor `taxomesh/contrib/django/admin.py` so that every admin mutation
(create, update, delete, bulk-delete, and inline row changes) routes through
`TaxomeshService` rather than calling the ORM directly. This enforces all domain
business rules — including DAG cycle detection — on every admin operation.

As a prerequisite discovered during planning, two new service methods
(`remove_category_parent`, `remove_item_from_category`) and two new repository
port methods (`delete_category_parent_link`, `delete_item_parent_link`) must be
added and implemented in all three repository adapters before the admin refactor
can be completed.

Three new inlines are added: `CategoryParentLink` on `CategoryModelAdmin`,
and `ItemParentLink` + `ItemTagLink` on `ItemModelAdmin`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin framework), Pydantic v2 (domain models), Typer ≥ 0.12
**Storage**: DjangoRepository — Django ORM (PostgreSQL/SQLite compatible)
**Testing**: pytest + pytest-django; mocks via `unittest.mock.patch`
**Target Platform**: Django web application (optional taxomesh backend)
**Project Type**: Library contrib module
**Performance Goals**: N/A — admin is a low-traffic staff tool
**Constraints**: Must not break existing admin tests; mypy --strict must pass
**Scale/Scope**: Affects one module (`admin.py`) and its test file; new service/repo methods affect the full adapter stack

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal architecture | ✅ PASS | admin → service → repo → ORM; no layer inversion |
| II. TaxomeshService as single facade | ✅ PASS | admin uses `TaxomeshService`; no direct repo calls |
| III. Repository as Protocol | ✅ PASS | New methods added to Protocol; all three adapters implement |
| IV. Pydantic models + mypy strict | ✅ PASS | No model changes; existing models used |
| V. Custom exception hierarchy | ✅ PASS | `TaxomeshValidationError` caught and surfaced in admin |
| VI. DAG integrity in domain layer | ✅ PASS | Cycle detection stays in service/domain; admin just catches errors |
| VIII. Quality gates | ✅ PASS | All gates must pass before merge |
| X. Named constants | ✅ PASS | No new magic literals; follow existing patterns |
| XI. OO by default | ✅ PASS | `TaxomeshAdminMixin` extracts shared `_make_service()`; all six admin classes inherit it |

**Spec assumption correction**: The spec states "no new service methods need to be
added". Research found this is incorrect — `remove_category_parent` and
`remove_item_from_category` (and their repo port methods) are missing and must be
added. See `research.md` Finding 1 & 2.

## Project Structure

### Documentation (this feature)

```text
specs/016-admin-service-layer/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
taxomesh/
├── ports/
│   └── repository.py               ← add delete_category_parent_link, delete_item_parent_link
├── adapters/
│   └── repositories/
│       ├── django_repository.py    ← implement 2 new delete methods
│       ├── json_repository.py      ← implement 2 new delete methods
│       └── yaml_repository.py      ← implement 2 new delete methods
├── application/
│   └── service.py                  ← add remove_category_parent, remove_item_from_category
└── contrib/
    └── django/
        └── admin.py                ← major refactor (see Implementation Design below)

tests/
└── contrib/
    └── django/
        ├── test_admin.py                    ← update existing smoke tests
        └── test_admin_service_routing.py    ← new: verify service-routing behaviour
```

**Additional test files to extend** (new service methods):
```text
tests/service/
├── test_category_parent_upsert.py    ← add remove_category_parent tests
├── test_item_parent_upsert.py        ← add remove_item_from_category tests
└── conftest.py                       ← extend InMemoryRepository with new delete methods
```

## Implementation Design

### Step 1 — Repository Port (lowest layer first)

Add to `TaxomeshRepositoryBase` in `taxomesh/ports/repository.py`:

```
delete_category_parent_link(category_id: UUID, parent_category_id: UUID) -> bool
delete_item_parent_link(item_id: UUID, category_id: UUID) -> bool
```

Both return `True` if deleted, `False` if not found (idempotent).

### Step 2 — Repository Implementations

Implement both methods in `DjangoRepository`, `JsonRepository`, `YamlRepository`.

- **DjangoRepository**: use `CategoryParentLinkModel.objects.filter(...).delete()`
  / `ItemParentLinkModel.objects.filter(...).delete()`. Return `True` if
  `deleted_count > 0`.
- **JsonRepository / YamlRepository**: filter out the target link from the
  in-memory list and write back atomically (same pattern as other deletions in
  these repos).

### Step 3 — Service Methods

Add to `TaxomeshService` in `taxomesh/application/service.py`:

**`remove_category_parent(category_id: UUID, parent_id: UUID) -> None`**
- Validate `category_id` exists (`get_category(category_id)`).
- Validate `parent_id` exists (`get_category(parent_id)`).
- Delegate to `self._repo.delete_category_parent_link(category_id, parent_id)`.
- Call `clear_all_caches()`.

**`remove_item_from_category(item_id: UUID, category_id: UUID) -> None`**
- Validate `item_id` exists (`get_item(item_id)`).
- Validate `category_id` exists (`get_category(category_id)`).
- Delegate to `self._repo.delete_item_parent_link(item_id, category_id)`.
- Call `clear_all_caches()`.

### Step 4 — Admin Refactor

**`TaxomeshAdminMixin`** (shared mixin — extracted as a constitution XI fix after initial implementation):

```python
class TaxomeshAdminMixin:
    def _make_service(self) -> TaxomeshService:
        return TaxomeshService(repository=DjangoRepository())
```

All six admin classes (`CategoryModelAdmin`, `ItemModelAdmin`, `TagModelAdmin`,
`CategoryParentLinkInline`, `ItemParentLinkInline`, `ItemTagLinkInline`) inherit from this mixin.
This eliminates the six-way duplication of `_make_service()` that was present in the first
implementation pass.

---

**`CategoryModelAdmin`** changes:

| Hook | Action |
|---|---|
| `save_model(request, obj, form, change)` | Call `svc.create_category(...)` or `svc.update_category(...)` depending on `change`. Do NOT call `super()`. Catch `TaxomeshValidationError` → `message_user(ERROR)`. |
| `delete_model(request, obj)` | Call `svc.delete_category(obj.category_id)`. Do NOT call `super()`. Catch `TaxomeshError` → `message_user(ERROR)`. |
| `delete_queryset(request, queryset)` | Iterate; call `svc.delete_category(obj.category_id)` per object. Collect errors; report via `message_user(ERROR)`. |
| `inlines` | Add `CategoryParentLinkInline`. |

**`CategoryParentLinkInline`** (new `TabularInline` subclass):

- `model = CategoryParentLinkModel`
- `form = CategoryParentLinkForm` (custom `ModelForm` subclass — see below).
- `delete_model(request, obj)`: call
  `svc.remove_category_parent(obj.category_id, obj.parent_category_id)`.
  Do NOT call `super()`.

> **Note on inline save flow**: `InlineModelAdmin.save_model()` is **never
> called** by Django's inline formset save path — Django calls
> `formset.save()` → `form.instance.save()` directly. Therefore
> `save_model` cannot intercept the ORM write for add operations. The correct
> hook is `ModelForm.clean()`, which runs before any persistence.

**`CategoryParentLinkForm`** (custom `ModelForm` for the inline):

- `clean()`: reads `category` and `parent_category` from `cleaned_data`.
  - Self-reference guard: if `cat_id == parent_id`, raise
    `forms.ValidationError("A category cannot be its own parent.")`.
  - Cycle check: call `check_no_cycle(cat_id, parent_id, repo.list_category_parent_links())`
    from `taxomesh.domain.dag` (read-only domain function). If it raises
    `TaxomeshCyclicDependencyError`, wrap in `forms.ValidationError(str(exc))`.
  - On valid data, return `cleaned_data`. The ORM write is performed by
    Django's native formset save after `clean()` passes.

---

**`ItemModelAdmin`** changes:

| Hook | Action |
|---|---|
| `save_model(request, obj, form, change)` | Call `svc.create_item(...)` or `svc.update_item(...)`. Do NOT call `super()`. Catch `TaxomeshValidationError` → `message_user(ERROR)`. |
| `delete_model(request, obj)` | Call `svc.delete_item(obj.item_id)`. Do NOT call `super()`. |
| `delete_queryset(request, queryset)` | Iterate; call `svc.delete_item(obj.item_id)` per object. |
| `inlines` | Add `ItemParentLinkInline`, `ItemTagLinkInline`. |

**`ItemParentLinkInline`** (new `TabularInline` subclass):
- `model = ItemParentLinkModel`
- `save_model`: call `svc.place_item_in_category(obj.item_id, obj.category_id, obj.sort_index)`. Do NOT call `super()`. Catch `TaxomeshError` → `message_user(ERROR)`.
- `delete_model`: call `svc.remove_item_from_category(obj.item_id, obj.category_id)`. Do NOT call `super()`.

**`ItemTagLinkInline`** (new `TabularInline` subclass):
- `model = ItemTagLinkModel`
- `save_model`: call `svc.assign_tag(obj.tag_id, obj.item_id)`. Do NOT call `super()`. Catch `TaxomeshError` → `message_user(ERROR)`.
- `delete_model`: call `svc.remove_tag(obj.tag_id, obj.item_id)`. Do NOT call `super()`.

---

**`TagModelAdmin`** changes:

| Hook | Action |
|---|---|
| `save_model(request, obj, form, change)` | Call `svc.create_tag(...)` or `svc.update_tag(...)`. Do NOT call `super()`. Catch `TaxomeshValidationError` → `message_user(ERROR)`. |
| `delete_model(request, obj)` | Call `svc.delete_tag(obj.tag_id)`. Do NOT call `super()`. |
| `delete_queryset(request, queryset)` | Iterate; call `svc.delete_tag(obj.tag_id)` per object. |

---

**`CategoryGraphProxyAdmin`** — **unchanged** (no mutations).

> **FR-006 / FR-007 coverage note**: Read operations (list view, detail view, graph view) are
> intentionally out of scope for service-layer routing. FR-006 (all read operations must continue
> without regression) and FR-007 (graph view unchanged) are verified by the existing smoke tests
> in `tests/contrib/django/test_admin.py` — specifically the admin registration checks and graph
> view tests which remain valid and unchanged.

### Step 5 — Tests

**`tests/contrib/django/test_admin_service_routing.py`** (new file):

Tests are grouped by admin class. Each test patches
`taxomesh.contrib.django.admin.TaxomeshService` to inject a mock service, then
triggers the relevant admin HTTP request or method call, and asserts the correct
service method was called with the right arguments.

Key test cases:
- `CategoryModelAdmin.save_model` → create path calls `service.create_category`
- `CategoryModelAdmin.save_model` → update path calls `service.update_category`
- `CategoryModelAdmin.delete_model` → calls `service.delete_category`
- `CategoryModelAdmin.delete_queryset` → calls `service.delete_category` per object
- `CategoryParentLinkInline.clean()` → cycle raises `ValidationError`
- `CategoryParentLinkInline.clean()` → valid link passes; ORM write proceeds natively via Django formset (`save_model` is not called for add operations)
- `CategoryParentLinkInline.delete_model` → calls `service.remove_category_parent`
- `ItemModelAdmin.save_model` → create/update paths
- `ItemModelAdmin.delete_model` / `delete_queryset`
- `ItemParentLinkInline.save_model` → calls `service.place_item_in_category`
- `ItemParentLinkInline.delete_model` → calls `service.remove_item_from_category`
- `ItemTagLinkInline.save_model` → calls `service.assign_tag`
- `ItemTagLinkInline.delete_model` → calls `service.remove_tag`
- `TagModelAdmin.save_model` → create/update paths
- `TagModelAdmin.delete_model` / `delete_queryset`
- `TaxomeshValidationError` in `save_model` → displayed via `message_user`
- `TaxomeshError` in `delete_model` → displayed via `message_user`

**`tests/service/test_category_parent_upsert.py`** — add tests for
`remove_category_parent`:
- Valid removal succeeds
- Removing non-existent link is a no-op (no error)
- Removing with non-existent category raises `TaxomeshCategoryNotFoundError`

**`tests/service/test_item_parent_upsert.py`** — add tests for
`remove_item_from_category`:
- Valid removal succeeds
- Removing non-existent placement is a no-op
- Removing with non-existent item raises `TaxomeshItemNotFoundError`

**`tests/contrib/django/test_admin.py`** — existing tests:
- Smoke tests (registration, labels) remain valid; no changes needed.
- Graph view tests remain valid (graph view is unchanged).

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| New repo port methods | Inline row deletion requires a delete path in the protocol | Direct ORM delete in service violates Protocol principle (III) |
| New service methods | Admin must call service to remove links; service had no remove methods | Admin calling repo directly violates hexagonal dependency rule |
| `clean()` probe for cycle detection | Cycle errors must be visible as form errors, not just admin messages | `save_model`-only approach cannot inject form-field-level errors after validation completes |
