# Implementation Plan: External-ID Database Indexes & Lookup Promotion

**Branch**: `032-external-id-index` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/032-external-id-index/spec.md`

## Summary

Add `db_index=True` to `ItemModel.external_id` and `CategoryModel.external_id` in the Django
contrib models, and generate a migration (`0004`) that applies those indexes to the database.
`DjangoRepository.list_items_by_external_id` and `list_categories_by_external_id` already use
filtered ORM queries — no query logic changes are needed. Add tests covering all three
cardinality cases (empty, single, duplicate) for both Django lookup methods, plus model-field
and migration-state assertions. Update the README with explicit guidance to use the dedicated
lookup methods for `external_id` resolution.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Django ≥ 4.2 (ORM + migrations)
**Storage**: Django ORM — `taxomesh_item.external_id` and `taxomesh_category.external_id` gain
DB indexes; no data changes required
**Testing**: pytest + pytest-django
**Target Platform**: Any Django-compatible database (SQLite in tests, PostgreSQL/MySQL in prod)
**Project Type**: Library contrib module (Django ORM adapter + migration)
**Performance Goals**: `filter(external_id=...)` uses a DB index instead of full table scan
**Constraints**: Migration must be additive; no uniqueness constraint; no data rewrite; mypy
strict must pass; ruff must pass
**Scale/Scope**: Affects `taxomesh_item` and `taxomesh_category` tables

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I — Hexagonal architecture | Changes are in `contrib/django/models.py` and `adapters/repositories/django_repository.py` (adapter layer). No domain or application layer changes. | ✅ |
| II — TaxomeshService is single facade | `TaxomeshService.list_categories()` already delegates to `list_categories_by_external_id` when `external_id` is passed. No service changes needed. | ✅ |
| III — Repository as Protocol | Both lookup methods are already declared in `TaxomeshRepositoryBase`. No protocol changes needed. | ✅ |
| IV — Pydantic + mypy strict | No new model fields; no type signature changes. Existing strict typing unchanged. | ✅ |
| V — Exception hierarchy | No new exceptions needed. Existing `TaxomeshRepositoryError` propagation in the lookup methods is unchanged. | ✅ |
| VI — DAG cycle detection | Not applicable — read-only lookup; no graph mutation. | ✅ |
| VII — Spec-driven development | Spec exists at `specs/032-external-id-index/spec.md`. | ✅ |
| VIII — Quality gates | ruff + mypy strict + pytest ≥ 80% coverage required before merge. | ✅ |
| IX — Framework-agnostic API handlers | Not applicable — this is a Django ORM adapter change, not part of `taxomesh.contrib.api`. | ✅ |
| X — Named constants | No new magic literals introduced. `db_index=True` is a Django field kwarg, not a domain constant. | ✅ |
| XI — OO by default | No new classes or module-level functions needed. All changes are field attribute + migration. | ✅ |

No constitution violations. No Complexity Tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/032-external-id-index/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── repository-api.md  ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (files touched)

```text
taxomesh/
└── contrib/
    └── django/
        ├── models.py           # Add db_index=True to CategoryModel.external_id + ItemModel.external_id
        └── migrations/
            └── 0004_external_id_indexes.py   # New additive migration

README.md                       # Add external_id lookup guidance section

tests/
└── contrib/
    └── django/
        └── test_django_repository.py   # Add TestExternalIdLookup test class
```

No new directories. No new Python runtime dependencies. No non-Django adapter changes.

**Structure Decision**: Single-project layout. All changes are in the `contrib/django` adapter,
an additive migration, and the existing Django repository test file.

---

## Implementation Phases

### Phase A — Model field update (TDD first)

**A1 — Tests for model field and migration state** *(write and confirm FAILING before A2)*

In `tests/contrib/django/test_django_repository.py`, add class `TestExternalIdIndex`:

- `test_item_external_id_field_has_db_index` — inspect `ItemModel._meta.get_field("external_id").db_index`; assert it is `True`.
- `test_category_external_id_field_has_db_index` — inspect `CategoryModel._meta.get_field("external_id").db_index`; assert it is `True`.

These tests fail before A2 because `db_index` defaults to `False`.

**A2 — Add `db_index=True` to both model fields** *(after A1 tests are FAILING)*

In `taxomesh/contrib/django/models.py`:

1. On `CategoryModel.external_id`: add `db_index=True` to the `CharField(...)` kwargs.
2. On `ItemModel.external_id`: add `db_index=True` to the `CharField(...)` kwargs.

After this change A1 tests pass.

**A3 — Generate migration `0004_external_id_indexes`** *(after A2)*

Run `python manage.py makemigrations` (or hand-write) in `taxomesh/contrib/django/migrations/`
to produce `0004_external_id_indexes.py`. The migration must:

- Depend on `("taxomesh_contrib_django", "0003_item_relation_link")`.
- Use `migrations.AlterField` for both `CategoryModel.external_id` and `ItemModel.external_id`
  to add the `db_index=True` kwarg.
- Contain no data migration operations.

---

### Phase B — Repository lookup tests

**B1 — Tests for `DjangoRepository` lookup methods** *(TDD — write before verifying behaviour)*

In `tests/contrib/django/test_django_repository.py`, add to `TestExternalIdIndex` (or a
sibling class `TestExternalIdLookup`):

Items:

- `test_list_items_by_external_id_no_match` — create zero items with the target `external_id`;
  call `list_items_by_external_id("missing")`; assert result is `[]`.
- `test_list_items_by_external_id_single_match` — create one item with `external_id="unique-1"`;
  call `list_items_by_external_id("unique-1")`; assert `len(result) == 1` and
  `result[0].external_id == "unique-1"`.
- `test_list_items_by_external_id_duplicate_match` — create two items with
  `external_id="dup-1"`; call `list_items_by_external_id("dup-1")`; assert `len(result) == 2`.
- `test_list_items_by_external_id_blank` — create one item with `external_id=""`; call
  `list_items_by_external_id("")`; assert result contains that item (blank is a valid lookup).

Categories:

- `test_list_categories_by_external_id_no_match` — analogous to item test.
- `test_list_categories_by_external_id_single_match` — analogous to item test.
- `test_list_categories_by_external_id_duplicate_match` — analogous to item test.
- `test_list_categories_by_external_id_blank` — analogous to item test.

These tests verify the correctness of the existing Django repository implementation. They do
not test query count — they assert result cardinality and field values only.

---

### Phase C — Documentation

**C1 — Update README.md**

Add a new subsection under the existing integration/repository section (or append to the
`external_id` introduction near line 97). Content must cover:

- Use `service.list_items_by_external_id(external_id)` /
  `service.list_categories_by_external_id(external_id)` for resolving items and categories
  by external ID.
- Do **not** use `list_items()` / `list_categories()` and filter in Python — this performs
  a full-table read.
- `external_id` is indexed in the Django backend but is **not** unique; 0, 1, or many matches
  are all valid outcomes.
- The return value is always a `list[Item]` / `list[Category]`; use `len(result)` to detect
  the orphan (`len == 0`) and duplicate (`len > 1`) states.

---

### Phase D — Quality Gates

```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

All four gates must be green before proposing a commit.
