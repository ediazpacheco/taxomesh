# Implementation Plan: Service Slug Lookup Methods

**Branch**: `020-slug-lookup` | **Date**: 2026-03-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/020-slug-lookup/spec.md`

## Summary

Add two read-only methods to `TaxomeshService`:
- `get_category_by_slug(slug: str) -> Category` — wraps the repository's nullable
  `get_category_by_slug`, raises `TaxomeshCategoryNotFoundError` if not found.
- `get_item_by_slug(slug: str) -> Item` — wraps the repository's nullable
  `get_item_by_slug`, raises `TaxomeshItemNotFoundError` if not found.

Both methods are decorated with `@memoize(DEFAULT_CACHE_TTL)` to match the caching
behaviour of `get_category` and `get_item`. No repository changes are required.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), stdlib only for this feature
**Storage**: All adapters already implement slug lookups; no storage change needed
**Testing**: pytest — new test classes added to `tests/service/test_service_slug.py`
**Target Platform**: Library (all platforms supported by Python 3.11+)
**Project Type**: library
**Performance Goals**: Consistent with existing `get_category` / `get_item` caching (TTL-based)
**Constraints**: mypy --strict must pass; ruff must pass; coverage ≥ 80%
**Scale/Scope**: Two new method additions to a single class; one test file extended

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | Service delegates to port; no cross-layer imports |
| II. TaxomeshService is the Single Public Facade | ✅ PASS | Methods added to TaxomeshService |
| III. Repository as Protocol | ✅ PASS | Existing protocol methods reused; no new protocol changes |
| IV. Pydantic Domain Models + mypy Strict | ✅ PASS | Return types are existing Pydantic models; `@memoize` is already typed |
| V. Custom Exception Hierarchy | ✅ PASS | Raises `TaxomeshCategoryNotFoundError` / `TaxomeshItemNotFoundError` |
| VI. DAG Integrity | ✅ N/A | Read-only; no graph mutations |
| VII. Spec-Driven Development | ✅ PASS | Spec exists at specs/020-slug-lookup/spec.md |
| VIII. Quality Gates | ✅ PASS | No new dependencies; existing gates apply |
| IX. Pluggable REST Views | ✅ N/A | No REST surface changes |
| X. Named Constants | ✅ PASS | Uses existing `DEFAULT_CACHE_TTL`; no new literals |
| XI. Object-Oriented by Default | ✅ PASS | Methods added to existing class |

**No violations. No Complexity Tracking entry needed.**

## Project Structure

### Documentation (this feature)

```text
specs/020-slug-lookup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── service-api.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (files touched)

```text
taxomesh/
└── application/
    └── service.py           # Add get_category_by_slug + get_item_by_slug

tests/
└── service/
    └── test_service_slug.py # Add TestGetCategoryBySlug + TestGetItemBySlug
```

**Structure Decision**: Single-project layout. Only `service.py` is modified.
`test_service_slug.py` is extended (not replaced). No new files in the source tree.

## Implementation Steps

### Step 1 — Write failing tests (TDD)

Add two test classes to `tests/service/test_service_slug.py`:

**`TestGetCategoryBySlug`**:
- `test_get_category_by_slug_returns_category` — create category with slug, call method, assert match
- `test_get_category_by_slug_not_found_raises` — call with non-existent slug, assert `TaxomeshCategoryNotFoundError`
- `test_get_category_by_slug_empty_slug_raises` — call with `""`, assert `TaxomeshCategoryNotFoundError`

**`TestGetItemBySlug`**:
- `test_get_item_by_slug_returns_item` — create item with slug, call method, assert match
- `test_get_item_by_slug_not_found_raises` — call with non-existent slug, assert `TaxomeshItemNotFoundError`
- `test_get_item_by_slug_empty_slug_raises` — call with `""`, assert `TaxomeshItemNotFoundError`

Run `pytest tests/service/test_service_slug.py` → all new tests FAIL (methods not yet implemented).

### Step 2 — Implement service methods

In `taxomesh/application/service.py`, add inside the Category section (after `update_category`):

```python
@memoize(DEFAULT_CACHE_TTL)
def get_category_by_slug(self, slug: str) -> Category:
    result = self._repo.get_category_by_slug(slug)
    if result is None or result.category_id == self._root_id:
        raise TaxomeshCategoryNotFoundError(f"Category not found for slug: {slug!r}")
    return result
```

And inside the Item section (after `update_item`):

```python
@memoize(DEFAULT_CACHE_TTL)
def get_item_by_slug(self, slug: str) -> Item:
    result = self._repo.get_item_by_slug(slug)
    if result is None:
        raise TaxomeshItemNotFoundError(f"Item not found for slug: {slug!r}")
    return result
```

### Step 3 — Run quality gates

```bash
pytest tests/service/test_service_slug.py          # all tests pass
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

All gates must pass before the feature is considered done.

## Phase 0 Artifacts

- [research.md](research.md) — all decisions resolved; no NEEDS CLARIFICATION items

## Phase 1 Artifacts

- [data-model.md](data-model.md) — no new entities; existing Category + Item documented
- [contracts/service-api.md](contracts/service-api.md) — method signatures and error contracts
- quickstart.md — see below

## Quickstart

```python
from taxomesh import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError

service = TaxomeshService()

# Create entities with slugs
cat = service.create_category(name="Electronics", slug="electronics")
item = service.create_item(name="Widget", external_id="w-001", slug="widget")

# Look up by slug
category = service.get_category_by_slug("electronics")  # returns Category
item = service.get_item_by_slug("widget")                # returns Item

# Not-found raises typed exception
try:
    service.get_category_by_slug("missing")
except TaxomeshCategoryNotFoundError:
    print("Category not found")

try:
    service.get_item_by_slug("missing")
except TaxomeshItemNotFoundError:
    print("Item not found")
```
