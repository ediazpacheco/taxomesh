# Feature Specification: Search Corpus Cache

**Feature Branch**: `040-search-corpus-cache`
**Created**: 2026-03-16
**Status**: Draft
**Input**: User description: "Improve generic search performance in taxomesh by reusing memoized service data for candidate loading and introducing internal pre-normalized search candidate caches for items and categories, with correct invalidation on all writes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Faster Repeated Searches Without Code Changes (Priority: P1)

A library consumer with a large catalog (thousands of items or categories) calls `search_items()` or `search_categories()` repeatedly. After the first call warms up the internal caches, subsequent calls to the same search service instance no longer reload all candidates from the repository or re-normalize every candidate's fields. The consumer makes no code changes to gain this benefit.

**Why this priority**: This is the core value of the feature. It directly reduces latency on repeated searches without any consumer-side changes, which is the primary stated goal.

**Independent Test**: Can be fully tested by calling `search_items()` twice on a populated service, verifying that the repository's load method is invoked fewer times on the second call than on the first.

**Acceptance Scenarios**:

1. **Given** a service with a populated item catalog, **When** `search_items()` is called twice with the same query, **Then** the repository is not queried for the full item list on the second call.
2. **Given** a service with a populated category catalog, **When** `search_categories()` is called twice, **Then** the candidate normalization is not repeated for the second call.
3. **Given** a cold service cache, **When** `search_items()` is called for the first time, **Then** results are correct and complete.

---

### User Story 2 - Cache Invalidation on Writes (Priority: P2)

A library consumer creates, updates, or deletes an item or category, then immediately performs a search. The search results reflect the write — no stale data is returned from the internal search cache.

**Why this priority**: Correctness is the library's stated first principle. Cache invalidation failures are silent correctness bugs. This must be validated before the optimization is considered safe for release.

**Independent Test**: Can be fully tested by creating an item, verifying it appears in subsequent search results; then deleting it and verifying it no longer appears.

**Acceptance Scenarios**:

1. **Given** a populated catalog and a warm search cache, **When** a new item is created, **Then** the next `search_items()` call returns the new item.
2. **Given** a populated catalog and a warm search cache, **When** an item is updated (name or slug changed), **Then** the next `search_items()` call reflects the updated fields.
3. **Given** a populated catalog and a warm search cache, **When** an item is deleted, **Then** the next `search_items()` call no longer returns it.
4. **Given** a populated catalog and a warm search cache, **When** a category is created, updated, or deleted, **Then** the next `search_categories()` call reflects the change.

---

### User Story 3 - Stable Public Search Behavior Across Backends (Priority: P3)

A library consumer using the Django, YAML, or JSON repository gets identical search result ordering and semantics before and after the optimization. Existing fuzzy and non-fuzzy search behavior is unaffected.

**Why this priority**: Backend and semantic parity is a correctness requirement for a multi-backend library. It must pass for the feature to ship, but it is not itself the primary optimization goal.

**Independent Test**: Can be fully tested by running the full existing search test suite against each supported repository with the optimization applied and verifying no regressions in result order or content.

**Acceptance Scenarios**:

1. **Given** any supported repository backend, **When** `search_items(query, fuzzy=True)` is called, **Then** results match the ranking returned before this feature was added.
2. **Given** any supported repository backend, **When** `search_items(query, fuzzy=False)` is called, **Then** results match the ranking returned before this feature was added.
3. **Given** a query of empty string or whitespace, **When** `search_items()` or `search_categories()` is called, **Then** an empty result is returned.

---

### User Story 4 - Category-Filtered and Recursive Search Still Works (Priority: P4)

A library consumer calls `search_items()` with a `category_id` filter or with recursive traversal. The optimization does not break filtered searches — only unrestricted (global) search reuses the full normalized corpus.

**Why this priority**: Filtered search has different candidate sets than global search. The cache must not be applied incorrectly to filtered searches, but this is a correctness constraint, not a new capability.

**Independent Test**: Can be fully tested by creating items in specific categories and verifying that filtered `search_items()` still returns only items in the correct category subtree.

**Acceptance Scenarios**:

1. **Given** items in multiple categories, **When** `search_items()` is called with a `category_id`, **Then** only items within that category (or subtree, if recursive) are returned.
2. **Given** a warm global item corpus cache, **When** `search_items()` is called with a `category_id` filter, **Then** the result is still correctly filtered regardless of the cached global corpus.

---

### Edge Cases

- What happens when a write occurs while a search is in progress (concurrent access is not a concern for the current single-threaded service, but invalidation must happen before the next read)?
- What happens when the normalized corpus is empty (no items or categories in the repository)?
- What happens when an item is added to or removed from a category (placement change) — should this invalidate the item corpus for filtered searches?
- What happens when the same service instance is reused across test cases that share in-process state?
- **Thread safety**: The corpus cache (`_item_corpus`, `_category_corpus`) is **not thread-safe**. `TaxomeshService` is designed for single-threaded use. Consumers sharing a service instance across threads without external synchronization may observe a spurious corpus rebuild (a benign extra normalization pass) but not data corruption or stale results. The documented contract: one `TaxomeshService` instance per thread, or external locking if sharing is required. Thread-safe corpus access is explicitly out of scope for this feature.

## Requirements *(mandatory)*

### Functional Requirements

**Candidate Loading**

- **FR-001**: `search_items()` MUST NOT call the repository's item list method directly when `category_id` is `None`; it MUST route through the service's memoized item load path instead.
- **FR-002**: `search_categories()` MUST reuse cached category loads from the service's memoized load path where semantically equivalent.
- **FR-003**: The implementation MUST preserve existing behavior for `search_items()` calls with a non-`None` `category_id`, including recursive subtree traversal.
- **FR-004**: Search MUST function correctly when all service caches are cold (first call after service initialization).

**Normalized Candidate Caching**

- **FR-005**: The library MUST maintain an internal cache of pre-normalized search candidates for items.
- **FR-006**: The library MUST maintain an internal cache of pre-normalized search candidates for categories.
- **FR-007**: Cached candidates MUST include only generic, search-relevant fields (e.g., normalized name, normalized slug, normalized external ID where applicable).
- **FR-008**: Cached candidates MUST NOT include application-specific fields, metadata keys, or derived domain values.
- **FR-009**: Cached candidates MUST be invalidated whenever a write operation can affect search-visible fields for that entity type.
- **FR-010**: Cache invalidation MUST occur on: `create_item`, `update_item`, `delete_item`, `create_category`, `update_category`, `delete_category`.

**Search Execution**

- **FR-011**: The public signatures of `search_items()` and `search_categories()` MUST remain unchanged.
- **FR-012**: Default ranking semantics (exact match boost, prefix boost, fuzzy fallback) MUST remain materially consistent with the pre-optimization behavior.
- **FR-013**: A staged scoring pipeline (deterministic boosts first, fuzzy only for remaining candidates) MAY be introduced, provided result ordering remains consistent with documented semantics.
- **FR-014**: Exact, prefix, and substring matching MUST continue to work with accent-insensitive normalization.
- **FR-015**: Fuzzy search MUST remain opt-in and MUST be controlled by the existing `fuzzy` parameter.
- **FR-016**: Empty or whitespace-only queries MUST return empty results.

**Backend and Model Neutrality**

- **FR-017**: The optimization MUST NOT introduce any Django-specific models, ORM queries, or Django-only APIs into the service layer.
- **FR-018**: The optimization MUST NOT assume SQL indexes, Redis, HTTP caches, or any external infrastructure.
- **FR-019**: The optimization MUST work correctly with Django, YAML, and JSON repositories.
- **FR-020**: The repository protocol MUST NOT be changed as part of this feature.

**Documentation and Quality**

- **FR-021**: README search documentation MUST be updated if any externally observable behavior changes.
- **FR-022**: New internal caching behavior MUST be covered by automated tests.
- **FR-023**: Tests MUST NOT use wall-clock timing assertions (e.g., "must run in under X ms").
- **FR-024**: Public docstrings for `search_items()` and `search_categories()` MUST remain accurate and generic.
- **FR-025**: All code changes MUST pass `ruff check`, `ruff format --check`, `mypy --strict`, and `pytest --cov=taxomesh --cov-fail-under=80`.
- **FR-026**: `TaxomeshService.get_debug()` MUST include two new keys: `item_corpus_size` (integer count of pre-normalized item candidates when the corpus is warm, `None` when cold) and `category_corpus_size` (integer count of pre-normalized category candidates when the corpus is warm, `None` when cold).

### Key Entities

- **SearchCandidate** (internal): An immutable representation of a single searchable entity (Item or Category) with pre-normalized field values. Not part of the public API. Contains the original domain object plus its normalized name, slug, and external ID strings.
- **Search Corpus Cache** (internal): A collection of `SearchCandidate` instances for all items or all categories. Owned exclusively by the service layer. Invalidated on all writes to the relevant entity type. Not exposed to consumers or repositories.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a warm cache, `search_items()` does not invoke the repository's bulk item load method; this is verifiable by counting repository calls across repeated searches.
- **SC-002**: On a warm cache, `search_categories()` does not invoke the repository's bulk category load method; this is verifiable by counting repository calls across repeated searches.
- **SC-003**: After any write operation (create, update, or delete) on an item or category, the next search call returns results consistent with the updated state, with zero stale entries.
- **SC-004**: All existing search tests pass without modification across Django, YAML, and JSON repository fixtures.
- **SC-005**: No public method signature or result type changes are introduced; existing consumer code requires no updates to benefit from the optimization.
- **SC-006**: The internal cache contains only generic entity fields; no domain-specific or application-specific fields appear in any cache entry.
- **SC-007**: `get_debug()` returns `item_corpus_size` as a non-negative integer after the first unfiltered `search_items()` call, and `None` before any such call or after an item write that invalidates the corpus.

## Clarifications

### Session 2026-03-16

- Q: Should internal corpus cache state be surfaced in `get_debug()`? → A: Yes — add corpus sizes to the existing `get_debug()` output (`item_corpus_size`, `category_corpus_size`; `None` when cold).
- Q: Should the spec formally document the thread-safety posture of the corpus cache? → A: Yes — document explicitly as not thread-safe; consumers must not share a `TaxomeshService` instance across threads without external synchronization.

## Assumptions

- The `TaxomeshService` instance is the correct and sole owner of the search corpus cache. Consumers are expected to hold a single service instance per logical catalog context.
- The existing memoization utility (`taxomesh/utils/memoize.py`) may be reused, extended, or bypassed in favor of an explicit `None`-sentinel cache pattern, depending on which approach is simpler and more correct. This decision is deferred to the planning phase.
- Category search receives the same normalized-corpus treatment as item search in the same implementation cycle, rather than being deferred to a follow-up.
- Staged fuzzy scoring is treated as an optional optimization to evaluate during planning; it is not a required deliverable for this feature.
- Item placement changes (adding or removing an item from a category) do not invalidate the global item corpus cache, since placement does not affect search-visible entity fields. Filtered search correctness is handled by loading the filtered candidate set directly rather than subsetting the global corpus.

## Open Questions

Both questions below were resolved during the planning phase (see `research.md`):

1. ~~Should the normalized candidate corpus use the existing TTL-based memoization utility, or a dedicated explicit cache?~~ **Resolved**: Dedicated `None`-sentinel cache owned by `TaxomeshService` (see research.md R-002).
2. ~~Is staged fuzzy scoring worth the added complexity?~~ **Resolved**: Deferred to a future cycle; not a deliverable for this feature (see research.md R-007).
