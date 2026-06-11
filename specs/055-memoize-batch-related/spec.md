# Feature Specification: Memoize Batched Related-Items Lookup

**Feature Branch**: `055-memoize-batch-related`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "Memoize list_related_items_for_sources in TaxomeshService and align it with the other read-cache methods" (source: `specs/PENDING-memoize-list-related-items-for-sources.md`, written from a LetrasTango performance review)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repeated batched lookups are served from the read cache (Priority: P1)

A consuming application (e.g. LetrasTango detail pages) asks the library for the related
items of a set of source items, grouped by relation type. When the same question is asked
again shortly afterwards (same source items, same relation-type filter, same error-handling
mode), the library answers from its short-lived read cache instead of querying the storage
backend again — exactly as every other read method in the service already does.

**Why this priority**: This is the core of the feature. Today the batched lookup is the
*only* read method without caching, which creates a perverse trade-off: callers that want
warm-cache performance must use the per-relation-type loop (N+1 on a cold cache), and
callers that want cold-cache performance must accept repeated storage queries on every
call. Fixing it removes the reason consumers avoid the recommended batched method.

**Independent Test**: With a counting storage backend, call the batched lookup twice with
identical arguments and assert the backend was queried only once.

**Acceptance Scenarios**:

1. **Given** a service with items and relations persisted, **When** the batched
   related-items lookup is called twice in a row with identical arguments within the cache
   lifetime, **Then** the storage backend is queried only once and both calls return the
   same result.
2. **Given** a warm cache for a given set of arguments, **When** the cache lifetime
   expires, **Then** the next call queries the storage backend again.
3. **Given** a warm cache, **When** the lookup is called with a *different* set of source
   items or a different relation-type filter, **Then** the storage backend is queried for
   the new combination (no false cache hits).

---

### User Story 2 - Equivalent calls share one cache entry (Priority: P2)

A caller passes the same source items and relation types in a different order, with
duplicates, or with different letter casing / surrounding whitespace in the relation type
names. The library recognises these calls as equivalent and serves them from the same
cache entry.

**Why this priority**: Without argument normalisation the cache would fragment into
near-duplicate entries (`["a", "b"]` vs `["b", "a"]`), silently halving its effectiveness
for callers that build filter lists dynamically.

**Independent Test**: With a counting storage backend, call the lookup with
`relation_types=["a", "b"]` and then `relation_types=["B", "a "]`; assert the backend was
queried only once.

**Acceptance Scenarios**:

1. **Given** a warm cache for relation types `("a", "b")`, **When** the lookup is called
   with the same types reordered, duplicated, re-cased, or padded with whitespace,
   **Then** the cached result is returned without querying the storage backend.
2. **Given** a warm cache for a set of source item IDs, **When** the same IDs are passed
   in a different order or with duplicates, **Then** the cached result is returned.
3. **Given** a warm cache for a call with no relation-type filter expressed as `None`,
   **When** the same call is made with an empty collection (also meaning "no filter"),
   **Then** the cached result is returned.

---

### User Story 3 - Writes and explicit cache clearing invalidate the cached results (Priority: P2)

After any write operation (creating/removing relations, items, etc.) or an explicit
cache-clear request, the next batched lookup reflects the new state of the data — stale
results are never served past an invalidation.

**Why this priority**: A read cache that survives writes returns wrong data, which is
worse than no cache. The library already guarantees this for every other read method;
the batched lookup must join that contract.

**Independent Test**: Warm the cache, clear all caches (or perform a write), and assert
the next identical call queries the storage backend again and reflects the change.

**Acceptance Scenarios**:

1. **Given** a warm cache for a batched lookup, **When** all caches are explicitly
   cleared, **Then** the next identical call re-queries the storage backend.
2. **Given** a warm cache for a batched lookup, **When** a new relation is created or an
   existing one removed, **Then** the next identical call reflects the updated relations.

---

### User Story 4 - Cold-cache single-item lookup avoids per-target queries (Priority: P3, optional)

A caller uses the single-item related-items lookup (`list_related_items`). On a cold
cache, the library resolves all target items through one bulk storage query instead of
one query per related item — but only if this does not complicate the code.

**Why this priority**: Explicitly optional in the source request. The per-target lookups
are already cached individually, so this only improves the cold-cache path.

**Independent Test**: With a counting storage backend and a cold cache, call
`list_related_items` for an item with several outgoing relations and assert target
resolution used a bulk query rather than one query per target.

**Acceptance Scenarios**:

1. **Given** an item with N outgoing relations and a cold cache, **When**
   `list_related_items` is called, **Then** the targets are resolved with a constant
   number of storage queries (not N), **And** the returned items and their order are
   unchanged from today's behaviour.

---

### Edge Cases

- Empty source collection: returns an empty result immediately (no storage query, no
  cache pollution) — unchanged from today.
- The two error-handling modes (`skip_on_error=True` / `False`) produce different
  behaviour for dangling relations, so they MUST NOT share a cache entry.
- Dangling relations (a relation pointing to a missing target): existing behaviour —
  skip-and-warn or raise — is preserved; a raised error MUST NOT poison the cache
  (a subsequent call re-queries).
- Cached results are shared object references, consistent with every other memoized read
  method in the service (callers must not mutate returned structures — existing
  library-wide convention).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The batched related-items lookup MUST serve repeated identical calls (same
  source items, same relation-type filter, same error-handling mode) from the service
  read cache within the standard cache lifetime, querying the storage backend only once.
- **FR-002**: Cache-key construction MUST treat as identical: source item collections
  that differ only in ordering or duplicates, and relation-type collections that differ
  only in ordering, duplicates, letter case, or surrounding whitespace. "No filter"
  expressed as `None` and as an empty collection MUST share one cache entry.
- **FR-003**: The error-handling mode (`skip_on_error`) MUST be part of the cache key,
  because it changes observable behaviour for dangling relations.
- **FR-004**: The cached entries MUST be invalidated by the existing global
  cache-clearing mechanism (explicit `clear_all_caches()` and every write operation that
  already triggers it), with no additional bookkeeping required of callers.
- **FR-005**: The lookup's observable behaviour — return shape, grouping, ordering of
  items within each relation type, normalisation of relation types, dangling-relation
  handling, and raised errors — MUST remain unchanged.
- **FR-006**: The public signature of the batched lookup MUST remain unchanged
  (collections of IDs and optional relation-type filter remain accepted as today).
- **FR-007**: Tests MUST prove: (a) two consecutive identical calls query the storage
  backend once; (b) different relation-type orderings share a cache entry; (c) explicit
  cache clearing forces a re-query — mirroring the existing memoization tests for sibling
  methods.
- **FR-008**: The changelog MUST be updated and the package version bumped following the
  repository's existing release conventions.
- **FR-009** *(optional — only if it does not complicate the code)*: The single-item
  related-items lookup SHOULD resolve its target items via one bulk storage query on a
  cold cache instead of one query per target, with identical results and ordering.

### Key Entities

- **Read cache entry**: An association between a normalised argument tuple (frozen set of
  source item IDs, frozen normalised relation-type filter, error-handling flag) and the
  grouped related-items result, with the service-standard time-to-live.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A second identical batched related-items call within the cache lifetime
  performs zero storage-backend queries (verified by a counting test backend).
- **SC-002**: Reordered / re-cased / duplicated argument variants of one logical query
  produce exactly one storage-backend query across all variants within the cache lifetime.
- **SC-003**: After a write or an explicit cache clear, the next batched call reflects
  the current persisted state (no stale results).
- **SC-004**: Consumers can replace a per-relation-type loop (2–5 storage queries per
  page on a cold cache, today's LetrasTango pattern) with one batched call costing at
  most 2 cold-cache queries and 0 warm-cache queries — removing the existing
  cold-vs-warm trade-off entirely.
- **SC-005**: All existing tests keep passing; quality gates (lint, format, strict type
  checking, coverage ≥ 80%) remain green.

## Assumptions

- The service-standard cache lifetime (the same TTL used by all sibling read methods) is
  the correct lifetime for this method too; no per-method TTL is introduced.
- Returning shared cached object references (rather than defensive copies) is acceptable
  because it matches the established behaviour of every other memoized read method.
- The follow-up migration of LetrasTango's `views/catalog.py` to the batched call is out
  of scope — it happens in that repository after this feature ships.
