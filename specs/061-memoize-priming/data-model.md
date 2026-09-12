# Phase 1 Data Model: Category priming and read-through

No domain entity changes. No stored-data changes. No migration. The only entity this
feature touches is an in-process cache entry.

## Cached entry

| Part | Shape | Meaning |
|---|---|---|
| key | `(args, tuple(sorted(kwargs.items())))` | The arguments the call was made with. For a decorated method, `args[0]` is the bound instance — research.md R1. |
| value | `(stored_at, result)` | The result, plus the `time.monotonic()` reading when it was stored. |

**Lifetime**: an entry is served while `now - stored_at < ttl`. `DEFAULT_CACHE_TTL` is 5
seconds. **Lifetime is measured from the fetch, not from the last access** — neither a call
that hits nor a read-through lookup refreshes `stored_at` (FR-004). An expired entry is not
removed; it is overwritten on the next fetch with that key, and otherwise persists.

**Invalidation**: every service write calls `clear_all_caches()`, which empties every
registered cache wholesale. There is no per-key invalidation and this feature does not add
one.

## The types

| Type | Role |
|---|---|
| `MemoizedFunction[**P, R]` | What `memoize(ttl)` returns. Owns the cache dict. A descriptor, so it binds as a method. |
| `MemoizedMethod[**P, R]` | What accessing a `MemoizedFunction` on an instance returns. Prepends that instance to every key. Holds no cache of its own. |
| `Miss` | Singleton marking "no fresh entry". Lets `cached` distinguish a miss from a cached `None` or other falsy value. |

Both callable types expose the same four operations, each typed against the decorated
callable's own parameters and return type:

| Operation | Signature | Reads storage? | Writes the cache? |
|---|---|---|---|
| call | `(*args: P.args, **kwargs: P.kwargs) -> R` | on a miss | on a miss |
| `prime` | `(value: R, /, *args: P.args, **kwargs: P.kwargs) -> None` | never | always |
| `cached` | `(*args: P.args, **kwargs: P.kwargs) -> R \| Miss` | never | **never** |
| `clear_cache` | `() -> None` | never | empties it |

`cached` being strictly read-only is a requirement, not an implementation note (FR-003): it
is what keeps a read-through hit from extending an entry's lifetime.

## What this feature changes

| | Before | After |
|---|---|---|
| Written by a call that missed | ✅ | ✅ |
| Written by priming from a batch read | ❌ | ✅ (categories only) |
| Consulted without calling the accessor | ❌ | ✅ (`cached`) |
| Key shape | unchanged | unchanged |
| Expiry | unchanged | unchanged |
| Invalidation | unchanged | unchanged |

A primed entry is **structurally identical** to a normally cached one: same key, same
`(stored_at, result)` value, same TTL, same wholesale invalidation. Nothing distinguishes
them once written — the property FR-004 requires and User Story 3 tests.

## Which caches are affected

| Accessor | Touched by | Primes | Reads through |
|---|---|---|---|
| `get_category` | `list_categories(parent_id=…)` | ✅ | ✅ |
| `get_category` | `list_categories_by_item(item_id)` | ✅ | ✅ |
| `get_item` | `list_items(category_id=…)` | ❌ FR-007 | ❌ FR-007 |

The other 14 memoized reads are untouched. Category reads that resolve rows *outside* these
two — `get_graph`, the search corpus builder, `get_category_by_slug`,
`get_category_by_external_id`, `get_categories_by_external_ids` — neither prime nor read
through, by decision (spec Clarifications, 2026-09-12): none of them primed on `0.1.0a49`
either, so none is a regression.

## Bounds

Entry count is bounded by the number of categories in the corpus, since priming can only
insert rows a category batch returned. Measured at 93 entries / 0.17 MB on the largest
corpus available. Not enforced by code — research.md R4.
