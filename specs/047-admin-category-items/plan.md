# Implementation Plan: Category Items Inline on Admin Change Page

**Branch**: `047-admin-category-items` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/047-admin-category-items/spec.md`

## Summary

Add a `CategoryItemLinkInline` tabular inline to the `CategoryModelAdmin` change page, allowing admins to view, add, and remove item–category placements directly from a category record. The inline uses the existing `ItemParentLinkModel` join model and existing service methods (`place_item_in_category` / `remove_item_from_category`). No new data model, no new service methods, no migrations.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin inline framework), Pydantic v2 (domain models — via `TaxomeshService`)
**Storage**: Django ORM — `taxomesh_item_parent_link` table (existing; no migration)
**Testing**: pytest + pytest-django; existing `tests/contrib/django/` suite
**Target Platform**: Django admin UI
**Project Type**: Django contrib module (optional adapter within taxomesh library)
**Performance Goals**: Standard Django admin page load; no special performance target
**Constraints**: Must route all writes through `TaxomeshService`; must pass `mypy --strict`; must not duplicate `ItemParentLinkInline` class (reuse pattern via mixin or direct mirror)
**Scale/Scope**: Single inline class + one test file addition

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ PASS | Inline is in `adapters/` (Django contrib); all writes route through `TaxomeshService` (application layer) |
| II — TaxomeshService is the single facade | ✅ PASS | `save_model` and `delete_model` call `self._make_service()` then delegate to service methods |
| III — Repository as Protocol | ✅ PASS | No direct repository access from inline |
| IV — Pydantic models + mypy strict | ✅ PASS | No new domain models; existing models are Pydantic |
| V — Custom exception hierarchy | ✅ PASS | `TaxomeshError` caught in `save_model`; surfaced via `message_user` |
| VI — DAG integrity | ✅ PASS | Item placements are flat; DAG check not required |
| VII — Spec-driven development | ✅ PASS | This plan is the spec artifact |
| VIII — Quality gates | ✅ PASS | Must pass ruff, mypy --strict, pytest ≥ 80% cov |
| IX — Framework-agnostic handlers | ✅ PASS | Feature is in `contrib/django/` (explicit Django adapter); not in `contrib/api/` |
| X — Named constants | ✅ PASS | No new magic literals introduced; `ROOT_CATEGORY_NAME` already a named constant |
| XI — Object-oriented by default | ✅ PASS | New inline is a class; extends existing class hierarchy |

**No violations. No complexity tracking required.**

## Project Structure

### Documentation (this feature)

```text
specs/047-admin-category-items/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
taxomesh/
└── contrib/
    └── django/
        └── admin.py          # Add CategoryItemLinkInline; add to CategoryModelAdmin.inlines

tests/
└── contrib/
    └── django/
        └── test_admin.py     # Add tests for CategoryItemLinkInline
```

**Structure Decision**: Single-project; all changes are in the existing Django contrib adapter. No new files required in production code or tests.

## Implementation Design

### New class: `CategoryItemLinkInline`

Mirrors `CategoryChildLinkInline` in structure. Placed in the "Item inlines" section of `admin.py`, alongside the existing `ItemParentLinkInline`.

```python
class CategoryItemLinkInline(TaxomeshAdminMixin, admin.TabularInline):
    """Inline for managing item placements on the Category admin page."""

    model = ItemParentLinkModel
    fk_name = "category"
    extra = 0
    verbose_name = "Item"
    verbose_name_plural = "Items"
    autocomplete_fields = ["item"]

    def save_model(self, request, obj, form, change):
        svc = self._make_service()
        try:
            svc.place_item_in_category(obj.item_id, obj.category_id, obj.sort_index)
        except TaxomeshError as exc:
            from django.contrib import messages
            self.message_user(request, str(exc), level=messages.ERROR)

    def delete_model(self, request, obj):
        svc = self._make_service()
        svc.remove_item_from_category(obj.item_id, obj.category_id)
```

### `CategoryModelAdmin` change

Add `CategoryItemLinkInline` to the inlines list:

```python
inlines = [CategoryParentLinkInline, CategoryChildLinkInline, CategoryItemLinkInline]
```

### No new service methods

`place_item_in_category` and `remove_item_from_category` already exist on `TaxomeshService` and are used by `ItemParentLinkInline`.

### No new form class

The ORM `unique_together` constraint on `ItemParentLinkModel` prevents duplicate links. No custom form validation is needed beyond what Django provides automatically.

## Test Plan

Tests live in `tests/contrib/django/test_admin.py` (existing file). New test cases:

1. **Category change page shows items** — GET the category change page; assert the items inline renders all assigned items.
2. **Add item to category via inline** — POST with a new item link; assert the link exists in the ORM.
3. **Remove item from category via inline** — POST with delete flag on an existing link; assert the link is removed but the item record still exists.
4. **Duplicate item link is rejected** — POST adding the same item twice; assert a validation error and only one record in the ORM.

All tests use `pytest-django` and the existing `RequestFactory` / admin-site test setup pattern established in the test suite.
