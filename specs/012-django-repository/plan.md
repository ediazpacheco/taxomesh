# Implementation Plan: Django Repository

**Branch**: `012-django-repository` | **Date**: 2026-02-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-django-repository/spec.md`

---

## Summary

Add a `DjangoRepository` storage adapter satisfying `TaxomeshRepositoryBase` via Django ORM.
The adapter lives at `taxomesh/adapters/repositories/django_repository.py`. Accompanying
Django infrastructure (ORM models, AppConfig, admin, initial migration) lives in
`taxomesh/contrib/django/`. Django is an optional dependency (`taxomesh[django]`). All Django
symbols are deferred-imported everywhere — `import taxomesh` and
`from taxomesh.contrib.django import get_taxomesh_service_with_django` both succeed without
Django installed. A new `taxomesh/domain/constants.py` module centralises all shared field
constraint values (replacing inline `max_length` literals across domain models and ORM models).
`TaxomeshService._build_repo_from_config()` gains a `"django"` branch. README gets a
"Storage backends" section.

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `django>=4.2` (optional extra); `pytest-django>=4.8` (dev only)
**Storage**: Django ORM — SQLite (tests), PostgreSQL/MySQL (production; deferred)
**Testing**: pytest-django + SQLite `:memory:` (`tests/django_settings.py`)
**Target Platform**: Any Django 4.2+ environment
**Project Type**: Library + optional Django integration
**Performance Goals**: No latency targets — correctness and protocol compliance are primary
**Constraints**: `mypy --strict` passes for all source except `taxomesh/contrib/django/`
(excluded via `pyproject.toml`); no `django-stubs`, no mypy Django plugin
**Scale/Scope**: 6 ORM tables; same domain objects as existing adapters

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ PASS | `DjangoRepository` → `adapters/repositories/`; Django app → `contrib/`; no domain imports in adapter |
| I — Composition-root exception | ✅ PASS | All Django imports deferred inside `__init__` and method bodies; applies to both `DjangoRepository` and `contrib/django/__init__.py` |
| I — Adapter defaults stay in adapters | ✅ PASS | `DJANGO_REPO_USING_DEFAULT = "default"` defined in `contrib/django/models.py`, imported by `service.py` |
| II — TaxomeshService facade | ✅ PASS | `DjangoRepository` always explicit — never auto-fallback; factory in `contrib/`, not core |
| III — Protocol structural typing | ✅ PASS | `DjangoRepository` satisfies `TaxomeshRepositoryBase` without inheritance |
| IV — Pydantic + mypy strict | ✅ PASS | `contrib/django/` excluded from mypy; adapter `django_repository.py` under full `--strict`; no `django-stubs` needed due to deferred imports |
| V — Exception hierarchy | ✅ PASS | `TaxomeshRepositoryError` for all DB/import errors; `TaxomeshConfigError` for bad config type |
| VII — Spec-driven development | ✅ PASS | Spec + two clarification sessions + this plan produced before implementation |
| VIII — Quality gates | ✅ PASS | TDD mandatory; ≥ 80% coverage enforced; `contrib/django/` mypy exclusion documented |
| X — Named constants | ✅ PASS | `domain/constants.py` centralises all `max_length` values; ORM constants in `models.py` as `Final` |
| XI — Object-oriented by default | ✅ PASS | `DjangoRepository` is a class; ORM models are classes; factory is a module-level function (pure, stateless — permitted by XI) |

**No constitution amendments required.**

---

## Architectural Decisions

### AD-001: Split Placement — Adapter vs. Contrib
`adapters/repositories/django_repository.py` = hexagonal adapter (protocol impl).
`contrib/django/` = Django app (ORM models, AppConfig, migrations, admin).
Rationale: Constitution Principle I. `contrib/` follows Django's own `django.contrib.*` naming.

### AD-002: Deferred Imports Everywhere
All `import django` / `from django.*` inside function/method bodies with `# noqa: PLC0415`.
Applies to: `DjangoRepository.__init__`, all methods, and `get_taxomesh_service_with_django()`.
Ensures both `import taxomesh` and `from taxomesh.contrib.django import ...` succeed without Django.

### AD-003: ExternalId Type Discriminator
`external_id CharField(max_length=MAX_EXTERNAL_ID_DB_LENGTH)` + `external_id_type CharField(max_length=MAX_EXTERNAL_ID_TYPE_LENGTH, choices=EXTERNAL_ID_TYPE_CHOICES)`.
Two helpers: `_serialize_external_id()` → `(str, type_code)` and `_deserialize_external_id()` → `ExternalId`.

### AD-004: Optional Dependency
`django>=4.2` in `[project.optional-dependencies] django`. No `django-stubs` — unnecessary
with deferred imports and `contrib/django/` mypy exclusion.

### AD-005: `taxomesh.toml` `type = "django"`
`_build_repo_from_config()` gains a `"django"` branch. Optional `using` key.
Error message updated to list `'yaml'`, `'json'`, `'django'`.

### AD-006: `domain/constants.py` — Single Source of Truth
New `taxomesh/domain/constants.py` with `Final` constants for all `max_length` values.
Existing `category.py`, `item.py`, `tag.py` updated to import from it.
`contrib/django/models.py` also imports from it. In scope for spec 012.

### AD-007: No Service Changes Needed for Sort
`TaxomeshService` already sorts `list_category_parent_links()` and `list_item_parent_links()`
by `sort_index` (verified in `service.py` lines 206–210, 320–323, 524–534).
FR-020 only requires repos to return records without an ordering guarantee — already true for
`JsonRepository` and `YAMLRepository`. No changes to `service.py` needed for sorting.

### AD-008: Cascade Delete Is the DjangoRepository Contract
`on_delete=CASCADE` on all link model FKs. `delete_category` / `delete_item` / `delete_tag`
silently remove associated link rows. This is intentional and differs from file-based repos.
Callers must not assume orphaned link records are preserved.

---

## Project Structure

### Documentation (this feature)

```text
specs/012-django-repository/
├── spec.md                        ← feature specification (updated with clarifications)
├── plan.md                        ← this file
├── research.md                    ← Phase 0 research findings
├── data-model.md                  ← ORM model definitions + constants
├── quickstart.md                  ← developer quickstart
├── contracts/
│   └── orm-schema.md              ← database schema contract
├── checklists/
│   └── requirements.md            ← FR/SC tracking checklist
└── tasks.md                       ← task list (via /speckit.tasks)
```

### Source Code

```text
taxomesh/
├── domain/
│   ├── constants.py               ← NEW: MAX_NAME_LENGTH, MAX_TAG_NAME_LENGTH,
│   │                                      MAX_DESCRIPTION_LENGTH, MAX_EXTERNAL_ID_STR_LENGTH,
│   │                                      MAX_EXTERNAL_ID_DB_LENGTH, MAX_EXTERNAL_ID_TYPE_LENGTH
│   └── models/
│       ├── category.py            ← MODIFY: import constants, replace inline max_length
│       ├── item.py                ← MODIFY: ExternalId uses MAX_EXTERNAL_ID_STR_LENGTH
│       └── tag.py                 ← MODIFY: import MAX_TAG_NAME_LENGTH
├── adapters/
│   └── repositories/
│       └── django_repository.py   ← NEW: DjangoRepository (18 protocol methods)
├── application/
│   └── service.py                 ← MODIFY: add "django" branch to _build_repo_from_config()
├── contrib/
│   ├── __init__.py                ← NEW: package marker
│   └── django/
│       ├── __init__.py            ← NEW: get_taxomesh_service_with_django() (deferred import)
│       ├── apps.py                ← NEW: TaxomeshContribDjangoConfig
│       ├── models.py              ← NEW: 6 ORM models + ORM constants (imports domain/constants.py)
│       ├── admin.py               ← NEW: 6 ModelAdmin registrations
│       └── migrations/
│           ├── __init__.py        ← NEW: empty
│           └── 0001_initial.py   ← NEW: generated via makemigrations

tests/
├── contrib/
│   ├── __init__.py                ← NEW: empty
│   └── django/
│       ├── __init__.py            ← NEW: empty
│       ├── test_django_repository.py  ← NEW: pytest-django integration tests
│       └── test_admin.py          ← NEW: admin registration smoke test
├── domain/
│   └── test_constants.py          ← NEW: tests for constants values + model field constraints
└── django_settings.py             ← NEW: minimal Django settings (SQLite :memory:)

pyproject.toml                     ← MODIFY: optional dep, pytest DJANGO_SETTINGS_MODULE, mypy exclude
README.md                          ← MODIFY: Storage backends section
```

---

## Phase 0: Research Findings

*(Full details in research.md — summary of decisions confirmed by spec + codebase inspection)*

| Decision | Outcome |
|----------|---------|
| Django version floor | 4.2 LTS — `JSONField` works on SQLite 3.38+ (Python 3.11 ships it) |
| Deferred import scope | Both `django_repository.py` AND `contrib/django/__init__.py` — no module-level Django |
| `sort_index` sorting in service | **Already implemented** — `service.py` lines 206–210, 320–323, 524–534. No code change needed |
| `django-stubs` / mypy plugin | Dropped — deferred imports mean no Django symbols visible to mypy at module level |
| `contrib/django/` mypy scope | Excluded via `pyproject.toml [tool.mypy] exclude` glob |
| `get_taxomesh_service_with_django()` location | `taxomesh/contrib/django/__init__.py`; deferred import inside function body |
| `domain/constants.py` scope | In scope for 012; update `category.py`, `item.py`, `tag.py` in same PR |
| Test database | SQLite `:memory:` only; PostgreSQL deferred |
| Cascade on delete | `on_delete=CASCADE` — explicit DjangoRepository contract |
| `ExternalId` type discriminator constants | `EXTERNAL_ID_TYPE_UUID/INT/STR` = `"uuid"` / `"int"` / `"str"` |

---

## Phase 1: Domain Constants (Pre-requisite for all ORM work)

### Constants to extract into `taxomesh/domain/constants.py`

Discovered by reading domain model files:

| Constant | Value | Current location | Used by |
|----------|-------|-----------------|---------|
| `MAX_CATEGORY_NAME_LENGTH` | `256` | `category.py` inline | `category.py`, `contrib/django/models.py` |
| `MAX_TAG_NAME_LENGTH` | `25` | `tag.py` inline | `tag.py`, `contrib/django/models.py` |
| `MAX_DESCRIPTION_LENGTH` | `100_000` | `category.py` inline | `category.py`, `contrib/django/models.py` |
| `MAX_EXTERNAL_ID_STR_LENGTH` | `256` | `types.py` inline | `types.py`, `contrib/django/models.py` |
| `MAX_EXTERNAL_ID_DB_LENGTH` | `512` | plan only (new) | `contrib/django/models.py` only |
| `MAX_EXTERNAL_ID_TYPE_LENGTH` | `8` | plan only (new) | `contrib/django/models.py` only |

**Note**: `types.py` also has `ExternalId = UUID | Annotated[str, Field(max_length=256)]` — the `256` here becomes `MAX_EXTERNAL_ID_STR_LENGTH`.

---

## Phase 2: ORM Data Model

*(Full field definitions in data-model.md — key points)*

- **6 models**: `CategoryModel`, `ItemModel`, `TagModel`, `CategoryParentLinkModel`, `ItemParentLinkModel`, `ItemTagLinkModel`
- All `Meta.app_label = APP_LABEL` (`"taxomesh_contrib_django"`)
- All `Meta.db_table = <TABLE_CONSTANT>`
- Link models: `unique_together` enforces upsert contract; `on_delete=CASCADE` on all FKs
- ORM constants (`APP_LABEL`, `CATEGORY_TABLE`, etc., `DJANGO_REPO_USING_DEFAULT`, `EXTERNAL_ID_TYPE_*`) defined as `Final` in `models.py`
- `max_length` values imported from `taxomesh.domain.constants`

---

## Complexity Tracking

No constitution violations. The `# noqa: PLC0415` on deferred imports is the approved pattern
(mirrors `service.py` lines 82, 109–110). `mypy --strict` exclusion of `contrib/django/` is
a documented decision (FR-017), not a quality gate bypass.
