# Research: Bulk Item Lookup by External ID (052)

**Branch**: `052-bulk-external-id-lookup`
**Date**: 2026-03-23

No open unknowns were found in the spec. All decisions below are derived from existing
codebase patterns and the feature requirements.

---

## Decision 1: Enabled Filtering — Adapter vs. Service Layer

**Decision**: `enabled` filtering is delegated to the repository adapter.

**Rationale**: Consistent with `list_items(*, enabled: bool | None = True)` and
`list_categories(*, enabled: bool | None = True)`, which delegate filtering to each
adapter. The Django adapter achieves this with a single `qs.filter(enabled=enabled)` call
(no post-processing). File-backed adapters (JSON, YAML) apply it during the single scan
of `self._items`.

**Alternatives considered**:
- Filter in the service after the repo returns all matches — simpler port signature, but
  forces file adapters to return disabled items only to discard them; loses the ability
  for Django to push the filter to SQL. Rejected.

---

## Decision 2: Input Type at the Port Boundary

**Decision**: Port receives `Collection[str]` — already normalized and deduplicated.
The service is responsible for converting `Iterable[str]` → normalized `set[str]`.

**Rationale**: Repositories must not be concerned with normalization (that is a service
responsibility, matching the existing `get_item_by_external_id` pattern where the
service passes `str(external_id)` to the repo). Passing a `Collection[str]` (specifically
a `set`) lets adapters use it directly in `filter(external_id__in=...)` without re-iterating.

**Alternatives considered**:
- Accept `Iterable[str]` at the port — simpler signature but forces each adapter to
  materialise the iterable (risk of double consumption with generators). Rejected.
- Accept `frozenset[str]` at the port — fully hashable, but unnecessarily restrictive for
  adapters that don't need hashing. `Collection[str]` is sufficient. Not chosen.

---

## Decision 3: Memoization

**Decision**: The service method IS decorated with `@memoize(DEFAULT_CACHE_TTL)`,
consistent with all other read methods on `TaxomeshService`.

**Rationale**: All service read methods use `@memoize` for TTL-based caching.
`get_items_by_external_ids` is a read method and must follow the same pattern.

The `memoize` decorator uses `(args, kwargs)` as the cache key and falls back
silently for unhashable arguments. Because the public signature accepts
`Iterable[str]` (lists and generators are unhashable), putting `@memoize` directly
on the public method would silently skip caching for most callers.

The solution is a two-method pattern:
- `get_items_by_external_ids(Iterable[str])` — public, normalises input to
  `frozenset[str]`, delegates to the private method.
- `_fetch_items_by_external_ids(frozenset[str])` — private, decorated with
  `@memoize(DEFAULT_CACHE_TTL)`. `frozenset` is hashable, so the cache key
  `(self, frozenset({...}), (('enabled', value),))` is always valid.

**Alternatives considered**:
- Decorate the public method directly — rejected; list/generator inputs would
  bypass the cache silently, giving no TTL benefit in practice.
- Change public API to `frozenset[str]` — rejected; too restrictive for callers
  who hold lists or generators.

---

## Decision 4: No New Migration Required

**Decision**: No new database migration is needed.

**Rationale**: `external_id` already has a database index on both `taxomesh_item` and
`taxomesh_category` (added in spec 032-external-id-index via migration 0004). The Django
`filter(external_id__in=...)` query will use that index. File-backed adapters perform
an O(n) scan regardless of indexes.

---

## Decision 5: Symmetric Category Method

**Decision**: A symmetric `get_categories_by_external_ids` is added alongside
`get_items_by_external_ids`.

**Rationale**: Callers that resolve categories by external ID have the same N+1 problem
as callers resolving items. The implementation is structurally identical. Root category
exclusion — already enforced in `get_category_by_external_id` — is applied in the
service as a post-filter after the memoized repository call.

**Root category exclusion placement**: Service post-filters on `category_id == self._root_id`
after the memoized call. Adapters return raw results; they do not know what the root ID is.
This mirrors the existing `get_category_by_external_id` pattern.

**Alternatives considered**:
- Exclude root in the adapter — rejected; adapters have no knowledge of which category is root.
- One combined method returning both items and categories — rejected; overcomplicates the API
  and violates single-responsibility.

---

## Decision 7: No `contrib.api` Handler

**Decision**: No handler is added to `taxomesh.contrib.api.handlers` in this spec.

**Rationale**: The bulk lookup is a service-layer API fix targeting library consumers
(e.g. LetrasTango) who call the service directly. Adding a contrib handler is a separate
concern outside the stated scope. It can be added in a follow-up spec if needed.

---

## Decision 8: `enabled` Default Value

**Decision**: Default is `None` (return all matching items regardless of enabled state).

**Rationale**: Specified explicitly in the feature description. A bulk resolution by
explicit IDs is a targeted operation — the caller knows which IDs it wants and opts in
to filtering. This differs from `list_items()` (default `True`) because listing is a
browsable operation where disabled items are typically hidden.
