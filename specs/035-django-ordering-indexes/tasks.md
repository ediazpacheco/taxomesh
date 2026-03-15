# Tasks: Database Indexes for Django Ordering Performance

**Input**: Design documents from `/specs/035-django-ordering-indexes/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅

**TDD**: Tests are mandatory per project constitution. Schema introspection tests MUST
be written and confirmed to fail (Django skip counts as skip, not fail — write and run
to confirm they skip/fail before adding the model changes) before each implementation task.

**Organization**: Two user stories, both P1. US1 = entity name indexes; US2 = composite
link indexes. Both are additive to the same `models.py`. A single migration covers all four.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no conflicting dependencies)
- **[Story]**: User story label (US1–US2)

---

## Phase 1: Setup

**Purpose**: Confirm baseline before any changes.

- [X] T001 Confirm `taxomesh/contrib/django/migrations/0004_external_id_indexes.py` is the latest migration (the new migration will depend on it)

---

## Phase 2: User Story 1 — Category and Item Name Indexes (Priority: P1) 🎯 MVP

**Goal**: `CategoryModel` and `ItemModel` each gain a `name` index so that `list_categories()`
and `list_items()` (and their `by_external_id` variants) can satisfy `ORDER BY name` via an
index scan rather than a full table sort.

**Independent Test**: Run `tests/contrib/django/test_django_ordering_indexes.py` — schema
introspection tests for `taxomesh_category_name_idx` and `taxomesh_item_name_idx` must pass
after migration; existing spec-034 ordering tests must continue to pass unchanged.

### Tests for User Story 1

> **Write these tests FIRST — confirm they skip/fail before implementation**

- [X] T002 [US1] Write schema introspection tests for `taxomesh_category_name_idx` and `taxomesh_item_name_idx` in `tests/contrib/django/test_django_ordering_indexes.py`: use `connection.introspection.get_constraints(cursor, table_name)` to assert both index names are present after migration; mark with `pytestmark = pytest.mark.django_db` and `pytest.importorskip("django")`

### Implementation for User Story 1

- [X] T003 [P] [US1] Add `indexes = [models.Index(fields=["name"], name="taxomesh_category_name_idx")]` to `CategoryModel.Meta` in `taxomesh/contrib/django/models.py`
- [X] T004 [P] [US1] Add `indexes = [models.Index(fields=["name"], name="taxomesh_item_name_idx")]` to `ItemModel.Meta` in `taxomesh/contrib/django/models.py`

**Checkpoint**: Model changes in place — migration not yet generated; T002 tests still fail

---

## Phase 3: User Story 2 — Link Model Composite Indexes (Priority: P1)

**Goal**: `CategoryParentLinkModel` and `ItemParentLinkModel` each gain a composite index
that matches the `ORDER BY` clause used by the link-list methods, eliminating the full-table
sort for grouped link queries.

**Independent Test**: Run `tests/contrib/django/test_django_ordering_indexes.py` — schema
introspection tests for `taxomesh_catlink_parent_sort_idx` and `taxomesh_itemlink_cat_sort_idx`
must pass after migration.

### Tests for User Story 2

> **Write these tests FIRST — confirm they skip/fail before implementation**

- [X] T005 [US2] Add schema introspection tests for `taxomesh_catlink_parent_sort_idx` and `taxomesh_itemlink_cat_sort_idx` to `tests/contrib/django/test_django_ordering_indexes.py` (same file as T002, extend the existing test class or add new assertions)

### Implementation for User Story 2

- [X] T006 [P] [US2] Add `indexes = [models.Index(fields=["parent_category_id", "sort_index"], name="taxomesh_catlink_parent_sort_idx")]` to `CategoryParentLinkModel.Meta` in `taxomesh/contrib/django/models.py`
- [X] T007 [P] [US2] Add `indexes = [models.Index(fields=["category_id", "sort_index"], name="taxomesh_itemlink_cat_sort_idx")]` to `ItemParentLinkModel.Meta` in `taxomesh/contrib/django/models.py`

**Checkpoint**: All four `Meta.indexes` entries in place — ready to generate migration

---

## Phase 4: Migration

**Purpose**: Generate and commit the migration that applies all four indexes atomically.

- [X] T008 Write `taxomesh/contrib/django/migrations/0005_ordering_indexes.py` with `dependencies = [("taxomesh_contrib_django", "0004_external_id_indexes")]` and four `migrations.AddIndex` operations (one per index from T003, T004, T006, T007) — either write manually or run `uv run python manage.py makemigrations --name ordering_indexes` if a Django settings file is available

**Checkpoint**: Run `uv run pytest tests/contrib/django/test_django_ordering_indexes.py --no-cov` — all schema tests MUST pass (or skip if Django not installed, which is acceptable given project constraints)

---

## Phase 5: Polish & Quality Gates

- [X] T009 [P] Run `uv run ruff check .` and fix any linting issues in modified files
- [X] T010 [P] Run `uv run ruff format --check .` and fix any formatting issues
- [X] T011 [P] Run `uv run mypy --strict .` and confirm no new type errors introduced (pre-existing Django import errors are acceptable)
- [X] T012 Run `uv run pytest --cov=taxomesh --cov-fail-under=80` and confirm all tests pass with coverage ≥ 80%

---

## Dependencies & Execution Order

### Phase Dependencies

```
T001 (baseline check)
  └── T002 (write US1 tests) ──┐
  └── T003 (CategoryModel.Meta) ─┤
  └── T004 (ItemModel.Meta) ────┤
        └── T005 (write US2 tests) ──┐
        └── T006 (CategoryParentLinkModel.Meta) ─┤
        └── T007 (ItemParentLinkModel.Meta) ─────┤
              └── T008 (migration 0005)
                    └── T009, T010, T011, T012 (quality gates, parallel)
```

### Parallel Opportunities

- T003 and T004 (both edit `models.py` at different class locations — sequential to avoid conflicts)
- T006 and T007 (same file — sequential)
- T009, T010, T011 (quality gates — parallel after T008)

---

## Implementation Strategy

### MVP (US1 only)

1. T001 baseline check
2. T002 write tests
3. T003 + T004 model changes
4. T008 migration (covering US1 indexes only — add US2 indexes after)
5. Validate T002 tests pass

### Full Delivery (both stories, one migration)

1. T001 → T002 → T003 → T004 (US1 model changes)
2. T005 → T006 → T007 (US2 model changes)
3. T008 (single migration covering all four indexes)
4. T009 → T010 → T011 → T012 (quality gates)

Recommended: full delivery in one pass — all changes are in the same file, single migration
is simpler than two.
