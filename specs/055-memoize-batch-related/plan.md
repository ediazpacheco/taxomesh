# Implementation Plan: Memoize Batched Related-Items Lookup

**Branch**: `055-memoize-batch-related` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/055-memoize-batch-related/spec.md`

## Summary

`TaxomeshService.list_related_items_for_sources` is the only read method in the service
without `@memoize(DEFAULT_CACHE_TTL)` caching. This feature memoizes it using the
established public-normaliser → private-memoized-implementation pattern
(`get_items_by_external_ids` → `_fetch_items_by_external_ids`): the public method
normalises its unhashable arguments (`Collection[UUID]` → `frozenset`,
`relation_types` → stripped/lowered, deduplicated, sorted `tuple[str, ...] | None`)
and delegates to a private `_fetch_related_items_for_sources` decorated with
`@memoize(DEFAULT_CACHE_TTL)`. `skip_on_error` stays in the cache key. Invalidation via
`clear_all_caches()` is automatic because `memoize` registers every cache in
`_cache_registry`. Additionally (FR-009), `list_related_items` swaps its per-link
`self.get_item(...)` loop for one bulk `self._repo.get_items_by_ids(...)` call on the
cold path, preserving result order and error behaviour.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 (domain models); no new dependencies. Uses existing `taxomesh/utils/memoize.py` TTL cache utility.
**Storage**: N/A — pure in-process cache; no storage or migration changes. All repository adapters (Json, YAML, Django, InMemory) untouched.
**Testing**: pytest with `MagicMock` repository (mirrors `tests/service/test_service_cache.py`)
**Target Platform**: Library — any platform supported by Python 3.11+
**Project Type**: Library (single project)
**Performance Goals**: Second identical batched call within TTL → 0 repository queries; cold `list_related_items` target resolution → 1 bulk query instead of N per-target queries.
**Constraints**: Observable behaviour of both methods unchanged (return shape, ordering, normalisation, dangling-link handling, raised errors, exact error messages). Public signatures unchanged.
**Scale/Scope**: Two methods in `taxomesh/application/service.py` + one new private helper; one test file extension; CHANGELOG + version bump.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal architecture | ✅ PASS | Change confined to `application/service.py`; depends only on `ports` + `utils`. No adapter changes. |
| II. TaxomeshService single facade | ✅ PASS | Public surface unchanged; new helper is private. |
| III. Repository as Protocol | ✅ PASS | Uses existing port methods (`list_item_relation_links_for_sources`, `get_items_by_ids`); no port changes. |
| IV. Pydantic models + mypy strict | ✅ PASS | No model changes; new helper fully typed, no `Any`. |
| V. Exception hierarchy, no silent failures | ✅ PASS | `TaxomeshItemNotFoundError` semantics preserved exactly (incl. messages). Exceptions are never cached (memoize only stores returned values). |
| VI. DAG integrity | ✅ PASS | Not touched. |
| VII. Spec-driven development | ✅ PASS | This spec (055). |
| VIII. Quality gates | ✅ PASS | ruff / ruff format / mypy --strict / pytest ≥ 80 % run before commit. |
| IX. Framework-agnostic handlers | ✅ PASS | `contrib.api` untouched. |
| X. Named constants | ✅ PASS | Reuses existing `DEFAULT_CACHE_TTL`; no new literals. |
| XI. Object-oriented by default | ✅ PASS | New logic is a private method on `TaxomeshService`. |

**Post-design re-check (Phase 1)**: all gates still pass — no new violations introduced by the design below.

## Project Structure

### Documentation (this feature)

```text
specs/055-memoize-batch-related/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── service-api.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
taxomesh/
└── application/
    └── service.py       # list_related_items_for_sources (normalise + delegate),
                         # new _fetch_related_items_for_sources (@memoize),
                         # list_related_items (bulk target resolution — FR-009)

tests/
└── service/
    └── test_service_cache.py   # new TestBatchRelatedItemsCaching class (FR-007)

CHANGELOG.md             # new 0.1.0a44 entry (FR-008)
pyproject.toml           # version bump 0.1.0a43 → 0.1.0a44
taxomesh/__init__.py     # __version__ sync (kept in sync since 0.1.0a43)
```

**Structure Decision**: Single-project library layout (existing). All production
changes live in `taxomesh/application/service.py`; tests extend the existing
service-cache test module.

## Design

### 1. Memoize `list_related_items_for_sources` (FR-001…FR-006)

Public method keeps its exact signature and docstring contract; its body becomes
normalisation + delegation:

```python
def list_related_items_for_sources(self, source_item_ids, *, relation_types=None, skip_on_error=True):
    unique_ids = frozenset(source_item_ids)          # was: set(...)
    if not unique_ids:
        return {}
    normalised_types = (
        tuple(sorted({t.strip().lower() for t in relation_types})) if relation_types else None
    )
    return self._fetch_related_items_for_sources(
        unique_ids, relation_types=normalised_types, skip_on_error=skip_on_error
    )

@memoize(DEFAULT_CACHE_TTL)
def _fetch_related_items_for_sources(
    self,
    source_item_ids: frozenset[UUID],
    *,
    relation_types: tuple[str, ...] | None,
    skip_on_error: bool,
) -> dict[UUID, dict[str, list[Item]]]:
    # existing body from the repo-call onwards, unchanged
```

Key decisions (full rationale in [research.md](research.md)):

- **`frozenset` for source IDs** — order/duplicate insensitive, hashable (FR-002).
- **Sorted tuple for relation types** — deduplicated set, then sorted tuple: hashable,
  order-insensitive, deterministic repository call argument. `None` and empty
  collection both normalise to `None` (one "no filter" entry, FR-002).
- **`skip_on_error` in the key** — passed as a kwarg to the memoized method, so it is
  part of the cache key automatically (FR-003).
- **Empty input short-circuits before the cache** — `{}` returned without polluting
  the cache, identical to today.
- **Raised errors are never cached** — `memoize` stores only returned values; a
  `TaxomeshItemNotFoundError` under `skip_on_error=False` propagates and the next call
  re-queries (spec edge case).
- **Invalidation is automatic (FR-004)** — `@memoize` registers `clear_cache` in
  `_cache_registry`; every write path already calls `clear_all_caches()`.

### 2. Bulk target resolution in `list_related_items` (FR-009)

Replace the per-link `self.get_item(...)` comprehension with one bulk repository call,
preserving order, duplicates, enabled-state behaviour (`get_item` ignores `enabled`,
so the bulk call uses `enabled=None`) and the exact `Item not found: {id}` error:

```python
links = self.list_item_relations(item_id, relation_type=relation_type, direction=direction)
attr = "target_item_id" if direction == "outgoing" else "source_item_id"
ordered_ids = [getattr(lnk, attr) for lnk in links]
if not ordered_ids:
    return []
item_map = self._repo.get_items_by_ids(set(ordered_ids), enabled=None)
result = []
for needed_id in ordered_ids:
    found = item_map.get(needed_id)
    if found is None:
        raise TaxomeshItemNotFoundError(f"Item not found: {needed_id}")
    result.append(found)
return result
```

This stays within the "only if it doesn't complicate the code" bound: same length
order of magnitude, one repository round-trip on the cold path, identical observable
behaviour (verified by existing tests in `test_service_item_relations.py` and
`test_service_list_related_resilience.py`).

### 3. Tests (FR-007)

New `TestBatchRelatedItemsCaching` class in `tests/service/test_service_cache.py`,
mirroring the existing class style (`setup_method` → `clear_all_caches()`, MagicMock
repo, `assert_called_once` / `call_count`):

- (a) two identical batched calls → `repo.list_item_relation_links_for_sources.assert_called_once()`
- (b) `relation_types=["a","b"]` then `["B", "a ", "b"]` → still one repo call (shared entry)
- source IDs reordered/duplicated → one repo call
- `relation_types=None` vs `[]` → one repo call
- `skip_on_error=True` vs `False` → two repo calls (distinct entries)
- (c) `clear_all_caches()` between identical calls → two repo calls
- write (`relate_items`) between identical calls → two repo calls
- FR-009: cold `list_related_items` with N links → `repo.get_items_by_ids` called once,
  `repo.get_item` not called; order preserved; missing target raises
  `TaxomeshItemNotFoundError`.

### 4. Release (FR-008)

- CHANGELOG: new `## [0.1.0a44]` entry under Performance (matches 0.1.0a42 style).
- `pyproject.toml` version → `0.1.0a44`; `taxomesh/__init__.py` `__version__` synced.

## Complexity Tracking

No constitution violations — table not required.
