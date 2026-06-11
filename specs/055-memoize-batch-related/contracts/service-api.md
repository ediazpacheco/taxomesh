# Service API Contract: Memoize Batched Related-Items Lookup

**Feature**: 055-memoize-batch-related | **Date**: 2026-06-11

## `TaxomeshService.list_related_items_for_sources` — signature UNCHANGED

```python
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
    skip_on_error: bool = True,
) -> dict[UUID, dict[str, list[Item]]]: ...
```

Existing contract preserved verbatim: return shape `{source_id: {relation_type:
[Item, ...]}}`, items ordered `(sort_index ASC, target_item_id ASC)`, sources without
matching links absent, relation types normalised to lower-case, dangling links skipped
with a WARNING (`skip_on_error=True`) or raising `TaxomeshItemNotFoundError`
(`skip_on_error=False`), empty input → `{}` with no repository call.

### New caching guarantees

| # | Guarantee |
|---|---|
| C1 | Repeated calls with equivalent arguments within `DEFAULT_CACHE_TTL` perform **zero** repository queries after the first. |
| C2 | Equivalence ignores: ordering/duplicates of `source_item_ids`; ordering/duplicates/case/surrounding-whitespace of `relation_types`; `None` vs empty collection for `relation_types`. |
| C3 | Calls differing in `skip_on_error` are **distinct** cache entries. |
| C4 | `clear_all_caches()` and every write operation invalidate the cache. |
| C5 | A raised `TaxomeshItemNotFoundError` is never cached; the next call re-queries. |
| C6 | Cached results are shared object references — callers must not mutate them (library-wide memoized-read convention). |

### New private member (not part of the public API)

```python
@memoize(DEFAULT_CACHE_TTL)
def _fetch_related_items_for_sources(
    self,
    source_item_ids: frozenset[UUID],
    *,
    relation_types: tuple[str, ...] | None,
    skip_on_error: bool,
) -> dict[UUID, dict[str, list[Item]]]: ...
```

## `TaxomeshService.list_related_items` — signature and behaviour UNCHANGED (FR-009)

```python
@memoize(DEFAULT_CACHE_TTL)
def list_related_items(
    self,
    item_id: UUID,
    *,
    relation_type: str | None = None,
    direction: Literal["outgoing", "incoming"] = "outgoing",
) -> list[Item]: ...
```

Internal change only: on a cold cache, target items are resolved through one
`repository.get_items_by_ids(ids, enabled=None)` call instead of one
`get_item` call per link. Observable behaviour is identical:

- result order = link order (duplicates preserved);
- disabled items still returned (bulk call uses `enabled=None`);
- a missing target still raises `TaxomeshItemNotFoundError(f"Item not found: {id}")`,
  for the first missing ID in link order.

## Repository port — UNCHANGED

Uses existing `list_item_relation_links_for_sources` and `get_items_by_ids` port
methods. No adapter (Json/YAML/Django/InMemory) changes.
