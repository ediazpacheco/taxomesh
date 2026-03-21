# Implementation Plan: Admin Child Categories Display

**Branch**: `042-admin-child-categories` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/042-admin-child-categories/spec.md`

## Summary

Add a read-only `CategoryChildLinkInline` to `CategoryModelAdmin` that shows the direct child categories of the category being viewed. The inline reverses the existing `CategoryParentLinkModel` join by using `fk_name = "parent_category"`, mirroring the pattern of the existing `IncomingRelationInline` (read-only, no add/change/delete permissions).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2, Pydantic v2 (domain models)
**Storage**: Django ORM — no new migrations required; uses the existing `CategoryParentLinkModel` table
**Testing**: pytest + pytest-django; existing `tests/contrib/django/` suite
**Target Platform**: Django admin web interface
**Project Type**: Library with optional Django contrib adapter
**Performance Goals**: N/A — admin page load; no performance-critical path
**Constraints**: Read-only inline — no save/delete service calls required
**Scale/Scope**: Single inline class; two lines of change in `CategoryModelAdmin.inlines`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | Change is entirely in `taxomesh/contrib/django/admin.py` (adapter layer). No domain or application layer touched. |
| II. TaxomeshService is the single facade | ✅ PASS | Read-only inline; no service calls needed. |
| III. Repository as Protocol | ✅ PASS | No repository changes. |
| IV. Pydantic domain models + mypy strict | ✅ PASS | No new domain models. The new inline class uses standard Django types. |
| V. Custom exception hierarchy | ✅ PASS | No error-path logic in a read-only inline. |
| VI. DAG integrity | ✅ PASS | No writes; cycle detection not invoked. |
| VII. Spec-driven development | ✅ PASS | This plan follows the spec. |
| VIII. Quality gates | ✅ PASS | All gates must pass (ruff, mypy --strict, pytest ≥ 80% cov). |
| IX. Framework-agnostic HTTP handlers | ✅ PASS | Change is in Django contrib (explicitly framework-coupled adapter). |
| X. Named constants | ✅ PASS | No new domain literals. Django class attributes (`extra = 0`, etc.) are self-evident. |
| XI. Object-oriented by default | ✅ PASS | `_ReadOnlyInlineMixin` extracted to satisfy the near-identical-class rule (shared with `IncomingRelationInline`). |

No violations. Complexity Tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/042-admin-child-categories/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code (affected files only)

```text
taxomesh/contrib/django/
└── admin.py             ← add CategoryChildLinkInline class; add to CategoryModelAdmin.inlines

tests/contrib/django/
└── test_admin.py        ← add tests for CategoryChildLinkInline registration and read-only behaviour
```

No new files. No migrations.

**Structure Decision**: Single-project layout. All changes are in the existing Django admin adapter module.
