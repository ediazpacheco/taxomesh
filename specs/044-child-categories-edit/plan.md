# Implementation Plan: Admin Child Categories Editable Inline

**Branch**: `044-child-categories-edit` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/044-child-categories-edit/spec.md`

## Summary

Convert the read-only `CategoryChildLinkInline` (introduced in spec 042) into a fully editable
inline that mirrors the existing `CategoryParentLinkInline`. The change is contained to one file:
`taxomesh/contrib/django/admin.py`. A new `CategoryChildLinkForm` adds cycle detection and
duplicate validation. The inline gains `save_model` / `delete_model` hooks that delegate to
`TaxomeshService`, and an autocomplete selector for the child category field. No migration is
required.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin framework), Pydantic v2 (domain models)
**Storage**: Django ORM — `CategoryParentLinkModel` table; no migrations required
**Testing**: pytest + pytest-django
**Target Platform**: Django admin web interface (contrib package)
**Project Type**: Django admin UI enhancement (adapter layer)
**Performance Goals**: Standard Django admin page response times
**Constraints**: No new migrations, no new models, no new URLs
**Scale/Scope**: Single inline class + form class; one test class

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I — Hexagonal architecture | ✅ Change is in `taxomesh.contrib.django` (adapter layer). Save/delete hooks delegate to `TaxomeshService` (application layer), never touching the ORM directly. Pattern already established in `CategoryParentLinkInline`. |
| II — TaxomeshService is the single facade | ✅ All writes go through `svc.add_category_parent()` / `svc.remove_category_parent()`. |
| IV — Pydantic + mypy strict | ✅ New form and inline typed correctly; no `Any` required. |
| V — Exception hierarchy | ✅ `TaxomeshCyclicDependencyError` caught in form `clean()` and converted to `ValidationError`. Duplicate caught via `unique_together` IntegrityError or service error. |
| VI — DAG integrity | ✅ Cycle detection stays in domain layer; form catches and surfaces the error. |
| VIII — Quality gates | ✅ All gates must pass before PR. |
| X — Named constants | ✅ `ROOT_CATEGORY_NAME` already a named constant; reused as-is. |
| XI — OO by default | ✅ New form and inline are classes. |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/044-child-categories-edit/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
taxomesh/contrib/django/
└── admin.py             # Add CategoryChildLinkForm; replace CategoryChildLinkInline

tests/contrib/django/
└── test_admin.py        # Replace/extend TestCategoryChildLinkInline
```

**Structure Decision**: Single-project layout. This feature touches exactly two files in the
existing project structure — the Django contrib admin module and its test file.

## Implementation Phases

### Phase A — Tests (TDD — must run before implementation)

Write failing tests in `tests/contrib/django/test_admin.py` for:

1. `TestCategoryChildLinkForm`
   - `test_valid_form_creates_child_link` — form with valid child + sort index is valid
   - `test_cycle_raises_validation_error` — form with child that would create a cycle is invalid
   - `test_duplicate_raises_validation_error` — form with already-linked child is invalid
   - `test_self_link_raises_validation_error` — form with child == parent is invalid

2. `TestCategoryChildLinkInline` (replace read-only tests)
   - `test_inline_registered_on_category_model_admin` — inline present in `CategoryModelAdmin.inlines`
   - `test_has_add_permission` — returns `True` (no longer blocked)
   - `test_has_change_permission` — returns `True`
   - `test_has_delete_permission` — returns `True`
   - `test_fk_name_is_parent_category` — `fk_name == "parent_category"`
   - `test_autocomplete_fields_includes_category` — `"category"` in `autocomplete_fields`
   - `test_save_model_calls_service_add` — `save_model()` calls `svc.add_category_parent()`
   - `test_delete_model_calls_service_remove` — `delete_model()` calls `svc.remove_category_parent()`
   - `test_root_category_excluded_from_child_selector` — root category absent from queryset

### Phase B — Implementation

Modify `taxomesh/contrib/django/admin.py`:

1. **Add `CategoryChildLinkForm`** (after `CategoryParentLinkForm`):
   - `Meta.model = CategoryParentLinkModel`
   - `clean()` validates: no self-link, no cycle (catch `TaxomeshCyclicDependencyError` from service)
   - Duplicate prevention handled by Django's `unique_together` validation (no extra code needed)

2. **Replace `CategoryChildLinkInline`**:
   - Remove `_ReadOnlyInlineMixin` base
   - Add `TaxomeshAdminMixin` base (already used by `CategoryParentLinkInline`)
   - Set `form = CategoryChildLinkForm`
   - Set `autocomplete_fields = ["category"]`
   - Add `save_model()` → `svc.add_category_parent(obj.category_id, obj.parent_category_id)`
   - Add `delete_model()` → `svc.remove_category_parent(obj.category_id, obj.parent_category_id)`
   - Add `formfield_for_foreignkey()` to exclude `ROOT_CATEGORY_NAME` from child selector

No changes to `CategoryModelAdmin` — the inline is already registered.

## Artifact Index

| Artifact | Path | Status |
|----------|------|--------|
| Spec | `specs/044-child-categories-edit/spec.md` | ✅ Complete |
| Research | `specs/044-child-categories-edit/research.md` | ✅ Complete |
| Data model | `specs/044-child-categories-edit/data-model.md` | ✅ Complete |
| Quickstart | `specs/044-child-categories-edit/quickstart.md` | ✅ Complete |
| Tasks | `specs/044-child-categories-edit/tasks.md` | ⏳ Next (`/speckit.tasks`) |
