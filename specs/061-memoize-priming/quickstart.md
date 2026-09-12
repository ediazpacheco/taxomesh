# Quickstart: what changes for a consumer

Nothing in your code, unless you import from `taxomesh.utils.memoize` directly. No service
signature, return type or exception changes. This is a cost change.

## What gets cheaper

`list_categories(parent_id=…)` and `list_categories_by_item(item_id)` now do two things
they did not do on `0.1.0a50`:

- **Prime** — every category row they fetch is left in the service's short-lived read
  cache, so a later `get_category` for it costs nothing.
- **Read through** — before fetching, they consult that cache and fetch only the rows not
  already in it. When every row is cached, they read nothing at all.

The pattern that benefits most is walking a tree node by node, because every node returned
as a *child* becomes the *parent* argument of the following call, and that argument is
validated through `get_category`:

```python
service = TaxomeshService()

def walk(parent_id):
    for child in service.list_categories(parent_id=parent_id):
        yield child
        yield from walk(child.category_id)   # this call no longer re-reads `child`
```

Measured on a 75-node, 3-level tree shaped like the one production corpus
(research.md R6, reproduced 2026-09-12):

| | storage reads |
|---|---:|
| `0.1.0a49` | 150 |
| `0.1.0a50` | 177 |
| this release | **103** |

103 rather than 0 because the walk's own root is nobody's child, so nothing primes it: its
one validation is a genuine read. Every other node's is free.

A single cold call is unchanged — still 3 reads. The saving is on repeated access, which is
exactly the case release 060's gates do not measure and the case that regressed.

Other measured category patterns, all at or below `0.1.0a49`:

| pattern | `0.1.0a49` | `0.1.0a50` | this release |
|---|---:|---:|---:|
| walk, 12 nodes, depth 2 | 26 | 30 | **18** |
| walk, 84 nodes, depth 3 | 170 | 191 | **107** |
| walk over a multi-parent tree | 12 | 16 | **9** |
| fetch children by id, then list them | 7 | 8 | **7** |
| `list_categories_by_item` × 40 over 5 categories | 85 | 120 | **84** |

## What deliberately does not change

`list_items(category_id=…)` neither primes nor reads through the per-item cache. Listing a
category's items and then fetching one by id still costs one read for that fetch.

That leaves three patterns costing slightly more than `0.1.0a49` — **at most one extra read
per `list_items(category_id=…)` call in the pattern**:

| pattern | `0.1.0a49` | this release |
|---|---:|---:|
| `list_items`, then `list_categories_by_item` per item (20) | 45 | 46 |
| `list_items`, then `get_item` per item (20) | 22 | 23 |
| 10 small `list_items` calls sharing 3 items | 23 | 30 |

Every other item pattern is *cheaper* than `0.1.0a49`, by 060's batch saving itself — a
cold `list_items` over 20 items went from 22 reads to 3.

This is intentional. Items are large — one measured corpus averages 3,258 bytes of metadata
per row — and the cache has no eviction, so anything primed is held until the next write.
Priming `get_item` measured **+2.37 MB** per `list_items` call on a 2,000-item fixture
(research.md R7); the one production consumer measured **108 MB per worker** on its own
corpus, on a host already swapping, reachable through a public unauthenticated endpoint.
Nothing on the item path regressed in 060's measurements, so there is no win to weigh
against that.

If you want it, the prerequisite is eviction in the cache, not a flag.

### The retention you already have

Worth stating plainly, because not priming items does **not** mean a listing is not
retained: `list_items` is itself memoized, so its result list — the same `Item` objects —
is held until the next write regardless. On that 2,000-item fixture one
`list_items(category_id=…)` call left **17.44 MB** retained on `0.1.0a50`, against 20.06 MB
on `0.1.0a49`. Not priming avoids only the 2.37 MB increment. The retention itself is a
pre-existing property of the unbounded cache.

## Cache semantics, unchanged

- Entries live 5 seconds (`DEFAULT_CACHE_TTL`), measured **from the fetch**. Neither a call
  that hits nor a read-through lookup extends that.
- **Every write clears every cache** — creating, updating or deleting anything calls
  `clear_all_caches()`. A primed entry is cleared by the same call, at the same moment, as a
  normally cached one.
- The cache is per-process. Under a multi-worker server each worker holds its own, and a
  worker that serves requests less often than the TTL sees a cold cache on essentially every
  request.
- A primed entry is indistinguishable from one written by a real call. There is no new
  staleness window: priming stores the row the batch just read, under the same lifetime and
  the same invalidation.
- Category reads other than the two above — `get_graph`, `get_category_by_slug`,
  `get_category_by_external_id`, `get_categories_by_external_ids`, and search — neither
  prime nor read through. None of them did on `0.1.0a49` either.

## If you decorate your own functions with `taxomesh.utils.memoize`

`memoize(ttl)` keeps its name and call syntax; you change nothing. What it *returns* is now
a typed object rather than a plain function, which gains you two operations:

```python
from taxomesh.utils.memoize import Miss, memoize

@memoize(5)
def paths_from_main() -> dict[int, str]:
    ...

hit = paths_from_main.cached()          # -> dict[int, str] | Miss, never touches the cache
if isinstance(hit, Miss):
    paths_from_main.prime(computed)     # value and arguments are type-checked
paths_from_main.clear_cache()           # unchanged
```

Zero-argument and keyword-only functions are supported and type-checked, and a decorated
callable still reports its own `__name__`, `__doc__` and signature, so `help()` and
`inspect.signature` behave as before.

**One removal**: the module-level `prime(func, value, …)` helper that existed briefly on the
`061` branch is gone — priming is a method now. It was never released, so no published
version exposed it.
