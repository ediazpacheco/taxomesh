# Research: Repository-Level Enabled Filtering

**Branch**: `046-repo-enabled-filter`
**Date**: 2026-03-21

---

## Decision 1: Three-Way `enabled` Parameter (`bool | None`)

**Decision**: The `enabled` parameter on `list_categories` and `list_items` is typed
`bool | None` with a default of `True`.

| Value   | Meaning                          | Used by                                      |
|---------|----------------------------------|----------------------------------------------|
| `True`  | Return only enabled records (default) | All public API surfaces (default)       |
| `False` | Return only disabled records     | Admin debugging, test fixtures               |
| `None`  | Return all records (no filter)   | Search corpus build, Django admin import views |

**Rationale**: The spec requires:
1. Default `enabled=True` for all public methods (Q1 answer).
2. `--include-disabled` CLI flag and `?include_disabled=true` API param that return all
   records (both enabled and disabled).
3. Search corpus caching (`_get_item_corpus`, `_get_category_corpus`) must hold all
   records so `search_items(enabled=False)` works correctly.

Without a `None` sentinel, fulfilling points 2 and 3 would require calling the repo
twice (once with `True`, once with `False`) and merging — an ugly N+1 pattern.
`bool | None = True` is the minimal contract extension that satisfies all requirements
without introducing a new method or sentinel type.

**Alternatives considered**:
- Two separate calls and merge: rejected — N+1 queries, more complex code.
- New `list_all_categories()` method: rejected — violates YAGNI; the `None` sentinel
  achieves the same result within the existing method.

---

## Decision 2: Handler / CLI Surface Uses `include_disabled: bool = False`

**Decision**: Public-facing surfaces (CLI flags, API query params, handler function
signatures) use `include_disabled: bool = False` which internally translates to
`enabled=None` when True.

**Rationale**: The spec specifies `--include-disabled` and `?include_disabled=true`
as the external contract. Exposing `enabled: bool | None` directly at the API level
would be confusing to consumers (what does `None` mean?). The `include_disabled` flag
is semantically clear. Internally, handlers translate:

```
include_disabled=False → enabled=True   (default: only enabled)
include_disabled=True  → enabled=None   (all records)
```

Service-layer callers who need disabled-only can still use `enabled=False` directly.

---

## Decision 3: `list_categories_by_item` Uses Python-Level Filtering

**Decision**: `list_categories_by_item` cannot delegate the `enabled` filter to the
repository because its implementation calls `get_category()` for each individual link
(one record lookup at a time). Python-level filtering of the returned categories is
used.

**Rationale**: Single-record lookups (`get_category`) are explicitly out of scope per
the clarification session. Refactoring `list_categories_by_item` to use a bulk query
is a separate optimization concern beyond this feature's scope.

**Alternatives considered**:
- Add a new repo method `list_categories_by_item_id(item_id, enabled)`: rejected —
  out of scope; a separate spec should drive bulk-lookup optimizations.

---

## Decision 4: `get_graph` Adds `enabled: bool = True` Parameter

**Decision**: `get_graph(*, enabled: bool = True) -> TaxomeshGraph` filters both
categories **and** items in the graph by the enabled state, since `TaxomeshGraph`
contains `CategoryNode.items: list[Item]` as well as category nodes.

**Rationale**: `TaxomeshGraph` is a composite snapshot: categories + items embedded
in each category node. Filtering categories by `enabled` while leaving disabled items
visible in the tree would violate the coherence principle. Both `list_categories()` and
`list_items()` are called internally by `get_graph` — both will receive the same
`enabled` value.

**Alternatives considered**:
- Separate `enabled_categories` and `enabled_items` params: rejected — unnecessary
  complexity; no spec requirement for independent control.

---

## Decision 5: Search Corpus Remains Full (All Records)

**Decision**: `_get_item_corpus()` calls `list_items(enabled=None)` and
`_get_category_corpus()` calls `list_categories(enabled=None)`. The corpus holds all
records. The `enabled` filter on `search_items` / `search_categories` is applied at
corpus-slice time (same as today, just renamed from `enabled_only`).

**Rationale**: The corpus is a pre-normalized search index. Rebuilding the corpus each
time the `enabled` filter changes would defeat the caching purpose. Keeping the corpus
full and filtering at query time preserves cache efficiency. The performance benefit of
repo-level filtering applies only to direct listing calls, not to cached corpus slices.

**Alternatives considered**:
- Two corpora (enabled/disabled): rejected — doubles memory, adds invalidation complexity.
- Filter at corpus-build time with `enabled=True`: rejected — breaks
  `search_items(enabled=False)` queries.

---

## Decision 6: Django Admin Internal Calls Use `enabled=None`

**Decision**: Admin views that call `repo.list_categories()` or
`svc.list_categories()`/`svc.list_items()` for structural/management purposes
(import, sync, drag-drop tree, child-listing) must explicitly pass `enabled=None`
to retrieve all records regardless of enabled state.

**Rationale**: Admin users need to manage disabled records — rename, re-enable, audit.
The Django admin's Category and Item changeviews already have `list_filter = ("enabled",
...)` allowing sidebar filtering. The default `enabled=True` is appropriate for the
public-facing admin tree rendering; internal management views need `enabled=None`.

**Affected admin call sites**:
- `repo.list_categories()` (line ~1014) — used to find root category: needs `enabled=None`
- `repo.list_categories()` (line ~1044) — used for import/sync: needs `enabled=None`
- `svc.list_categories(parent_id=...)` (line ~1124) — child listing in drag-drop view:
  needs `enabled=None` (admin management context)
- `svc.list_items(category_id=...)` (line ~1125) — item listing in drag-drop view:
  needs `enabled=None` (admin management context)

---

## Affected Files Inventory

| File | Change type |
|------|-------------|
| `taxomesh/ports/repository.py` | Signature change: `list_categories`, `list_items` |
| `taxomesh/application/service.py` | `list_categories`, `list_items`, `list_categories_by_item`, `search_items`, `search_categories`, `get_graph`, `_get_item_corpus`, `_get_category_corpus` |
| `taxomesh/adapters/repositories/json_repository.py` | Implement `enabled` filter |
| `taxomesh/adapters/repositories/yaml_repository.py` | Implement `enabled` filter |
| `taxomesh/adapters/repositories/django_repository.py` | Implement `enabled` filter at ORM level |
| `taxomesh/adapters/cli/main.py` | Add `--include-disabled` to `category list`, `item list`, `graph` |
| `taxomesh/contrib/api/handlers.py` | Add `include_disabled` param to `list_categories`, `list_items`, `get_graph`; rename `enabled_only` in search handlers |
| `taxomesh/contrib/api/schemas.py` | Rename `enabled_only` → `enabled` in search schemas; add `include_disabled` to list schemas |
| `taxomesh/contrib/django/admin.py` | Update internal repo/service calls to use `enabled=None` |
| `tests/service/conftest.py` | Update `InMemoryRepository.list_categories`, `list_items` |
| All test files touching enabled filter | Update to new API |
