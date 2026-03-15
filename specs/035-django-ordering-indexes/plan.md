# Implementation Plan: Database Indexes for Django Ordering Performance

**Branch**: `035-django-ordering-indexes` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/035-django-ordering-indexes/spec.md`

---

## Summary

Add four database indexes to the Django ORM models to optimise the `ORDER BY` queries
introduced in spec 034. Two single-column indexes (`name` on Category and Item) and two
composite indexes (`(parent_category_id, sort_index)` on CategoryParentLink,
`(category_id, sort_index)` on ItemParentLink) are added via `Meta.indexes` in the model
and applied through a single Django migration. No logic, API, or domain model changes.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (ORM + migrations)
**Storage**: Django ORM — SQLite (tests), PostgreSQL (production)
**Testing**: pytest, pytest-django, pytest-cov
**Target Platform**: Library (contrib Django adapter)
**Performance Goals**: Eliminate full-table-scan sort for `ORDER BY name` and `ORDER BY (parent_id, sort_index)`
**Constraints**: No logic changes; no API changes; no domain model changes; additive migration only
**Scale/Scope**: 4 index definitions across 4 models; 1 migration file

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ Pass | Changes are in the contrib Django adapter only; domain untouched |
| II — TaxomeshService is single facade | ✅ Pass | No service changes |
| III — Repository as Protocol | ✅ Pass | No repository interface changes |
| IV — Pydantic + mypy strict | ✅ Pass | Indexes are ORM metadata; no Python type annotations affected |
| V — Custom exceptions | ✅ Pass | No new error paths |
| VI — DAG integrity | ✅ Pass | No write operations touched |
| VII — Spec-driven development | ✅ Pass | This plan follows the spec |
| VIII — Quality gates | ✅ Pass | Migration must pass ruff, mypy, pytest ≥ 80% |
| IX — Framework-agnostic handlers | ✅ Pass | Not applicable |
| X — Named Constants | ✅ Pass | Index names defined as string constants in migration |
| XI — OO by default | ✅ Pass | Changes are within existing model classes |

No violations.

---

## Project Structure

### Documentation (this feature)

```text
specs/035-django-ordering-indexes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Files Changed

```text
taxomesh/contrib/django/
├── models.py                         # Add Meta.indexes to 4 models
└── migrations/
    └── 0005_ordering_indexes.py      # New migration — AddIndex × 4
```

No other files change.

---

## Phase 0: Research

No unknowns. All decisions are pre-determined by the spec and existing codebase conventions.
See [research.md](research.md) for the decision record.

---

## Phase 1: Design

### 1.1 Index Definitions

Indexes are declared in each model's `Meta.indexes` list using `django.db.models.Index`.
Names follow the pattern `taxomesh_<table>_<cols>_idx` (truncated if needed by Django).

**CategoryModel** — add to `Meta`:
```python
indexes = [
    models.Index(fields=["name"], name="taxomesh_category_name_idx"),
]
```

**ItemModel** — add to `Meta`:
```python
indexes = [
    models.Index(fields=["name"], name="taxomesh_item_name_idx"),
]
```

**CategoryParentLinkModel** — add to `Meta`:
```python
indexes = [
    models.Index(fields=["parent_category_id", "sort_index"], name="taxomesh_catlink_parent_sort_idx"),
]
```

**ItemParentLinkModel** — add to `Meta`:
```python
indexes = [
    models.Index(fields=["category_id", "sort_index"], name="taxomesh_itemlink_cat_sort_idx"),
]
```

### 1.2 Migration

A single migration `0005_ordering_indexes.py` is written (or generated via `makemigrations`)
containing four `migrations.AddIndex` operations in dependency order:

```python
operations = [
    migrations.AddIndex(model_name="categorymodel",     index=models.Index(...)),
    migrations.AddIndex(model_name="itemmodel",         index=models.Index(...)),
    migrations.AddIndex(model_name="categoryparentlinkmodel", index=models.Index(...)),
    migrations.AddIndex(model_name="itemparentlinkmodel",     index=models.Index(...)),
]
```

Dependency: `("taxomesh_contrib_django", "0004_external_id_indexes")`

### 1.3 Test Strategy

No new test file is required. The correctness of ordering is already covered by the
spec 034 ordering tests (`tests/contrib/django/test_django_repository_ordering.py`).
The migration is verified by confirming those tests pass after migration is applied.

The only new test needed is a migration smoke-test: verify that after running
`migrate`, all four index names are present in the database schema.

### 1.4 No Contracts / No External Interface

This feature adds no new public API, CLI command, or external interface. No `contracts/`
directory is needed.
