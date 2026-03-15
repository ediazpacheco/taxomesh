# Implementation Plan: Fuzzy Search APIs

**Branch**: `033-fuzzy-search` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/033-fuzzy-search/spec.md`

## Summary

Add `search_items()` and `search_categories()` as public methods on `TaxomeshService`. Both
methods load candidates via existing service/repository calls, normalize query and field values
with a new `SearchEngine` class, compute a composite score using exact/prefix/substring boosts
plus RapidFuzz similarity, and return results sorted by descending score. No repository interface
changes are required. `rapidfuzz>=3.0` is added as a runtime dependency.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models), `rapidfuzz>=3.0` (new — fuzzy scoring), `stdlib unicodedata` + `re` (normalization)
**Storage**: JsonRepository / YAMLRepository / DjangoRepository — no changes; candidates loaded via existing service methods
**Testing**: pytest + pytest-cov; `InMemoryRepository` fixture from `tests/service/conftest.py`
**Target Platform**: Python library (all platforms)
**Project Type**: Library
**Performance Goals**: None specified for v1 catalog sizes (< a few thousand items)
**Constraints**: No repository interface changes; no new public `__init__.py` exports beyond `TaxomeshService`
**Scale/Scope**: Service-layer only; ~250 lines new code across two files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I — Hexagonal: dependency direction inward | `search.py` lives in `application/`; imports from `domain/` only. No adapter imports. | ✅ Pass |
| II — TaxomeshService is the single facade | Both new methods are on `TaxomeshService`. `SearchEngine` is internal. | ✅ Pass |
| III — Repository as Protocol | No new repository methods added. Existing `list_items()`, `list_categories()` calls unchanged. | ✅ Pass |
| IV — Pydantic models + mypy strict | No new domain models. `search.py` must be fully typed; `SearchEngine.normalize` returns `str`; `score_candidate` returns `float \| None`. | ✅ Pass (by construction) |
| V — Custom exception hierarchy | `ValueError` for `limit <= 0`; `TaxomeshCategoryNotFoundError` for invalid filter IDs. No new exceptions needed. | ✅ Pass |
| VI — DAG integrity | Not applicable (no category graph writes). | ✅ N/A |
| VII — Spec-driven development | This spec exists. | ✅ Pass |
| VIII — Quality gates | ruff, mypy --strict, pytest --cov ≥ 80% must all pass. | ✅ Must verify |
| IX — Framework-agnostic HTTP | No HTTP layer involved. | ✅ N/A |
| X — Named constants | Score boost values and fuzzy threshold defined as `Final[int]` constants. | ✅ Pass (by design) |
| XI — OO by default | Scoring logic encapsulated in `SearchEngine` class. Module-level constants are stateless. | ✅ Pass |

**Composition-root exception**: `rapidfuzz` is a required runtime dependency imported at module level in `search.py`. No lazy import needed.

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/033-fuzzy-search/
├── plan.md              # This file
├── research.md          # Phase 0 output ✅
├── data-model.md        # Phase 1 output ✅
├── quickstart.md        # Phase 1 output ✅
├── contracts/
│   └── service-api.md   # Phase 1 output ✅
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code Changes

```text
taxomesh/
├── application/
│   ├── search.py         # NEW — SearchEngine class, scoring constants, DEFAULT_SEARCH_LIMIT
│   └── service.py        # MODIFIED — search_items(), search_categories(),
│                         #             _collect_descendant_ids(), _load_item_candidates(),
│                         #             _score_and_rank()
└── (no other source changes)

tests/
└── service/
    └── test_service_search.py  # NEW — ≥ 25 test functions

pyproject.toml            # MODIFIED — add rapidfuzz>=3.0 to dependencies
```

**Structure Decision**: Single-project layout; no new packages. All new code lives in the existing
`taxomesh/application/` layer. Tests mirror the existing `tests/service/` structure.

## Phase 0: Research

**Status**: Complete. See [research.md](research.md).

All unknowns resolved:
- Normalization: stdlib `unicodedata` + `re`
- Fuzzy scoring: `rapidfuzz` (ratio, partial_ratio, token_set_ratio)
- Score formula: tiered boost + fuzzy additive; threshold = 70 for pure-fuzzy candidates
- Search module location: `taxomesh/application/search.py`
- Candidate loading: existing service methods (`list_items`, `list_categories`, `_repo.list_categories`)
- `external_id` sentinel: `""` — skip matching when equal

## Phase 1: Design & Contracts

**Status**: Complete.

- [data-model.md](data-model.md) — `SearchEngine` class design, new service method signatures, `_collect_descendant_ids` helper
- [contracts/service-api.md](contracts/service-api.md) — full parameter/return/exception contracts for both public methods

## Implementation Tasks (for `/speckit.tasks`)

Ordered by dependency:

### T1 — Add `rapidfuzz` dependency
- Edit `pyproject.toml`: add `"rapidfuzz>=3.0"` to `[project] dependencies`
- Run `uv sync` (or `pip install -e .`) to verify
- **Gate**: `import rapidfuzz` works in the project environment

### T2 — Tests: normalization helper
- Create `tests/service/test_service_search.py`
- Write failing tests for `SearchEngine.normalize()`:
  - accent removal (Agustín → agustin)
  - apostrophe to space (D'Arienzo → d arienzo)
  - dash to space (gallo-ciego → gallo ciego)
  - whitespace collapse
  - lowercase
- **Gate**: all tests fail (red phase)

### T3 — Implement `SearchEngine.normalize`
- Create `taxomesh/application/search.py`
- Implement `SearchEngine` class with `normalize` staticmethod
- **Gate**: T2 tests pass

### T4 — Tests: `score_candidate` (exact, prefix, substring)
- Add test cases for scoring signals:
  - exact name → score ≥ BOOST_EXACT
  - prefix name → score ≥ BOOST_PREFIX_NAME
  - prefix slug → score ≥ BOOST_PREFIX_SLUG
  - word-prefix name → score ≥ BOOST_WORD_PREFIX
  - substring name → score ≥ BOOST_SUBSTRING_NAME
  - substring slug → score ≥ BOOST_SUBSTRING_SLUG
  - substring external_id → score ≥ BOOST_SUBSTRING_EXT
  - empty external_id → external_id boost not applied
  - no match → returns None
- **Gate**: tests fail

### T5 — Implement `SearchEngine.score_candidate` (non-fuzzy signals)
- Implement boost logic in `SearchEngine.score_candidate`
- `fuzzy=False` path: return boost or None
- **Gate**: T4 tests pass

### T6 — Tests: fuzzy scoring
- Add test cases for:
  - typo match: "piazola" scores against "piazzolla" (≥ FUZZY_THRESHOLD)
  - typo + `fuzzy=False` → returns None (no boost, no fuzzy)
  - below threshold: completely unrelated string → returns None
- **Gate**: tests fail

### T7 — Implement `SearchEngine.score_candidate` (fuzzy signals)
- Add RapidFuzz calls for `fuzzy=True` path
- Additive fuzzy score + threshold guard
- **Gate**: T6 tests pass

### T8 — Tests: `search_items()` (item-search cases)
- Add 14 item-search test functions covering:
  1. exact name match
  2. exact slug match
  3. prefix name match
  4. prefix slug match
  5. substring match
  6. typo-tolerant match ("piazola" finds "Piazzolla")
  7. accent-insensitive ("agustin" finds "Agustín")
  8. punctuation-insensitive ("d arienzo" finds "D'Arienzo")
  9. disabled items excluded when `enabled_only=True`
  10. disabled items included when `enabled_only=False`
  11. `category_id` filter works (direct members only)
  12. invalid `category_id` raises `TaxomeshCategoryNotFoundError`
  13. `limit` is respected
  14. empty query returns `[]`
- **Gate**: all fail

### T9 — Implement `TaxomeshService.search_items` (core, no recursive)
- Add `search_items()` to `service.py` (without `recursive=True` path)
- Uses `SearchEngine` for normalization and scoring
- **Gate**: T8 tests pass

### T10 — Tests: `search_items()` recursive filter
- Add tests for `recursive=True`:
  - items in category X and child category C both returned
  - `recursive=True` without `category_id` returns all items
- **Gate**: tests fail

### T11 — Implement `_collect_descendant_ids` + `recursive=True` path in `search_items`
- Add `_collect_descendant_ids(category_id)` private method to `TaxomeshService`
- Wire into `search_items` when `recursive=True`
- **Gate**: T10 tests pass

### T12 — Tests: `search_categories()` (category-search cases)
- Add 8 category-search test functions:
  1. exact name match
  2. exact slug match
  3. typo-tolerant match ("orkesta tipika" finds "Orquesta Típica")
  4. accent-insensitive
  5. `parent_id` filter works (direct children only)
  6. invalid `parent_id` raises `TaxomeshCategoryNotFoundError`
  7. `limit` respected
  8. empty query returns `[]`
- **Gate**: all fail

### T13 — Implement `TaxomeshService.search_categories`
- Add `search_categories()` to `service.py`
- Uses `self._repo.list_categories()` (filtered from root) for `parent_id=None`
- Uses `self.list_categories(parent_id=X)` for filtered case
- **Gate**: T12 tests pass

### T14 — Tests: ranking behavior (3 cases)
- exact match ranks above fuzzy match
- prefix ranks above substring
- likely intended typo ("piazola") ranks above weaker false positive
- **Gate**: tests fail

### T15 — Verify ranking (fix if needed)
- Run T14 tests; if failing, adjust score weights
- **Gate**: all ranking tests pass

### T16 — Quality gates
- `ruff check .`
- `ruff format --check .`
- `mypy --strict .`
- `pytest --cov=taxomesh --cov-fail-under=80`
- Fix any violations found

### T17 — Docstrings
- Add Google-style docstrings to:
  - `search.py` module
  - `SearchEngine` class
  - `SearchEngine.normalize`
  - `SearchEngine.score_candidate`
  - `TaxomeshService.search_items`
  - `TaxomeshService.search_categories`
  - `TaxomeshService._collect_descendant_ids`

## Key Design Decisions

### Composition-root note
`rapidfuzz` is imported at module level in `search.py`. It is a required runtime dependency,
so no lazy import is needed. The composition-root exception in Principle I does not apply here.

### Why `SearchEngine` is a class and not module-level functions
Constitution Principle XI: "Prefer class-based design over module-level functions." The
`SearchEngine` groups related behavior (normalize + score) under a single namespace. The
methods are stateless, but encapsulating them in a class makes future extension (e.g., adding
configurable thresholds) straightforward without breaking the interface.

### Why `_collect_descendant_ids` is on `TaxomeshService`, not `SearchEngine`
`SearchEngine` should not know about repositories or service state. Descendant traversal is a
graph operation over the category hierarchy, which is a service-layer concern. `SearchEngine`
only receives already-loaded candidates and scores them.

### `search_categories(parent_id=None)` loads from `_repo.list_categories()`
`TaxomeshService.list_categories(parent_id=None)` returns root-level categories (children of
the internal root), not all categories. Searching "all categories" must use
`self._repo.list_categories()` directly and exclude the root node manually.
