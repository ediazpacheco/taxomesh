# Phase 1 Data Model: Batch resolution for the placement read paths

**Feature**: `060-batch-placement-reads` | **Date**: 2026-09-09

## Domain model changes

**None.** No Pydantic model gains, loses, or changes a field. No migration.
`Category`, `Item`, `CategoryParentLink` and `ItemParentLink` are untouched, and
`taxomesh/domain/` is not modified by this feature.

What changes is how the application layer *assembles* results from records it
already reads, plus two additions to the read surface of the port.

## Entities referenced

### `CategoryParentLink` — read with a new filter

| Field | Type | Role in this feature |
| --- | --- | --- |
| `category_id` | `UUID` | The child. Becomes the key set passed to the batch category resolve. |
| `parent_category_id` | `UUID` | The new filter column (FR-009). |
| `sort_index` | `int` | Sibling order. May be negative, may tie, may be the default assigned at placement time (feature 034). |

Ordering contract, unchanged: `(parent_category_id ASC, sort_index ASC, category_id ASC)`.
The contract must continue to hold **under the new filter** (FR-010).

### `ItemParentLink` — read as today

| Field | Type | Role in this feature |
| --- | --- | --- |
| `item_id` | `UUID` | Key set for the batch item resolve; also an existing filter. |
| `category_id` | `UUID` | Key set for the batch category resolve; also an existing filter. |
| `sort_index` | `int` | Placement order, same characteristics as above. |

Ordering contract, unchanged: `(category_id ASC, sort_index ASC, item_id ASC)`.

### Batch resolve result — a mapping, not a sequence

The shape the whole feature turns on:

```
dict[UUID, Category]     # new
dict[UUID, Item]         # existing, unchanged
```

Three properties define it, and each drives a requirement:

1. **Unordered.** Order comes from the link list, never from the map. The
   ordered link list is iterated and each id looked up — this is why FR-015 is
   satisfiable at all, and why R1's re-sort must survive.
2. **Partial.** A requested id with no row is simply absent. There is no
   sentinel and no error. FR-012 is what assigns meaning to an absent key —
   without a stated policy the loop cannot be written.
3. **Deduplicated by construction.** A `dict` cannot hold the same key twice, so
   duplicate input ids collapse. Callers pass a `set` (FR-002 — the port does
   not normalise).

## Invariants the rewrite must preserve

| Invariant | Where it is asserted |
| --- | --- |
| Result order equals link order after the stable `sort_index` re-sort | FR-015, R1 |
| A disabled endpoint is filtered, never treated as missing | FR-011, R2 |
| An absent endpoint raises, with the existing message text | FR-012, R6 |
| A non-existent category/item raises before any link read | FR-013 |
| An empty link set returns `[]` without a batch call | FR-016 |
| Round-trips do not scale with result size | FR-014, FR-019 |

## State transitions

None. Every path in scope is read-only; no write path, cache-invalidation
trigger, or lifecycle rule changes. The TTL read cache continues to wrap all
three methods (`@memoize(DEFAULT_CACHE_TTL)` at `service.py:294`, `:503`,
`:531`) and continues to be invalidated by the existing write paths (FR-018).
