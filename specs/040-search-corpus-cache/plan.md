# Implementation Plan: Search Corpus Cache

**Branch**: `040-search-corpus-cache` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/040-search-corpus-cache/spec.md`

## Summary

Eliminate two hot-path costs in `search_items()` and `search_categories()`:

1. **Candidate reload**: `_load_item_candidates(category_id=None)` currently calls `self._repository.list_items()` directly, bypassing the memoized `self.list_items()`. Fix: route unfiltered loads through the memoized service method.

2. **Per-request re-normalization**: `_score_and_rank()` creates `SearchCandidate` wrappers (normalizing every field) on every search call. Fix: introduce private `_item_corpus` and `_category_corpus` instance attributes on `TaxomeshService` that cache pre-normalized candidates. Build once per cache lifetime; invalidate on writes that affect entity fields; reuse across repeated searches.

No repository protocol changes. No public API changes. All changes are internal to `taxomesh/application/service.py`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Pydantic v2 (domain models), `rapidfuzz>=3.0` (fuzzy scoring — existing), stdlib `heapq` (existing)
**Storage**: N/A — no new storage; optimization is purely in-process
**Testing**: pytest, `unittest.mock.patch`
**Target Platform**: Cross-platform Python library (Linux, macOS, Windows)
**Project Type**: Library (PyPI)
**Performance Goals**: Eliminate repeated repository I/O and field normalization on warm-cache repeated searches
**Constraints**: No wall-clock test assertions; no breaking public API changes; no repository protocol changes
**Scale/Scope**: Optimized for catalogs of 1k–50k items/categories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Assessment | Notes |
|-----------|-----------|-------|
| I — Hexagonal Architecture | ✅ PASS | All cache logic lives in `application/service.py`. No adapter imports. Repository protocol unchanged. |
| II — TaxomeshService as facade | ✅ PASS | Internal caches are private (`_item_corpus`, `_category_corpus`). Public interface unchanged. |
| III — Repository as Protocol | ✅ PASS | No changes to `TaxomeshRepositoryBase`. All three backends unaffected. |
| IV — Pydantic + mypy strict | ✅ PASS | New attributes typed as `list[SearchCandidate[Item]] \| None`. All Final constants named. |
| V — Exception hierarchy | ✅ PASS | No new exceptions required. |
| VI — DAG integrity | N/A | No category relationship logic changed. |
| VII — Spec-driven development | ✅ PASS | Spec exists at `specs/040-search-corpus-cache/spec.md`. |
| VIII — Quality gates | ✅ REQUIRED | ruff, mypy --strict, pytest ≥80% coverage must all pass before merge. |
| IX — Framework-agnostic HTTP | N/A | No HTTP layer changes. |
| X — Named constants | ✅ REQUIRED | Any new sentinel or threshold values must use `Final`. No magic literals. |
| XI — OO by default | ✅ PASS | Cache logic lives in `TaxomeshService` class. `SearchEngine` remains stateless utility. |

## Project Structure

### Documentation (this feature)

```text
specs/040-search-corpus-cache/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (affected files only)

```text
taxomesh/
└── application/
    ├── service.py     # PRIMARY: corpus cache attrs, _get_item_corpus(), _get_category_corpus(),
    │                  #          _score_corpus(), _load_item_candidates() fix, search_categories() fix,
    │                  #          invalidation in write methods
    └── search.py      # READ-ONLY: SearchCandidate already correct; no changes expected

tests/
└── service/
    └── test_search_corpus_cache.py   # NEW: corpus reuse, invalidation, and regression tests
```

No new modules. No new packages. No migrations. No repository changes.

## Phase 0: Research

All NEEDS CLARIFICATION items resolved. See `research.md` for full decisions and rationale.

**Key decisions (summary)**:

| ID | Decision |
|----|----------|
| R-001 | Fix `_load_item_candidates(None)` to call `self.list_items()`, not `self._repository.list_items()` |
| R-002 | Use dedicated `None`-sentinel corpus cache (not TTL memoize) for explicit write-triggered invalidation |
| R-003 | Both item and category corpus caches ship in this cycle |
| R-004 | Add `_score_corpus()` method for pre-normalized candidates; keep `_score_and_rank()` for filtered path |
| R-005 | Item writes set `_item_corpus = None`; category writes set `_category_corpus = None`; placement/link ops do not invalidate |
| R-006 | `SearchCandidate` fields unchanged: `obj`, `norm_name`, `norm_slug`, `norm_ext` |
| R-007 | Staged fuzzy scoring deferred to a future cycle |
| R-008 | Tests use call counts and object identity, not wall-clock assertions |

## Phase 1: Design & Contracts

### 1.1 Changes to `taxomesh/application/service.py`

#### New private instance attributes (in `__init__`)

```python
self._item_corpus: list[SearchCandidate[Item]] | None = None
self._category_corpus: list[SearchCandidate[Category]] | None = None
```

#### New private methods

**`_get_item_corpus() -> list[SearchCandidate[Item]]`**

Lazy builder. If `_item_corpus` is `None`, calls `self.list_items()` (memoized), builds `SearchCandidate` wrappers with `SearchEngine.normalize()`, stores in `_item_corpus`, and returns it. On subsequent calls, returns the cached list.

```
if self._item_corpus is None:
    items = self.list_items()
    self._item_corpus = [
        SearchCandidate(item, normalize(item.name), normalize(item.slug), normalize(item.external_id or ""))
        for item in items
    ]
return self._item_corpus
```

**`_get_category_corpus() -> list[SearchCandidate[Category]]`**

Symmetric to `_get_item_corpus()`. Loads all categories via `self._repo.list_categories()` directly (not a memoized service path), excludes the internal root category, builds corpus.

**Deviation note**: `self.list_categories()` was not used here because it returns only root-level children, not all categories — making it semantically incompatible with building a full search corpus. Calling `_repo.list_categories()` directly is intentional; the corpus cache itself eliminates repeated repository calls on subsequent searches.

**`_score_corpus(norm_q, corpus, *, fuzzy, limit) -> list[_T]`**

Accepts `list[SearchCandidate[_T]]`. Iterates corpus, instantiates `SearchEngine()` locally, calls `engine._score_prenorm()` for each candidate (no field normalization — already done at corpus build time). Delegates final ranking to `_rank_scored(scored, limit)`.

**`_rank_scored(scored, limit) -> list[_T]`**

Shared ranking helper extracted during simplify review. Sorts `(score, norm_name, obj)` tuples by `(-score, norm_name)`. Uses `heapq.nsmallest` when `limit < len(scored)` (O(N log k) vs O(N log N) for full sort). Used by both `_score_corpus` and `_score_and_rank`.

#### Fix: `_load_item_candidates()`

Change the `category_id is None` branch from:
```python
return self._repository.list_items()
```
to:
```python
return self.list_items()
```

This is the sole change needed for FR-001. All other branches (filtered, recursive) remain unchanged.

#### Fix: `search_items()` unfiltered path

When `category_id is None` (and after empty-query guard):
- Call `_get_item_corpus()` to get pre-normalized candidates.
- Apply `enabled_only` filter on corpus.
- Call `_score_corpus(norm_q, filtered_corpus, fuzzy=fuzzy, limit=limit)`.
- Return results.

When `category_id is not None`:
- Existing `_load_item_candidates()` → `_score_and_rank()` path. Unchanged.

#### Fix: `search_categories()` unfiltered path

When `parent_id is None`:
- Call `_get_category_corpus()`.
- Call `_score_corpus(norm_q, corpus, fuzzy=fuzzy, limit=limit)`.

When `parent_id is not None`:
- Existing path. Unchanged.

#### Invalidation additions (item writes)

After each of `create_item()`, `update_item()`, `delete_item()`:
```python
clear_all_caches()
self._item_corpus = None
```

#### Invalidation additions (category writes)

After each of `create_category()`, `update_category()`, `delete_category()`:
```python
clear_all_caches()
self._category_corpus = None
```

#### No invalidation for placement/link operations

`place_item_in_category`, `remove_item_from_category`, `reparent_item`, `add_category_parent`, `remove_category_parent`, `reparent_category`, `reorder_*`, `relate_items`, `remove_item_relation`, tag operations — no corpus changes. See `data-model.md` for rationale.

### 1.2 `SearchEngine` in `search.py`

No changes required. `SearchCandidate` and `_score_prenorm()` are already the correct shape. `_score_corpus()` in `service.py` will call `self._engine._score_prenorm()` directly.

### 1.3 Test design (`tests/service/test_search_corpus_cache.py`)

**Test Group 1: Candidate loading reuse (FR-001, FR-002)**
- `test_item_search_reuses_memoized_list_items`: search twice; assert `repository.list_items` called once.
- `test_category_search_reuses_memoized_list_categories`: search twice; assert repository category load called once.

**Test Group 2: Corpus object identity (FR-005, FR-006)**
- `test_item_corpus_built_once_and_reused`: search twice; assert `service._item_corpus is <same object>`.
- `test_category_corpus_built_once_and_reused`: symmetric.

**Test Group 3: Corpus invalidation on writes (FR-009, FR-010)**
- `test_create_item_invalidates_item_corpus`: create item; assert `_item_corpus is None`.
- `test_update_item_invalidates_item_corpus`: update item; assert `_item_corpus is None`.
- `test_delete_item_invalidates_item_corpus`: delete item; assert `_item_corpus is None`.
- `test_create_category_invalidates_category_corpus`: create category; assert `_category_corpus is None`.
- `test_update_category_invalidates_category_corpus`: symmetric.
- `test_delete_category_invalidates_category_corpus`: symmetric.
- `test_item_placement_does_not_invalidate_item_corpus`: place item; assert corpus survives.
- `test_category_link_does_not_invalidate_category_corpus`: add parent; assert corpus survives.

**Test Group 4: Correctness after invalidation (FR-004)**
- `test_new_item_appears_in_search_after_create`: create item "Piazzolla"; search "piazz"; item appears.
- `test_updated_item_name_appears_in_search_after_update`: rename item; new name searchable.
- `test_deleted_item_absent_from_search_after_delete`: delete item; no longer in results.
- `test_new_category_appears_in_search_after_create`: symmetric for categories.

**Test Group 5: Ranking regression (FR-012)**
- `test_exact_match_ranked_first`: item with exact name match outranks partial match.
- `test_fuzzy_search_returns_results`: fuzzy=True returns results for near-match query.
- `test_non_fuzzy_search_excludes_fuzzy_only_matches`: fuzzy=False returns only deterministic matches.
- `test_empty_query_returns_empty`: `search_items("") == []`.
- `test_whitespace_query_returns_empty`: `search_items("   ") == []`.

**Test Group 6: Filtered search unaffected (FR-003)**
- `test_filtered_search_with_category_id_still_works`: category_id filter still restricts results.
- `test_recursive_search_still_works`: recursive=True returns items from subtree.

### 1.4 No new public contracts

This feature has no new public API surface. No `contracts/` directory is created — the feature is purely internal optimization with no externally observable interface changes beyond performance.

### 1.5 No README changes at this stage

No externally observable behavior changes. README search docs remain accurate. README update not required per FR-021 (only required "if internal behavior changes are externally relevant").

## Complexity Tracking

No constitution violations. No complexity justifications required.
