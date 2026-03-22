# Implementation Plan: Domain Audit Fields (created_at, updated_at, version)

**Branch**: `049-domain-audit-fields` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/049-domain-audit-fields/spec.md`

## Summary

Add three audit fields — `created_at` (UTC datetime), `updated_at` (UTC datetime), and
`version` (int, starts at 0) — to the `Category` and `Item` domain models.

**Responsibility split (decided during implementation):**

- **Service layer** stamps timestamps: `create_*` sets `created_at = updated_at = now(UTC)`;
  `update_*` advances `updated_at = now(UTC)`. Structural operations do not touch audit fields.
- **Repository layer** owns version atomicity: each adapter increments `version` inside its own
  `save_*` method (`entity.version += 1` for JSON/YAML; `F("version") + 1` for Django ORM).
  This guarantees the increment is atomic with the write, regardless of backend.

Domain models are passive containers. Structural operations (parent links, tags, relations)
do not affect audit fields. All repository backends persist and restore the fields transparently
via Pydantic serialization (JSON/YAML) or explicit ORM column mapping (Django).

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 4.2 (ORM adapter), pyyaml ≥ 6.0 (YAML adapter)
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM)
**Testing**: pytest, pytest-django (Django adapter tests)
**Target Platform**: Library — no platform dependency
**Project Type**: Python library
**Performance Goals**: No change from baseline — audit field writes piggyback on existing `save_category` / `save_item` calls
**Constraints**: Backward-compatible deserialization — legacy records without audit fields must load without error
**Scale/Scope**: Two domain models, one service class, three repository adapters, one Django migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Notes |
|-----------|-------|-------|
| I. Hexagonal Architecture | ✅ PASS | Timestamp stamping lives in service; version increment lives in each adapter's `save_*` method (atomic with the write). No adapter imports leak into domain |
| II. TaxomeshService is the single facade | ✅ PASS | `create_category`, `update_category`, `create_item`, `update_item` are the only service entry points that affect audit fields |
| III. Repository as Protocol | ✅ PASS | No new repository protocol methods needed; each adapter's existing `save_*` is responsible for version atomicity |
| IV. Pydantic + mypy strict | ✅ PASS | New fields declared as `datetime` (timezone-aware) with `Annotated` / `Field`; `version: int` needs no Annotated constraint (not a str); must add `Final` constants per Principle X |
| IV. String length rule | ✅ PASS | No new `str` fields; `datetime` and `int` are exempt from the max_length constraint |
| V. Exception hierarchy | ✅ PASS | No new error types required |
| VI. DAG integrity | ✅ PASS | Not affected |
| VIII. Quality gates | ✅ PASS | All gates must still pass after changes |
| X. Named constants | ✅ PASS | `AUDIT_EPOCH` and `DEFAULT_VERSION` constants required; no magic literals in model defaults or service logic |
| XI. Object-oriented by default | ✅ PASS | No module-level state introduced; audit stamping stays inside service methods |

**Constitution Check Result**: ✅ No violations. Proceed to Phase 1.

## Project Structure

### Documentation (this feature)

```text
specs/049-domain-audit-fields/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output
│   └── domain-api.md
└── tasks.md             ← Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (affected files)

```text
taxomesh/
├── domain/
│   ├── constants.py                          ← add AUDIT_EPOCH, DEFAULT_VERSION
│   └── models/
│       ├── category.py                       ← add created_at, updated_at, version fields
│       └── item.py                           ← add created_at, updated_at, version fields
├── application/
│   └── service.py                            ← stamp audit fields in create_* and update_*
├── adapters/
│   └── repositories/
│       └── django_repository.py              ← update save_category, _row_to_category,
│                                                save_item, _row_to_item
└── contrib/
    └── django/
        ├── models.py                         ← add 3 columns to CategoryModel and ItemModel
        └── migrations/
            └── 0009_audit_fields.py          ← new migration

tests/
├── test_audit_fields_domain.py               ← new: unit tests for model defaults
├── test_audit_fields_service.py              ← new: service-level audit field tests
└── contrib/django/
    └── test_audit_fields_django.py           ← new: Django adapter round-trip tests
```

**Structure Decision**: Single-project layout. All changes confined to existing
`taxomesh/` tree. No new top-level packages. Three new test files, one new migration.

## Complexity Tracking

> No constitution violations — section not applicable.
