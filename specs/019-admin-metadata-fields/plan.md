# Implementation Plan: Admin Metadata Fields

**Branch**: `019-admin-metadata-fields` | **Date**: 2026-03-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-admin-metadata-fields/spec.md`

## Summary

Expose the `metadata` JSONField on `CategoryModel` and `ItemModel` in the Django admin detail
views so administrators can view and edit it. The `metadata` field already exists on both models
and in the database schema. The admin `fields` tuples currently omit it.

Because `save_model` for both `CategoryModelAdmin` and `ItemModelAdmin` routes all persistence
through `TaxomeshService`, and because `service.update_category` and `service.update_item` do
not yet accept a `metadata` argument, this feature requires two layers of work:

1. **Service layer** — add `metadata` parameter to `update_category` and `update_item`.
2. **Admin layer** — add `"metadata"` to the `fields` tuples; pass `obj.metadata` in
   `save_model` for both create and update paths.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin), taxomesh service layer
**Storage**: Django ORM — `CategoryModel.metadata` and `ItemModel.metadata` are `JSONField(blank=True, default=dict)`
**Testing**: pytest with `pytest-django`
**Target Platform**: Django admin backend
**Project Type**: library (contrib/django optional adapter)
**Performance Goals**: N/A — single-record admin form save
**Constraints**: Must pass ruff, mypy --strict, pytest ≥ 80% coverage
**Scale/Scope**: 2 model admins; 2 service methods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal architecture | ✅ PASS | All changes stay within `adapters/` (Django contrib) and `application/`. No domain layer changes. |
| II. TaxomeshService is the single facade | ✅ PASS | `update_category` and `update_item` extended — not bypassed. Service remains the only mutation path. |
| III. Repository as Protocol | ✅ PASS | No protocol changes. |
| IV. Pydantic + mypy strict | ✅ PASS | `metadata: dict[str, Any] | None` is already the type used everywhere. No new domain model changes. |
| V. Custom exception hierarchy | ✅ PASS | No new error paths. |
| VI. DAG integrity | ✅ PASS | Not applicable. |
| VII. Spec-driven development | ✅ PASS | Spec exists at `specs/019-admin-metadata-fields/spec.md`. |
| VIII. Quality gates | ✅ PASS | Plan produces only testable, typed, linted code. |
| IX. Pluggable REST views | ✅ PASS | Not applicable. |
| X. Named constants | ✅ PASS | No new magic literals. Field names in Django admin `fields` tuples are standard framework config. |
| XI. OOP by default | ✅ PASS | Changes stay within existing `ModelAdmin` subclasses. |

**Post-design re-check**: All principles still pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/019-admin-metadata-fields/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── application/
│   └── service.py           # MODIFY: add metadata param to update_category, update_item
└── contrib/
    └── django/
        └── admin.py         # MODIFY: CategoryModelAdmin.fields, ItemModelAdmin.fields + save_model

tests/
└── contrib/
    └── django/
        └── test_admin.py    # MODIFY: add metadata field presence tests
tests/
├── service/
│   ├── test_service_categories.py  # MODIFY: add update_category metadata tests
│   └── test_service_items.py       # MODIFY: add update_item metadata tests
```

**Structure Decision**: Single-project layout. No new files — all changes are targeted edits to
existing files in the `application/` and `contrib/django/` layers.

## Architectural Discovery

During planning, a dependency gap was identified: `service.update_category` and
`service.update_item` do not accept a `metadata` argument. Without this, adding `"metadata"` to
the admin `fields` tuple would show the field but silently discard any edits (the service
re-fetches the record and saves only the fields it knows about).

**Decision**: Extend both service methods to accept `metadata: dict[str, Any] | None = None`.
When `None`, metadata is left unchanged on the existing record (consistent with how `name`,
`slug`, etc. work). This is the minimal change required to fulfil FR-004 without bypassing the
service layer.

This is confirmed in-scope: FR-004 requires that saving the metadata field persists the value.
The service is the single write path (Constitution Principle II). No domain model changes are
needed — `Category.metadata` and `Item.metadata` already exist.
