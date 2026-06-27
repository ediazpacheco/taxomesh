# Contracts: Direction-Aware Batched Related-Items Traversal

## 1. Service method (generalized public API)

```python
def list_related_items_for_sources(
    self,
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
    skip_on_error: bool = True,
    direction: Literal["outgoing", "incoming", "both"] = "outgoing",
) -> dict[UUID, dict[str, list[Item]]]:
```

**Contract:**

- `direction` is the only added parameter; it is keyword-only and defaults to
  `"outgoing"`. With the default, behavior is byte-for-byte identical to the
  pre-feature method (same result, grouping, ordering, errors, cache keys).
- `source_item_ids` are the **queried** item ids, interpreted per `direction`:
  matched on the source side (`outgoing`), the target side (`incoming`), or either
  (`both`).
- Return: `dict[queried_id: {relation_type: [related Item, ...]}]`. Queried ids
  with no matching links are absent.
- `relation_types`: optional allow-list; normalized case-insensitively
  (`strip().lower()`, deduped). `None`/`[]` = no filter.
- `skip_on_error=True` (default): dangling/disabled related items are skipped and
  a WARNING is logged. `skip_on_error=False`: raises
  `TaxomeshItemNotFoundError` on the first such link.
- Only `enabled=True` items are materialized as related items.
- Empty `source_item_ids` → `{}` with **zero** repository calls.
- Result is memoized (`DEFAULT_CACHE_TTL`); `direction` is part of the cache key;
  writes and `clear_all_caches()` invalidate.

**Repository-call bound (anti-N+1):**

| direction | repository calls | independent of #ids? |
|---|---|---|
| `outgoing` | 2 (one link query + bulk items) | yes |
| `incoming` | 2 (one link query + bulk items) | yes |
| `both` | 2 (one combined source-OR-target link query + bulk items) | yes |

## 2. Repository Protocol method (unified, replaces the prior two)

```python
def list_item_relation_links_for_items(
    self,
    item_ids: Collection[UUID],
    *,
    direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]:
    """Return relation links for many items in a single query, by direction."""
```

**Contract:**

- `outgoing`: links whose `source_item_id` is in `item_ids`, ordered
  `(source_item_id, relation_type, sort_index, target_item_id)`.
- `incoming`: links whose `target_item_id` is in `item_ids`, ordered
  `(target_item_id, relation_type, sort_index, source_item_id)`.
- `both`: links where `item_ids` contains the source **or** the target (a single
  combined query — `Q(source__in) | Q(target__in)` on Django), ordered
  `(sort_index, source_item_id, target_item_id)`.
- `relation_types`: optional allow-list (post-normalization equality). `None`/`[]`
  = no filter.
- Empty `item_ids` → `[]` (no storage access).
- Must be implemented by `JsonRepository`, `YAMLRepository`,
  `DjangoRepository`, and the in-memory test repository.

## 3. Compatibility notes

- Service layer: `direction` is additive with a default; `direction="outgoing"`
  is byte-for-byte identical to prior behavior.
- Repository layer (breaking, accepted): the prior
  `list_item_relation_links_for_sources` (shipped `0.1.0a44`) is removed and
  replaced by the unified `list_item_relation_links_for_items`.
- Django: a composite index `taxomesh_rl_tgt_type_sort_idx` mirrors the existing
  outgoing index so the incoming/both `ORDER BY` is index-backed.
