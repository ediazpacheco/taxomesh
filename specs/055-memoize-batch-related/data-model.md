# Data Model: Memoize Batched Related-Items Lookup

**Feature**: 055-memoize-batch-related | **Date**: 2026-06-11

No domain model, port, or storage changes. The only "data" introduced is the in-process
cache entry shape used by the memoized private method.

## Cache entry (in-process, TTL-bound)

| Component | Type | Normalisation applied | Why |
|---|---|---|---|
| `self` | `TaxomeshService` | identity hash | one cache namespace per service instance (standard `memoize` behaviour) |
| `source_item_ids` | `frozenset[UUID]` | deduplicated, order-insensitive | FR-002 |
| `relation_types` | `tuple[str, ...] \| None` | each entry `strip().lower()`, deduplicated, sorted; `None`/empty → `None` | FR-002 |
| `skip_on_error` | `bool` | none — kept verbatim | FR-003 (behaviour-changing flag) |

**Value**: `dict[UUID, dict[str, list[Item]]]` — the exact return value of the method,
stored by reference (shared-object convention of all memoized read methods).

**Lifetime**: `DEFAULT_CACHE_TTL` (5 s, existing constant). Evicted early by
`clear_all_caches()`, which every write path already invokes (FR-004).

**Error behaviour**: exceptions are never stored; a failed call leaves no entry.

## State transitions

```
cold ──(call: repo queried, value stored)──► warm
warm ──(identical call within TTL)─────────► warm (0 repo queries)
warm ──(TTL elapsed)───────────────────────► cold
warm ──(any write / clear_all_caches())────► cold
```
