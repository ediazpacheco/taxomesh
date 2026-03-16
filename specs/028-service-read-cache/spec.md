# Feature Specification: Service Read Cache Completeness

**Feature Branch**: `028-service-read-cache`
**Created**: 2026-03-08
**Status**: Draft

## Overview

The taxomesh service layer exposes read operations for fetching data by external
identifier and for querying item-to-item relations. These operations are called
on every admin page load by external consuming apps and are vulnerable to
cache-miss amplification: a sudden burst of requests (accidental or malicious)
would bypass the in-memory cache and hit the underlying data store directly for
every call.

The service already applies a short-lived TTL cache to eight read methods. Four
remaining read methods have been left unprotected. Two write methods that modify
relation data are also missing the mandatory cache-invalidation call, meaning
stale data could be served after a successful write.

This feature closes both gaps: it extends cache coverage to the four unprotected
read methods and fixes the two write methods that omit cache invalidation.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — External-ID Lookups Are Cache-Protected (Priority: P1)

An external application resolves a taxomesh item or category by the external
identifier of one of its own records (e.g. a content UUID). This lookup is
performed on every admin detail-page load. Without caching, each page load
triggers a direct data-store query regardless of how recently the same lookup
was performed.

**Why this priority**: Highest-frequency call path in all known consumer apps.
Cache coverage here has the most impact on load protection.

**Independent Test**: Call the external-ID item lookup and the external-ID
category lookup repeatedly with the same argument within the TTL window; verify
that the data store is queried only once per unique argument set.

**Acceptance Scenarios**:

1. **Given** an item exists with a known external ID, **When** the lookup is
   called twice in quick succession with the same ID, **Then** the second call
   returns identical results without hitting the data store.
2. **Given** an item's external ID is changed via a write operation, **When**
   the lookup is performed afterward, **Then** the updated value is returned
   (cache was invalidated on write).
3. **Given** an unknown external ID, **When** the lookup is called, **Then** an
   empty list is returned and that empty result is cached for the TTL window.

---

### User Story 2 — Item Relation Queries Are Cache-Protected (Priority: P2)

An admin graph view or API consumer lists the outgoing or incoming relations of
an item. Without caching, repeated renders of the same graph segment hit the
data store on every request.

**Why this priority**: Relation queries appear in graph rendering and admin
inlines. High-repetition but lower frequency than external-ID lookups.

**Independent Test**: Call the relation list and the related-items list
repeatedly for the same item within the TTL window; verify a single data-store
query per unique argument combination.

**Acceptance Scenarios**:

1. **Given** an item has outgoing relations, **When** the relation list is
   called twice with the same arguments, **Then** the second call is served from
   cache.
2. **Given** a relation is created between two items, **When** relation queries
   are performed afterward, **Then** the new relation appears (cache was
   invalidated on write).
3. **Given** a relation is removed, **When** relation queries are performed
   afterward, **Then** the deleted relation no longer appears (cache was
   invalidated on delete).
4. **Given** two calls with different direction values, **When** the results
   are compared, **Then** each direction is cached independently.

---

### User Story 3 — Write Operations Always Invalidate the Cache (Priority: P1)

Any operation that creates or removes a relation must immediately invalidate all
cached read results so that subsequent reads return fresh data.

**Why this priority**: Data correctness. A write that does not invalidate the
cache silently serves stale results — this is a correctness bug, not a
performance gap.

**Independent Test**: Create a relation, immediately read relations for the same
item, and verify the new relation appears. Remove a relation, immediately read,
and verify it is gone.

**Acceptance Scenarios**:

1. **Given** no relation exists between two items, **When** a relation is
   created and the relation list is queried, **Then** the new relation is
   returned.
2. **Given** a relation exists, **When** it is removed and the relation list is
   queried, **Then** the relation is absent.

---

### Edge Cases

- What happens when a lookup is called with an external ID that matches no
  records? The empty-list result must be cached and returned consistently for
  the TTL window.
- What happens when arguments include types that cannot be used as cache keys?
  The cache must fall through gracefully and call the underlying data store
  without error. **Note**: all four newly decorated methods accept only `UUID`,
  `str`, and `str | None` arguments — all hashable by definition. FR-009 is
  satisfied structurally for these methods; no dedicated test is required.
- What happens when direction and relation_type are provided in different
  combinations? Each unique combination of arguments must produce an independent
  cache entry.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST return cached results for external-ID item
  lookups when called with the same argument within the cache TTL window.
- **FR-002**: The service MUST return cached results for external-ID category
  lookups when called with the same argument within the cache TTL window.
- **FR-003**: The service MUST return cached results for relation list queries
  when called with the same item, type, and direction within the TTL window.
- **FR-004**: The service MUST return cached results for related-item queries
  when called with the same item, type, and direction within the TTL window.
- **FR-005**: Creating a relation MUST invalidate all service-level read caches
  immediately upon successful completion.
- **FR-006**: Removing a relation MUST invalidate all service-level read caches
  immediately upon successful completion.
- **FR-007**: Cached results MUST expire automatically after the established
  TTL without any manual intervention.
- **FR-008**: Cache behaviour MUST be transparent to callers — public method
  signatures and return types MUST remain unchanged.
- **FR-009**: When arguments are not suitable as cache keys, the cache MUST be
  bypassed silently; the call MUST still return correct results.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Repeated identical read calls within the TTL window produce at
  most one data-store query per unique argument set, regardless of call
  frequency.
- **SC-002**: After any write operation that creates or removes a relation, the
  very next read call returns data consistent with the write — zero stale-read
  window after invalidation.
- **SC-003**: All existing automated tests continue to pass with no changes to
  test assertions, confirming that cache transparency is maintained.
- **SC-004**: Each newly cached method and each write-invalidation fix is
  covered by at least one automated test that directly verifies the caching or
  invalidation behaviour.

---

## Assumptions

- The existing cache TTL (5 seconds) is appropriate for the newly protected
  methods; no per-method TTL tuning is in scope.
- Cache scope is in-process (single Python interpreter). Distributed or
  shared-memory caching is out of scope.
- The existing cache fallback for non-hashable arguments is sufficient; no
  changes to the cache utility itself are needed.
- No changes to public API surface (signatures, return types, exceptions) are
  required or permitted.
