# Quickstart: Memoize Batched Related-Items Lookup

**Feature**: 055-memoize-batch-related

## What changes for consumers

Nothing in your code — `list_related_items_for_sources` now simply joins the read
cache like every other read method. The old trade-off (batched call = cheaper cold but
re-queries every call; per-type loop = N+1 cold but free warm) is gone: the batched
call is now at most 2 repository queries cold and 0 warm.

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

ids = [song_a.item_id, song_b.item_id]

# Cold: 2 repository queries (links + bulk items)
related = service.list_related_items_for_sources(ids, relation_types=["performed_by"])

# Warm (within the 5 s TTL): 0 repository queries — served from cache.
# Ordering, duplicates, case and whitespace don't fragment the cache:
related_again = service.list_related_items_for_sources(
    [song_b.item_id, song_a.item_id, song_a.item_id],
    relation_types=["PERFORMED_BY "],
)
assert related_again is related  # same cached object

# Any write — or an explicit clear — invalidates:
service.relate_items(song_a.item_id, label.item_id, "released_by")
fresh = service.list_related_items_for_sources(ids)  # re-queries the repository
```

`list_related_items` is also cheaper on a cold cache: its targets are resolved with
one bulk query instead of one query per related item. Behaviour is unchanged.

## Verify

```bash
pytest tests/service/test_service_cache.py -q          # new TestBatchRelatedItemsCaching
pytest -q                                              # full suite
ruff check . && ruff format --check . && mypy --strict .
```

## Migration note (LetrasTango — separate repo, after release)

`views/catalog.py` can now migrate `_related_items` / `_lyric_linked_entities` from the
per-relation-type `list_related_items` loop to a single
`list_related_items_for_sources` call for `direction="outgoing"` callers, dropping 2–5
cold-cache relation queries per detail page to 2.
