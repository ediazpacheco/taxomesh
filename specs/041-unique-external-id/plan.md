# Implementation Plan: Unique External ID (1:1 Constraint)

**Branch**: `041-unique-external-id` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/041-unique-external-id/spec.md`

---

## Summary

Replace the duplicate-tolerant `external_id` design (list-return lookups, `""` sentinel) with a
true 1:1 unique identifier. `external_id` becomes `str | None` across all layers. Lookups return
`T | None`. Writes enforce uniqueness via in-process checks (JSON/YAML) and a DB constraint
(Django). A new migration converts existing `""` → `NULL` and adds the unique constraint.
A new `TaxomeshExternalIdConflictError` is added to the exception hierarchy.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), Django ≥ 4.2 (ORM + admin), Typer ≥ 0.12 (CLI), pyyaml ≥ 6.0
**Storage**: JSON file (`JsonRepository`), YAML file (`YAMLRepository`), Django ORM (`DjangoRepository`)
**Testing**: pytest, pytest-django
**Target Platform**: Library — Python 3.11–3.13
**Project Type**: Library
**Performance Goals**: N/A — O(n) in-process scan for file-based repos is acceptable
**Constraints**: `mypy --strict`; line length 119; no partial indexes required
**Scale/Scope**: All three repository backends; service layer; CLI; Django admin; public exception API

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal Architecture | ✅ PASS | `TaxomeshExternalIdConflictError` raised in adapters; no domain layer import of adapters |
| II. Single Public Facade | ✅ PASS | New service methods replace old; `TaxomeshService` remains the only entry point |
| III. Protocol — Structural Typing | ✅ PASS | New protocol methods `get_item_by_external_id` / `get_category_by_external_id` follow existing pattern |
| IV. Pydantic + mypy Strict | ✅ PASS | `external_id: str \| None` uses `X \| None` syntax; `Annotated[str \| None, Field(max_length=256)]` preserves string-length constraint when non-None |
| IV. String length rule | ✅ PASS | `Annotated[str \| None, Field(max_length=256)]` — Pydantic v2 applies `max_length` only when value is a string; `None` is exempt |
| V. Exception Hierarchy | ✅ PASS | `TaxomeshExternalIdConflictError(TaxomeshValidationError)` — consistent with `TaxomeshDuplicateSlugError` |
| VII. Spec-Driven | ✅ PASS | This plan is the spec |
| VIII. Quality Gates | ✅ PASS | All gates required before PR |
| X. Named Constants | ✅ PASS | `DEFAULT_*_EXTERNAL_ID` constants updated; no magic literals |
| XI. Object-Oriented | ✅ PASS | No new module-level mutable state introduced |

**No violations. Proceed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/041-unique-external-id/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── contracts/
│   ├── service-api.md
│   └── repository-protocol.md
└── tasks.md             ← /speckit.tasks output (not yet created)
```

### Source Code (files modified by this feature)

```text
taxomesh/
├── domain/
│   ├── constants.py                                  # DEFAULT_*_EXTERNAL_ID → None
│   └── models/
│       ├── item.py                                   # external_id: str | None
│       └── category.py                               # external_id: str | None
├── ports/
│   └── repository.py                                 # protocol methods replaced
├── exceptions.py                                     # TaxomeshExternalIdConflictError added
├── __init__.py                                       # new exception exported
├── application/
│   └── service.py                                    # get_*_by_external_id methods replaced
├── adapters/
│   ├── repositories/
│   │   ├── json_repository.py                        # new get_*, uniqueness in save_*
│   │   ├── yaml_repository.py                        # new get_*, uniqueness in save_*
│   │   └── django_repository.py                      # new get_*, IntegrityError handling
│   └── cli/
│       └── main.py                                   # empty string → None; display None as —
└── contrib/
    └── django/
        ├── models.py                                 # unique=True, null=True
        ├── admin.py                                  # GraphEntry + _resolve_linked_url
        └── migrations/
            └── 0008_unique_external_id.py            # RunPython "" → NULL + AlterField

tests/
├── test_service_external_id.py                       # full replacement
├── contrib/
│   └── django/
│       ├── test_django_repository.py                 # update external_id tests
│       └── test_unique_external_id.py                # new: uniqueness + conflict tests
└── adapters/
    └── repositories/
        ├── test_json_repository_external_id.py       # new: uniqueness + conflict tests
        └── test_yaml_repository_external_id.py       # new: uniqueness + conflict tests

README.md                                             # public API section
CLAUDE.md                                             # Active Technologies entries
```

---

## Complexity Tracking

No constitution violations. Section omitted.

---

## Implementation Sequence

Tasks are ordered by dependency. TDD is mandatory: every implementation task is preceded by a failing-test task.

### Group A — Exception

| Step | Task | File(s) |
|---|---|---|
| A1 | **TEST** — Write failing tests for `TaxomeshExternalIdConflictError`: exists, correct hierarchy, message contains external_id value | `tests/test_exceptions.py` (new or existing) |
| A2 | **IMPL** — Add `TaxomeshExternalIdConflictError(TaxomeshValidationError)` to `exceptions.py`; export from `__init__.py` | `taxomesh/exceptions.py`, `taxomesh/__init__.py` |

### Group B — Domain Models

| Step | Task | File(s) |
|---|---|---|
| B1 | **TEST** — Write failing tests: `Item.external_id` defaults to `None`; `None` input stays `None`; UUID/int coerced to `str`; `Annotated[str \| None]` satisfies mypy | `tests/domain/test_item.py` |
| B2 | **IMPL** — Update `DEFAULT_ITEM_EXTERNAL_ID` and `DEFAULT_CATEGORY_EXTERNAL_ID` to `None`; update `Item.external_id` and `Category.external_id` fields and validators | `taxomesh/domain/constants.py`, `taxomesh/domain/models/item.py`, `taxomesh/domain/models/category.py` |
| B3 | **TEST** — Write failing tests: `Category.external_id` defaults to `None`; same coercion rules | `tests/domain/test_category.py` |

### Group C — Repository Protocol

| Step | Task | File(s) |
|---|---|---|
| C1 | **IMPL** — Replace `list_items_by_external_id` / `list_categories_by_external_id` with `get_item_by_external_id` / `get_category_by_external_id` in `TaxomeshRepositoryBase`; update `save_item` / `save_category` docstrings to document conflict behaviour | `taxomesh/ports/repository.py` |

*(Protocol is a structural `Protocol` — no tests for the protocol itself; implementations are tested below.)*

### Group D — JsonRepository

| Step | Task | File(s) |
|---|---|---|
| D1 | **TEST** — Write failing tests: `get_item_by_external_id` found/not-found; `save_item` raises `TaxomeshExternalIdConflictError` on duplicate non-None `external_id`; re-save same record does not raise; `None` round-trip | `tests/adapters/repositories/test_json_repository_external_id.py` |
| D2 | **IMPL** — Replace `list_*` with `get_*`; add uniqueness check in `save_item` / `save_category` | `taxomesh/adapters/repositories/json_repository.py` |

### Group E — YAMLRepository

| Step | Task | File(s) |
|---|---|---|
| E1 | **TEST** — Same tests as D1, parameterised or duplicated for YAML backend | `tests/adapters/repositories/test_yaml_repository_external_id.py` |
| E2 | **IMPL** — Same changes as D2 for YAML backend | `taxomesh/adapters/repositories/yaml_repository.py` |

### Group F — Service Layer

| Step | Task | File(s) |
|---|---|---|
| F1 | **TEST** — Replace all tests in `test_service_external_id.py`: `get_item_by_external_id` found → Item; not found → None; None input → None; UUID/int coercion; root Category excluded | `tests/test_service_external_id.py` |
| F2 | **IMPL** — Replace `get_items_by_external_id` / `get_categories_by_external_id` with `get_item_by_external_id` / `get_category_by_external_id`; add `None` short-circuit before repo call | `taxomesh/application/service.py` |

### Group G — DjangoRepository

| Step | Task | File(s) |
|---|---|---|
| G1 | **TEST** — Write failing tests: `get_item_by_external_id` found/not-found; `save_item` raises `TaxomeshExternalIdConflictError` on DB unique violation; re-save does not raise; multiple `NULL` external_ids do not conflict | `tests/contrib/django/test_unique_external_id.py` |
| G2 | **IMPL** — Replace `list_*` with `get_*`; update `save_item` / `save_category` to catch `IntegrityError` → `TaxomeshExternalIdConflictError` | `taxomesh/adapters/repositories/django_repository.py` |

### Group H — Django ORM + Migration

| Step | Task | File(s) |
|---|---|---|
| H1 | **TEST** — Write migration test: migration converts `""` → `NULL`; unique constraint enforced at DB level | `tests/contrib/django/test_migrations.py` (or existing) |
| H2 | **IMPL** — Update `CategoryModel.external_id` and `ItemModel.external_id` field definitions | `taxomesh/contrib/django/models.py` |
| H3 | **IMPL** — Write migration `0008_unique_external_id.py`: `RunPython` `""` → `NULL`, then `AlterField` for both models | `taxomesh/contrib/django/migrations/0008_unique_external_id.py` |

### Group I — CLI

| Step | Task | File(s) |
|---|---|---|
| I1 | **TEST** — Write failing tests: `_parse_external_id("")` → `None`; CLI item display renders `None` as `—` | `tests/adapters/cli/test_cli_external_id.py` (new or existing) |
| I2 | **IMPL** — Update `_parse_external_id` to return `str \| None`; update display rendering | `taxomesh/adapters/cli/main.py` |

### Group J — Django Admin

| Step | Task | File(s) |
|---|---|---|
| J1 | **TEST** — Write failing tests: `_resolve_linked_url(None)` returns `None`; admin list_display renders empty cell for `None` | `tests/contrib/django/test_admin_external_id.py` (new or existing) |
| J2 | **IMPL** — Update `GraphEntry.external_id: str \| None`; update `_resolve_linked_url` signature and `None` guard; update `list_display` rendering | `taxomesh/contrib/django/admin.py` |

### Group K — Documentation

| Step | Task | File(s) |
|---|---|---|
| K1 | **IMPL** — Update README public API section: new method signatures, `None` semantics, `TaxomeshExternalIdConflictError` | `README.md` |
| K2 | **IMPL** — Update `CLAUDE.md` Active Technologies entries for specs 013, 021 | `CLAUDE.md` |

### Group L — Quality Gates

| Step | Task |
|---|---|
| L1 | Run `ruff check .` — fix all lint errors |
| L2 | Run `ruff format --check .` — fix formatting |
| L3 | Run `mypy --strict .` — fix all type errors |
| L4 | Run `pytest --cov=taxomesh --cov-fail-under=80` — all tests pass, coverage ≥ 80% |

---

## Key Design Decisions (summary)

| Decision | Choice | Rationale |
|---|---|---|
| Exception parent | `TaxomeshValidationError` | Parallel to `TaxomeshDuplicateSlugError` |
| Django constraint | `unique=True` on field (not partial index) | Spec FR-013/014/016 explicit; SQLite + PostgreSQL support NULL-safe UNIQUE |
| Constants | Retain, change value to `None` | Principle X: single source of truth |
| Caching | Keep `@memoize` on new methods | Works with `Item \| None` return type; negative cache valid |
| DjangoRepository conflict | Catch `IntegrityError` specifically | Precise error mapping; avoids TOCTOU race of pre-check SELECT |
| JSON/YAML conflict | In-process O(n) scan excluding own PK | Only available mechanism for file backends |
