# Feature Specification: Search Performance for Autocomplete

**Feature Branch**: `039-search-perf`
**Created**: 2026-03-16
**Status**: Clarified
**Input**: Optimize `taxomesh` search performance for autocomplete-style queries

## Clarifications

### Session 2026-03-16

- Q: Should FR-005 normalization scope be per-call only (SearchCandidate built fresh each call) or cross-call (cached for service lifetime)? → A: Per-call only — cross-call caching is out of scope for this feature.
- Q: Should `NormalizationCache` be removed from Key Entities or kept as deferred? → A: Removed — only `SearchCandidate` is implemented; no cross-call cache in scope.
- Q: How should SC-004 (normalization work is bounded) be verified? → A: Structural unit test — assert each candidate field is normalized exactly once per call by inspecting `SearchCandidate` fields; no timing benchmarks.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast Autocomplete Results (Priority: P1)

A downstream application calls `search_items()` or `search_categories()` on every keystroke as a user types into an autocomplete field. With a large catalog, the current per-keystroke search is too slow, causing visible lag. After this feature, the same query against the same catalog returns the same top results faster, with no change to the calling code.

**Why this priority**: This is the primary motivation for the feature. Every autocomplete request is affected, and the slowdown is user-visible.

**Independent Test**: Can be fully tested by running `search_items(query, limit=5)` against a large item catalog and confirming the returned results are identical to the pre-optimization results, but measured faster.

**Acceptance Scenarios**:

1. **Given** a catalog of N items, **When** `search_items("appl", limit=5)` is called, **Then** the 5 highest-scoring matches are returned in descending score order (ties broken by normalized name), identical to the results before optimization.
2. **Given** a catalog with typos in query ("aple"), **When** `search_items("aple", limit=5, fuzzy=True)` is called, **Then** fuzzy-matched items still appear in results.
3. **Given** `search_items()` called with `limit=5` on a 1000-item catalog, **Then** the call completes without performing unnecessary work proportional to the full catalog size beyond what is required to find the top 5.

---

### User Story 2 - Repeated Normalization Within a Call Eliminated (Priority: P2)

As a user types character by character ("a", "ap", "app", "appl"), each call to `search_items()` or `search_categories()` previously normalized every candidate's name twice (once in `_score_and_rank`, once inside `score_candidate`) and normalized slug and external_id from scratch too. After this feature, a `SearchCandidate` is built once per call with all fields pre-normalized, eliminating the double-normalization within each call. Cross-call caching is out of scope for this feature.

**Why this priority**: Normalization is CPU-bound Unicode work. Eliminating it for repeated queries is the second-highest leverage point after top-k selection.

**Independent Test**: Can be tested by confirming that within a single `search_items()` call, each candidate's name, slug, and external_id are each normalized exactly once (via `SearchCandidate`), and that results are correct.

**Acceptance Scenarios**:

1. **Given** a catalog of items, **When** `search_items()` is called, **Then** each candidate's fields are normalized exactly once per call (not twice per candidate as previously).
2. **Given** a candidate whose name contains diacritics ("Ñoño"), **When** it appears in search results, **Then** its normalization is consistent with the existing `SearchEngine.normalize()` behavior.

---

### User Story 3 - Result Ordering Is Deterministic and Unchanged (Priority: P3)

Callers that rely on stable ordering (e.g., test suites, display logic) must see the same ranked list before and after the optimization.

**Why this priority**: Correctness constraint. Any optimization that changes ordering would be a regression.

**Independent Test**: Can be fully tested by comparing the output of the optimized path against the legacy full-sort path on the same inputs, verifying identical ordering for all result positions up to `limit`.

**Acceptance Scenarios**:

1. **Given** multiple candidates with equal scores, **When** `search_items()` is called, **Then** ties are broken by normalized name in ascending alphabetical order, same as before.
2. **Given** a query that matches 50 candidates when `limit=10`, **When** the top-k path is used, **Then** the returned 10 items are the same 10 that a full sort would have selected.

---

### Edge Cases

- What happens when `limit` equals or exceeds the total number of matching candidates? No top-k shortcut should alter results — return all matches.
- What happens when the catalog is empty? Return an empty list immediately, as before.
- What happens when all candidates have the same score? Tie-breaking by normalized name must still apply and be stable.
- What happens when items are added or removed between two search calls? Because `SearchCandidate` objects are rebuilt fresh on every call, there is no stale cache — the next call naturally reflects the current catalog state.
- What happens when `fuzzy=False`? Top-k and normalization improvements apply equally; no fuzzy-specific logic must be bypassed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST return the same top-`limit` results (in the same order) as the current implementation for all valid inputs to `search_items()` and `search_categories()`.
- **FR-002**: The library MUST preserve exact match, prefix match, word-prefix match, substring match, and fuzzy typo-tolerant match behaviors.
- **FR-003**: The library MUST preserve deterministic ordering: descending score, then normalized name ascending for ties.
- **FR-004**: When `limit` is smaller than the total number of scoring candidates, the library MUST select the top-`limit` results without necessarily performing a full sort of all candidates.
- **FR-005**: Within a single search call, the library MUST normalize each candidate's name, slug, and external_id exactly once (via `SearchCandidate`) rather than re-normalizing them at multiple points in the call stack. Cross-call normalization caching is out of scope for this feature.
- **FR-006**: The public signatures of `search_items()` and `search_categories()` MUST remain backward-compatible; no existing keyword argument may be removed or renamed.
- **FR-007**: Any new optional parameter added to the public API MUST have a default value that preserves existing behavior when omitted.
- **FR-008**: The optimization MUST apply to both `search_items()` and `search_categories()` equally.
- **FR-009**: Because `SearchCandidate` objects are built fresh on every call (no cross-call cache), no cache invalidation logic is required for this feature. If a catalog mutation occurs between two calls, the next call will re-build `SearchCandidate` objects from the latest state automatically.

### Key Entities

- **SearchCandidate**: An internal representation pairing a domain object (Item or Category) with its pre-normalized name, slug, and external_id fields. Built fresh on every search call. Not exposed in the public API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing search-related tests pass without modification after the optimization is applied.
- **SC-002**: A test suite covering ranking stability confirms that the top-k optimized path returns results identical (same items, same order) to the full-sort path for at least 50 distinct query/catalog combinations (interpreted as: a catalog of 50 items exercised against ≥10 distinct query strings, yielding 50 combinations).
- **SC-003**: A test confirms that fuzzy typo-tolerant queries (≥1 character substitution) still surface the expected candidates after optimization.
- **SC-004**: A structural unit test asserts that each candidate's name, slug, and external_id are each normalized exactly once within a single `_score_and_rank` call — verified by inspecting `SearchCandidate` field values rather than by timing. No benchmarks or CI-timing assertions required.
- **SC-005**: The public API surface of `search_items()` and `search_categories()` remains unchanged: no new required parameters, no removed parameters, no changed return types.

## Assumptions

- `SearchCandidate` objects are built fresh on every search call (no cross-call cache). This means no cache invalidation logic is needed and catalog mutations between calls are handled automatically.
- The catalog is assumed to be read-frequently and write-infrequently, making per-call `SearchCandidate` construction amortizable over the scoring work that follows.
- `rapidfuzz` library version already in use (`>=3.0`) is sufficient; no dependency changes are needed.
- The `DEFAULT_ITEM_EXTERNAL_ID` sentinel for empty external IDs is preserved and handled consistently in normalized candidate fields.
- Documentation updates include the public API changelog and README search section.
