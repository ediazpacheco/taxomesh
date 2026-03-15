# Research: Database Indexes for Django Ordering Performance

**Feature**: `035-django-ordering-indexes`
**Date**: 2026-03-15

No unknowns were identified during planning. All decisions follow directly from the spec,
the existing codebase, and Django conventions. This document records the decisions for traceability.

---

## Decision 1: Index Definition Mechanism — `Meta.indexes` vs `db_index=True`

- **Decision**: Use `Meta.indexes` with explicit `django.db.models.Index` entries for all four indexes.
- **Rationale**: `db_index=True` only supports single-column indexes and does not allow
  naming. `Meta.indexes` supports both single-column and composite indexes, allows explicit
  naming (required for introspection tests and Django migration consistency), and is the
  Django-recommended approach for all non-unique indexes.
- **Alternatives considered**: `db_index=True` (rejected — no composite support, no naming);
  raw SQL in migration (rejected — bypasses ORM and breaks `makemigrations` state tracking).

---

## Decision 2: Index Naming Convention

- **Decision**: `taxomesh_<model_short>_<cols>_idx` pattern.
  - `taxomesh_category_name_idx`
  - `taxomesh_item_name_idx`
  - `taxomesh_catlink_parent_sort_idx`
  - `taxomesh_itemlink_cat_sort_idx`
- **Rationale**: Consistent with the existing `taxomesh_` prefix used for table names.
  Names are short enough to stay within PostgreSQL's 63-character identifier limit and
  descriptive enough to identify purpose at a glance.
- **Alternatives considered**: Auto-generated Django names (rejected — unpredictable,
  harder to reference in tests); full table name prefix (rejected — too verbose, risks
  hitting identifier length limits).

---

## Decision 3: ItemRelationLinkModel.sort_index — Excluded

- **Decision**: Do not add a `sort_index` index to `ItemRelationLinkModel`.
- **Rationale**: `list_item_relation_links()` always applies a WHERE clause on
  `source_item_id` or `target_item_id` before ordering. Both FK columns are already
  indexed by Django automatically. The filtered result set is bounded by the number of
  relations for a single item — in practice a small number (tens, not thousands).
  Adding a `sort_index` index would not be used by the query planner for these filtered
  queries and would incur unnecessary write overhead.
- **Alternatives considered**: Add index anyway as defensive measure (rejected — YAGNI;
  adds write overhead with no measurable read benefit for the access pattern in use).

---

## Decision 4: Migration Strategy — Manual vs `makemigrations`

- **Decision**: Write the migration manually (`0005_ordering_indexes.py`) using
  `migrations.AddIndex` operations. Alternatively, `makemigrations` can be run to
  auto-generate it from the model changes — the result is identical.
- **Rationale**: The migration content is fully deterministic (4 AddIndex operations,
  known dependency). Manual authoring avoids requiring a running Django environment during
  implementation. Auto-generation via `makemigrations` is equally valid and preferred if
  a Django environment is available.
- **Alternatives considered**: Raw `CREATE INDEX` SQL in a `RunSQL` operation (rejected —
  not tracked by Django migration state; breaks `--check` and `showmigrations`).

---

## Decision 5: No New Tests Required

- **Decision**: No new test file. Correctness of ordering is already verified by
  `tests/contrib/django/test_django_repository_ordering.py` (from spec 034). A migration
  smoke test (schema introspection) is the only addition.
- **Rationale**: The indexes are transparent to callers — they affect query performance,
  not query results. Existing ordering tests provide full regression coverage.
- **Alternatives considered**: Add performance benchmarks (rejected — out of scope for
  a library test suite; benchmark harness would be a separate concern).
