# Phase 1 Data Model: Direction-Aware Batched Related-Items Traversal

No new domain models or persisted fields are introduced. This feature is a
read-side traversal generalization. The relevant existing entities and the
shape of the in-memory result are documented below.

## Existing entities (unchanged)

### ItemRelationLink (`taxomesh/domain/models/item_relation_link.py`)

A directed edge in the item property graph. Fields:

| Field | Type | Notes |
|---|---|---|
| `source_item_id` | `UUID` | edge tail |
| `target_item_id` | `UUID` | edge head |
| `relation_type` | `str` (`max_length=RELATION_TYPE_MAX_LENGTH`) | normalized `strip().lower()` on construction; non-empty |
| `sort_index` | `int` (default `0`) | ordering within a `(item, relation_type)` group |
| `metadata` | `dict[str, Any]` | free-form |

Invariant: `source_item_id != target_item_id` (self-relations rejected). This
guarantees a single link contributes to exactly one side, so the `both`
traversal needs no cross-side de-duplication.

### Item (`taxomesh/domain/models/item.py`)

Materialized by the bulk lookup `get_items_by_ids(ids, enabled=True)`. Carries an
`enabled` flag; disabled items are excluded from materialization, so a link to a
disabled item is treated as dangling.

## Traversal semantics by direction

For a queried item id `q` and a matched link `L`:

All three directions use one unified repository query
`list_item_relation_links_for_items(ids, *, direction, relation_types)`:

| direction | query | matched when | group key | related item id |
|---|---|---|---|---|
| `outgoing` | `..._for_items({q,...}, direction="outgoing")` | `L.source_item_id == q` | `L.source_item_id` | `L.target_item_id` |
| `incoming` | `..._for_items({q,...}, direction="incoming")` | `L.target_item_id == q` | `L.target_item_id` | `L.source_item_id` |
| `both` | `..._for_items({q,...}, direction="both")` (one combined `source OR target` query) | either endpoint == `q` | the endpoint equal to `q` | the other endpoint |

## Result shape (in-memory, not persisted)

```text
dict[UUID, dict[str, list[Item]]]
  └ queried item id
        └ relation_type (normalized)
              └ ordered list of related Item objects
```

Ordering within each `relation_type` list:

- `outgoing`: `(sort_index ASC, target_item_id ASC)`
- `incoming`: `(sort_index ASC, source_item_id ASC)`
- `both`: outgoing-derived items first, then incoming-derived items, each half in
  its own order above.

Items with no matching links in the requested direction are **absent** from the
outer dict (no empty inner dicts).
