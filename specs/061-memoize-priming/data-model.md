# Phase 1 Data Model: Memoize priming for batch category reads

No domain entity changes. No stored-data changes. No migration. The only entity this
feature touches is an in-process cache entry.

## Cached entry (existing)

Held in a closure `dict` owned by each decorated function.

| Part | Shape | Meaning |
|---|---|---|
| key | `(args, tuple(sorted(kwargs.items())))` | The arguments the call was made with. For a decorated method, `args[0]` is the bound instance — see research.md R1. |
| value | `(timestamp, result)` | The result, plus the `time.monotonic()` reading when it was stored. |

**Lifetime**: an entry is served while `now - timestamp < ttl`. `DEFAULT_CACHE_TTL` is
5 seconds. An expired entry is not removed — it is overwritten on the next call with
that key, and otherwise persists.

**Invalidation**: every service write calls `clear_all_caches()`, which empties every
registered cache wholesale. There is no per-key invalidation and this feature does not
add one.

## What this feature changes

Exactly one thing: an entry can now come into existence a second way.

| | Before | After |
|---|---|---|
| Written by a call that missed | ✅ | ✅ |
| Written by priming from a batch read | ❌ | ✅ (categories only) |
| Read | unchanged | unchanged |
| Expiry | unchanged | unchanged |
| Invalidation | unchanged | unchanged |

A primed entry is **structurally identical** to a normally cached one: same key shape,
same `(timestamp, result)` value, same TTL, same wholesale invalidation. Nothing
distinguishes them once written, which is the property FR-003 requires and User Story 3
tests.

## Which caches are affected

| Accessor | Primed from | Status |
|---|---|---|
| `get_category` | `list_categories(parent_id=…)` | ✅ primed |
| `get_category` | `list_categories_by_item(item_id)` | ✅ primed |
| `get_item` | `list_items(category_id=…)` | ❌ deliberately not — FR-007 |

The other six memoized reads are untouched.

## Bounds

Entry count is bounded by the number of categories in the corpus, since priming can only
insert rows a batch read returned and those batches are drawn from the category table.
Measured at 93 entries / 0.17 MB on the largest corpus available. Not enforced by code —
see research.md R4.
