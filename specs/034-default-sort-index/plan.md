# Implementation Plan: Default sort_index Ordering for All Collection-Returning Methods

**Branch**: `034-default-sort-index` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/034-default-sort-index/spec.md`

---

## Summary

All collection-returning methods in the repository adapters (JSON, YAML, Django) and the
`TaxomeshRepositoryBase` Protocol must return results in a deterministic, stable order by
default. Sorting is applied at the **repository layer** so service-level methods that delegate
directly receive ordered results for free. No method signatures change. No domain model changes.

Sort keys (from research findings):
- Entities with `sort_index` (link models): sort ascending by `sort_index`, secondary by IDs.
- Entities without `sort_index` (`Category`, `Item`): sort ascending by `name`, secondary by ID.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2, Django ≥ 4.2 (optional adapter), pyyaml ≥ 6.0
**Storage**: JsonRepository (JSON file), YAMLRepository (YAML file), DjangoRepository (Django ORM)
**Testing**: pytest, pytest-cov
**Target Platform**: Library (used by Python 3.11–3.13 applications)
**Project Type**: Library
**Performance Goals**: No new performance requirements; ORM ordering delegated to DB engine
**Constraints**: No method signature changes; no schema migrations; no new dependencies
**Scale/Scope**: 7 repo methods × 3 adapters = 21 method changes; Protocol docstrings update

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ Pass | Sorting added inside adapter layer only; domain models untouched |
| II — TaxomeshService is single facade | ✅ Pass | Service API unchanged; no new public methods |
| III — Repository as Protocol | ✅ Pass | Protocol docstrings updated to document ordering contract |
| IV — Pydantic + mypy strict | ✅ Pass | No new fields; `sorted()` key lambdas are fully typed |
| V — Custom exceptions | ✅ Pass | No new error paths introduced |
| VI — DAG integrity | ✅ Pass | No write operations touched |
| VII — Spec-driven development | ✅ Pass | This plan follows the spec |
| VIII — Quality gates | ✅ Pass | All gates must pass; coverage ≥ 80% |
| IX — Framework-agnostic handlers | ✅ Pass | Not applicable to this feature |
| X — Named constants | ✅ Pass | No magic literals; sort keys are field references |
| XI — OO by default | ✅ Pass | Changes are within existing classes |

No violations. Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/034-default-sort-index/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Files Changed

```text
taxomesh/
├── ports/
│   └── repository.py                          # Update docstrings (7 methods)
└── adapters/
    └── repositories/
        ├── json_repository.py                 # Add sorted() to 7 methods
        ├── yaml_repository.py                 # Add sorted() to 7 methods
        └── django_repository.py               # Add .order_by() to 7 methods

tests/
├── service/
│   ├── test_json_repository_ordering.py       # New — JSON/YAML ordering tests
│   └── test_yaml_repository_ordering.py       # New — YAML ordering tests
└── contrib/
    └── django/
        └── test_django_repository_ordering.py # New — Django ordering tests (skipped if Django absent)
```

**Structure Decision**: Single project layout. All changes are within existing modules.
No new modules, packages, or directories required.

---

## Phase 0: Research

Complete. See [research.md](research.md).

Key findings:
1. `Category` and `Item` have **no** `sort_index` field — sort by `name` for unfiltered listing.
2. All link models (`CategoryParentLink`, `ItemParentLink`, `ItemRelationLink`) have `sort_index`.
3. Service layer already sorts correctly for parent/category-filtered paths — no service changes needed.
4. FR-005 spec assumption corrected: unfiltered `list_items()` sorts by `item.name`, not by `sort_index`.
5. 21 method bodies need changes (7 methods × 3 adapters); Protocol docstrings also updated.

---

## Phase 1: Design

### 1.1 Sort Key Definitions

Sort keys are expressed as inline key lambdas (JSON/YAML) or ORM column references (Django).
Principle X is satisfied because field names are referenced symbolically, not as magic literals.

**JSON/YAML repositories** — Python `sorted()` with `key=` tuples:

```python
# For Category listing
sorted(values, key=lambda c: (c.name, str(c.category_id)))

# For Item listing
sorted(values, key=lambda i: (i.name, str(i.item_id)))

# For CategoryParentLink listing  — group by parent first, then sort_index within group
sorted(links, key=lambda l: (str(l.parent_category_id), l.sort_index, str(l.category_id)))

# For ItemParentLink listing  — group by category first, then sort_index within group
sorted(links, key=lambda l: (str(l.category_id), l.sort_index, str(l.item_id)))

# For ItemRelationLink listing
sorted(links, key=lambda l: (l.sort_index, str(l.source_item_id), str(l.target_item_id)))
```

**DjangoRepository** — ORM `.order_by()` (all column names are lowercase snake_case in
the Django model, matching domain field names):

```python
.order_by("name", "category_id")                              # list_categories()
.order_by("name", "item_id")                                  # list_items()
.order_by("parent_category_id", "sort_index", "category_id") # list_category_parent_links()
.order_by("category_id", "sort_index", "item_id")             # list_item_parent_links()
.order_by("sort_index", "source_item_id", "target_item_id")   # list_item_relation_links()
.order_by("name", "item_id")                                  # list_items_by_external_id()
.order_by("name", "category_id")                              # list_categories_by_external_id()
```

### 1.2 Protocol Docstring Updates

Each affected method in `TaxomeshRepositoryBase` (`taxomesh/ports/repository.py`) gains
a `Returns:` clause that documents the ordering guarantee. Example:

```python
def list_categories(self) -> list[Category]:
    """Return all stored categories.

    Returns:
        List of all categories ordered ascending by name, then by
        category_id for stability. Empty list if the store is empty.
    """
    ...
```

### 1.3 Service Layer

No changes to sorting logic. The three service methods that delegate to repo
(`list_item_relations()`, `get_items_by_external_id()`, `get_categories_by_external_id()`)
automatically receive sorted output after the repo changes. Their docstrings may optionally
be updated to note the ordering guarantee.

### 1.4 Test Strategy

Each new test module follows the same structure:

1. **Setup**: Create records with `sort_index` or `name` values in *non-ascending* order.
2. **Assert**: Call the list method; verify result order matches ascending sort key.
3. **Tie-breaker**: Create records with equal primary sort key; verify secondary key governs.
4. **Empty**: Call on empty store; verify empty list returned without error.
5. **Filtered variants**: For methods with filters (e.g. `list_item_relation_links()` with
   `relation_type`/`direction`), verify ordering is preserved after filtering.

Tests use the in-memory repo fixture pattern already established in the test suite.
Django repo ordering tests use `pytest-django` and the existing Django test setup.

---

## Detailed Change Specification

### A. `JsonRepository` and `YAMLRepository` (identical changes in both files)

| Method | Current return | New return |
|--------|----------------|------------|
| `list_categories()` | `list(self._categories.values())` | `sorted(..., key=lambda c: (c.name, str(c.category_id)))` |
| `list_items()` | `list(self._items.values())` | `sorted(..., key=lambda i: (i.name, str(i.item_id)))` |
| `list_category_parent_links()` | `list(self._category_parent_links)` | `sorted(..., key=lambda l: (str(l.parent_category_id), l.sort_index, str(l.category_id)))` |
| `list_item_parent_links()` | `list(self._item_parent_links)` | `sorted(..., key=lambda l: (str(l.category_id), l.sort_index, str(l.item_id)))` |
| `list_items_by_external_id()` | list comprehension (unsorted) | list comprehension wrapped in `sorted(..., key=lambda i: (i.name, str(i.item_id)))` |
| `list_categories_by_external_id()` | list comprehension (unsorted) | list comprehension wrapped in `sorted(..., key=lambda c: (c.name, str(c.category_id)))` |
| `list_item_relation_links()` | filtered list (unsorted) | filtered list wrapped in `sorted(..., key=lambda l: (l.sort_index, str(l.source_item_id), str(l.target_item_id)))` |

### B. `DjangoRepository`

| Method | Change |
|--------|--------|
| `list_categories()` | Add `.order_by("name", "category_id")` to queryset |
| `list_items()` | Add `.order_by("name", "item_id")` to queryset |
| `list_category_parent_links()` | Add `.order_by("parent_category_id", "sort_index", "category_id")` |
| `list_item_parent_links()` | Add `.order_by("category_id", "sort_index", "item_id")` |
| `list_items_by_external_id()` | Add `.order_by("name", "item_id")` to filter queryset |
| `list_categories_by_external_id()` | Add `.order_by("name", "category_id")` to filter queryset |
| `list_item_relation_links()` | Add `.order_by("sort_index", "source_item_id", "target_item_id")` to queryset |

### C. `TaxomeshRepositoryBase` Protocol

Update `Returns:` docstring section of all 7 affected methods to state the ordering guarantee.

---

## Contracts

No public API contracts change (no new methods, no signature changes). The ordering
guarantee is a behaviour contract documented in Protocol docstrings only.

---

## Open Questions / Risks

| Item | Status |
|------|--------|
| Django model column names for `sort_index` in ORM | Must verify column names in `django_repository.py` ORM models match exactly before writing `.order_by()` clauses |
| `list_categories(parent_id=None)` at service layer | Already routes to root_id and sorts by link.sort_index — unchanged, correct |
| `@memoize` on service methods | Caching is orthogonal to sorting; no impact |
