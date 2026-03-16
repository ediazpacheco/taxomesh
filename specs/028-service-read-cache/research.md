# Research: Service Read Cache Completeness

## Decision 1 — Memoize key construction for keyword-only arguments

**Decision**: The existing `memoize` utility correctly handles keyword-only
arguments. The key is built as `(args, tuple(sorted(kwargs.items())))`, so
`list_item_relations(item_id, relation_type="covers", direction="incoming")`
and `list_item_relations(item_id, direction="outgoing")` produce distinct
cache entries.

**Rationale**: Verified by reading `taxomesh/utils/memoize.py` line 42. No
utility changes are needed.

**Alternatives considered**: None — this is an existing implementation detail.

---

## Decision 2 — Cache `list_related_items` even though it delegates to cached methods

**Decision**: Add `@memoize(DEFAULT_CACHE_TTL)` to `list_related_items` in
addition to `list_item_relations`.

**Rationale**: `list_related_items` constructs a `list[Item]` by calling
`list_item_relations` (now cached) and `get_item` (already cached). Caching
the final result avoids re-executing list comprehension and multiple dict
lookups per call on hot paths, at the cost of a small amount of additional
memory. The TTL and invalidation semantics are identical to all other cached
methods.

**Alternatives considered**: Leave `list_related_items` uncached and rely on
the cached sub-calls — acceptable but leaves the outer call path unprotected
from amplification.

---

## Decision 3 — Write-invalidation bug scope

**Decision**: Add `clear_all_caches()` to `relate_items` and
`remove_item_relation`. No other write methods are missing this call.

**Rationale**: Audited all write methods in `service.py`. The full list of
write methods and their `clear_all_caches()` status before this fix:

| Method | Has clear_all_caches()? |
|--------|------------------------|
| `create_category` | ✅ |
| `update_category` | ✅ |
| `delete_category` | ✅ |
| `add_category_parent` | ✅ |
| `remove_category_parent` | ✅ |
| `create_item` | ✅ |
| `update_item` | ✅ |
| `delete_item` | ✅ |
| `place_item_in_category` | ✅ |
| `remove_item_from_category` | ✅ |
| `create_tag` | ✅ |
| `delete_tag` | ✅ |
| `assign_tag` | ✅ |
| `remove_tag` | ✅ |
| `relate_items` | ❌ **BUG** |
| `remove_item_relation` | ❌ **BUG** |

**Alternatives considered**: None — all write methods must call
`clear_all_caches()` per project convention.

---

## Decision 4 — No changes to `memoize` utility

**Decision**: `taxomesh/utils/memoize.py` remains unchanged.

**Rationale**: The utility already handles all required cases: TTL expiry,
unhashable-argument fallback (silently bypasses cache and calls the function),
and global registry for `clear_all_caches()`. The feature requires no new
behaviour from the utility.

**Alternatives considered**: Per-method cache invalidation — rejected because
it would require a more complex utility and diverges from the existing
convention of global invalidation on any write.

---

## Decision 5 — Test placement

**Decision**: Append new test classes to the existing
`tests/service/test_service_cache.py`.

**Rationale**: This file already contains cache-specific tests for the eight
previously memoized methods, with the same `_mock_repo()` / `_make_service()`
helpers and `setup_method: clear_all_caches()` pattern. Adding new classes
here keeps all cache tests co-located.

**Alternatives considered**: New file `test_service_cache_relations.py` —
unnecessary split; the existing file's scope covers all service-level cache
tests.
