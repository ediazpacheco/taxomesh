# Implementation Plan: Search Performance for Autocomplete

**Branch**: `039-search-perf` | **Date**: 2026-03-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/039-search-perf/spec.md`

## Summary

Optimize `TaxomeshService.search_items()` and `search_categories()` for autocomplete-style workloads. Two complementary improvements: (1) pre-normalize candidate fields once per search call, eliminating the current double-normalization of names and avoiding repeated slug/ext normalization; (2) replace the full `list.sort()` with `heapq.nlargest` when `limit` is smaller than the number of scored matches, reducing O(N log N) to O(N log k). Public API and result ordering are unchanged.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `rapidfuzz >= 3.0` (existing), `heapq` (stdlib)
**Storage**: N/A — pure in-process optimization; no storage changes
**Testing**: pytest + pytest-cov
**Target Platform**: Any platform supporting Python 3.11+
**Project Type**: Library
**Performance Goals**: Reduce per-call normalization work (currently O(2N) normalizations per call → O(N)); reduce sort cost from O(N log N) to O(N log k) when k << N
**Constraints**: Backward-compatible public API; mypy strict; ruff clean; ≥ 80% coverage
**Scale/Scope**: Two source files (`search.py`, `service.py`); one existing test file extended; one new test file for performance-equivalence tests

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal Architecture | ✅ | Changes confined to `application/` layer; no adapter or domain imports added |
| II. TaxomeshService is single facade | ✅ | `search_items` / `search_categories` signatures unchanged |
| III. Repository as Protocol | ✅ | No repository changes |
| IV. Pydantic + mypy strict | ✅ | `SearchCandidate` will be fully typed; no `Any` added |
| V. Custom exceptions | ✅ | No new exceptions; existing ones preserved |
| VI. DAG integrity | ✅ | Not touched |
| VII. Spec-driven | ✅ | This spec + plan exist |
| VIII. Quality gates | ✅ | ruff, mypy, pytest ≥ 80% cov required before merge |
| IX. Framework-agnostic handlers | ✅ | Not touched |
| X. Named constants | ✅ | No new magic literals; existing constants unchanged |
| XI. OO by default | ✅ | `SearchCandidate` is a class; `_score_prenorm` is a method on `SearchEngine` |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/039-search-perf/
├── plan.md              # This file
├── research.md          # Phase 0 complete
├── data-model.md        # Phase 1 complete
├── quickstart.md        # Phase 1 complete
├── contracts/
│   └── public-api.md    # Phase 1 complete
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (changes)

```text
taxomesh/
└── application/
    ├── search.py          # Add SearchCandidate class; add SearchEngine._score_prenorm()
    └── service.py         # Refactor _score_and_rank to use SearchCandidate + heapq.nlargest

tests/
└── service/
    ├── test_service_search.py     # Extend with top-k equivalence + ordering stability tests
    └── test_search_engine.py      # New: unit tests for SearchCandidate + _score_prenorm

Other:
    CHANGELOG.md           # Performance improvement entry under [Unreleased]
    README.md              # Search section: note autocomplete performance improvement
```

## Implementation Phases

### Phase A: Tests First (TDD)

**A1** — Extend `tests/service/test_service_search.py`:
- Test: top-k path returns same top-`limit` items as full-sort path for ≥ 50 query/catalog combinations
- Test: tie-breaking by normalized name is stable with optimized path
- Test: `search_items(query, limit=5, fuzzy=True)` on catalog with typo still returns fuzzy matches

**A2** — Create `tests/service/test_search_engine.py`:
- Test: `SearchCandidate` stores pre-normalized fields correctly
- Test: `SearchEngine._score_prenorm()` returns same score as `score_candidate()` for identical inputs
- Test: `_score_prenorm()` with pre-normalized fields matches the result of `score_candidate()` on raw fields for all match types (exact, prefix, substring, fuzzy)

### Phase B: Implementation

**B1** — Add `SearchCandidate` to `search.py`:
- Private generic dataclass/class with `obj: _T`, `norm_name: str`, `norm_slug: str`, `norm_ext: str`
- No exports; no changes to module `__all__`

**B2** — Add `SearchEngine._score_prenorm()` to `search.py`:
- Accepts pre-normalized fields directly
- Shares `_compute_boost` and `_compute_fuzzy` with existing `score_candidate`
- `score_candidate` delegates to `_score_prenorm` after normalizing its inputs (avoids logic duplication)

**B3** — Refactor `TaxomeshService._score_and_rank()` in `service.py`:
- Build `list[SearchCandidate[_T]]` from candidates, pre-normalizing all fields once
- Score each candidate using `engine._score_prenorm()`
- Replace `scored.sort(...) + [:limit]` with `heapq.nsmallest(limit, scored, key=lambda t: (-t[0], t[1]))` when `limit < len(scored)`, otherwise use sort; `nsmallest` on `(-score, name)` tuples is the correct call — tuples are stored with negated scores so the smallest tuple corresponds to the highest-scoring, alphabetically-earliest candidate (`nlargest` and `nsmallest` are equivalent when the key negates the primary field, but `nsmallest` matches the stored tuple representation)
- Keep tie-breaking: sort key is `(-score, norm_name)`

### Phase C: Docs

**C1** — `CHANGELOG.md`: add performance improvement note under `[Unreleased]`
**C2** — `README.md`: update search section to note autocomplete performance

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Cross-call normalization cache | Deferred | Requires catalog version tracking; out of scope |
| `heapq.nsmallest` threshold | Always apply when `limit < len(scored)` | Simpler; stdlib handles large-k fallback; `nsmallest` used because scored tuples store `(-score, name)` |
| `score_candidate` public method | Unchanged — delegates to `_score_prenorm` | Preserves public API; avoids logic duplication |
| `SearchCandidate` scope | Private, not exported | Internal optimization detail only |

## Residual Risks

- If a future feature adds a catalog mutation in the middle of a search call (impossible in current single-threaded library usage), pre-normalization would be stale. Acceptable given current design.
- Cross-call normalization caching (deferred) would provide larger gains for long autocomplete sessions. Noted for a future spec.
