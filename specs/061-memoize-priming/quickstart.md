# Quickstart: what changes for a consumer

Nothing in your code. No signature, return type or exception changes. This is a cost
change only.

## What gets cheaper

Reading a category through `list_categories(parent_id=…)` or
`list_categories_by_item(item_id)` now leaves those categories in the service's
short-lived read cache. A later lookup of one of them — including the parent validation
the next step of a tree walk performs — is served from memory.

The pattern that benefits most is walking a tree node by node, because every node
returned as a *child* becomes the *parent* argument of the following call:

```python
service = TaxomeshService()

def walk(parent_id):
    for child in service.list_categories(parent_id=parent_id):
        yield child
        yield from walk(child.category_id)   # this call no longer re-reads `child`
```

Measured on a 75-node, 3-level tree:

| | storage reads |
|---|---:|
| `0.1.0a49` | 151 |
| `0.1.0a50` | 177 |
| this release | **102** |

A single cold call is unchanged — still 3 reads. The saving is on repeated access, which
is exactly the case the release-060 gates do not measure and the case that regressed.

## What deliberately does not change

`list_items(category_id=…)` does **not** prime the per-item cache. Listing a category's
items then fetching one of them by id still costs one read for that fetch.

This is intentional. Items are large — one measured corpus averages 3,258 bytes of
metadata per row — and the cache has no eviction, so priming a large listing would hold
it until the next write. Measured on that corpus: priming one large item listing costs
**98 MB**, and the whole item corpus **108 MB**, against **0.17 MB** for every category.
Where the endpoint triggering such a listing is public, that becomes a memory-exhaustion
vector rather than merely a large cache. Nothing on the item path regressed in release
060's measurements, so there is no win to weigh against that cost.

If you want it, the prerequisite is eviction in the cache, not a flag.

## Cache semantics, unchanged

- Entries live 5 seconds (`DEFAULT_CACHE_TTL`).
- **Every write clears every cache** — creating, updating or deleting anything calls
  `clear_all_caches()`. A primed entry is cleared by the same call, at the same moment,
  as a normally cached one.
- The cache is per-process. Under a multi-worker server each worker holds its own, and
  a worker that serves requests less often than the TTL sees a cold cache on essentially
  every request.
- A primed entry is indistinguishable from one written by a real call. There is no new
  staleness window: priming stores the row the batch just read, under the same lifetime
  and the same invalidation.
