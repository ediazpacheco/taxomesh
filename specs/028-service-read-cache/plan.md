# Implementation Plan: Service Read Cache Completeness

**Branch**: `028-service-read-cache` | **Date**: 2026-03-08 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing `@memoize(DEFAULT_CACHE_TTL)` cache to four uncovered read
methods in `TaxomeshService`, and add the missing `clear_all_caches()` call to
two write methods that mutate item relations. All changes are confined to
`taxomesh/application/service.py`. New tests go into the existing
`tests/service/test_service_cache.py`.

---

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: `taxomesh/utils/memoize.py` (existing TTL cache utility)  
**Storage**: N/A — pure in-process cache; no new storage, no migrations  
**Testing**: pytest + pytest-cov (`tests/service/test_service_cache.py`)  
**Target Platform**: Library (all environments where taxomesh runs)  
**Project Type**: Library — service layer enhancement  
**Performance Goals**: Repeated identical calls within 5-second TTL window hit
the data store at most once per unique argument set  
**Constraints**: No changes to public API signatures, return types, or
exception types; no new dependencies  
**Scale/Scope**: 6 targeted edits in a single file

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ PASS | Cache utility lives in `taxomesh/utils/`; decorating `service.py` methods introduces no inward dependency violations. |
| II — Single Facade | ✅ PASS | All changes are on `TaxomeshService` methods; the facade contract is unchanged. |
| III — Repository Protocol | ✅ PASS | No repository interface changes. |
| IV — Pydantic + mypy strict | ✅ PASS | `@memoize` is already typed and passes mypy strict; no new `Any` usage. |
| V — Exception Hierarchy | ✅ PASS | No new exceptions; existing error propagation unchanged. |
| VII — Spec-Driven | ✅ PASS | This plan is generated from spec.md. |
| VIII — Quality Gates | ✅ PASS | Existing test suite passes; new cache tests will be added. |
| X — Named Constants | ✅ PASS | `DEFAULT_CACHE_TTL` already defined; no new magic literals. |
| XI — OO by Default | ✅ PASS | Decorator additions only; no new module-level state introduced. |

No violations. No Complexity Tracking table required.

---

## Project Structure

### Documentation (this feature)

```text
specs/028-service-read-cache/
├── plan.md              ← this file
├── research.md
├── data-model.md        ← N/A (no new entities; omitted)
└── tasks.md             ← /speckit.tasks output
```

### Source Code (affected files only)

```text
taxomesh/application/service.py          ← 6 targeted edits
tests/service/test_service_cache.py      ← new test classes appended
```

---

## Phase 0 — Research Findings

See [research.md](research.md).

---

## Implementation Phases

### Phase 1 — Write-Invalidation Bug Fixes (blocking)

Fix `relate_items` and `remove_item_relation`: both mutate relation data but
omit `clear_all_caches()`. These MUST be fixed before the read-cache additions
are useful — otherwise a write would leave stale cached data in the four newly
protected methods.

**Files**: `taxomesh/application/service.py`

### Phase 2 — Cache Additions for Read Methods

Add `@memoize(DEFAULT_CACHE_TTL)` to:

| Method | Keyword args that form cache key |
|--------|----------------------------------|
| `get_items_by_external_id(external_id)` | none (positional only) |
| `get_categories_by_external_id(external_id)` | none (positional only) |
| `list_item_relations(item_id, *, relation_type, direction)` | `relation_type`, `direction` |
| `list_related_items(item_id, *, relation_type, direction)` | `relation_type`, `direction` |

The existing `memoize` decorator builds its key from
`(args, tuple(sorted(kwargs.items())))` — keyword-only arguments like
`relation_type` and `direction` are therefore correctly captured.

**Files**: `taxomesh/application/service.py`

### Phase 3 — Tests

Append new test classes to `tests/service/test_service_cache.py` covering:

- `get_items_by_external_id` returns cached result on second call
- `get_categories_by_external_id` returns cached result on second call
- `list_item_relations` returns cached result on second call
- `list_item_relations` with `direction="incoming"` is a distinct cache entry
- `list_related_items` returns cached result on second call
- `relate_items` invalidates the relation cache
- `remove_item_relation` invalidates the relation cache

---

## Key Decisions

### D1 — Cache `list_related_items` independently of `list_item_relations`

`list_related_items` delegates to `list_item_relations` (cached) and
`get_item` (cached). Adding cache to `list_related_items` as well avoids
re-traversing the cached sub-calls on hot paths and stores the fully resolved
`list[Item]` result directly.

### D2 — `clear_all_caches()` scope

`clear_all_caches()` clears every registered cache. This is the existing
project-wide convention. No targeted per-method invalidation is introduced
(consistent with all other write methods).

### D3 — No changes to `memoize` utility

The utility already handles: TTL expiry, unhashable-arg fallback (returns
result without caching), and `clear_cache()` registration. No changes needed.
