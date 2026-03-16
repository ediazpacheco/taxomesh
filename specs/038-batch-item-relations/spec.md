# Feature Specification: Batch Item Relation Lookup

**Feature Branch**: `038-batch-item-relations`
**Created**: 2026-03-16
**Status**: Draft
**Input**: User description: Add batch support for reading outgoing item relation links across multiple source items to avoid N+1 query patterns.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk Relation Lookup for Index Building (Priority: P1)

An application that needs to build a search index or aggregated view over thousands of items wants to retrieve all outgoing relations for a given set of source items in a single call, rather than issuing one request per item.

**Why this priority**: Core of the feature. Without this, there is no batch capability. All other stories depend on it.

**Independent Test**: Can be fully tested by calling the batch API with a list of source item IDs and verifying that the returned structure groups results correctly by source ID and relation type.

**Acceptance Scenarios**:

1. **Given** a set of N source item IDs with outgoing relations, **When** the batch API is called with those IDs, **Then** the result contains exactly one top-level key per source item that has at least one outgoing relation, and each key maps to a dict of `relation_type → [items]`.
2. **Given** source item IDs some of which have no outgoing relations, **When** the batch API is called, **Then** only source items with at least one outgoing relation appear as keys in the result (no empty entries).
3. **Given** an empty list of source item IDs, **When** the batch API is called, **Then** the result is an empty dict and no storage is queried.

---

### User Story 2 - Filtering Batch Lookup by Relation Type (Priority: P2)

An application already knows which relation type(s) it cares about (e.g., `music_by`) and wants to retrieve only those relation types for many source items at once.

**Why this priority**: Reduces payload size and storage work for consumers with narrowly scoped needs.

**Independent Test**: Can be fully tested by calling the batch API with a specific `relation_types` filter and verifying that only matching relation types appear in the response.

**Acceptance Scenarios**:

1. **Given** source items that each have multiple relation types, **When** the batch API is called with `relation_types=["music_by"]`, **Then** the result contains only `music_by` entries; other relation types are absent.
2. **Given** `relation_types=None` or `relation_types` not provided, **When** the batch API is called, **Then** all outgoing relation types are returned without filtering.
3. **Given** `relation_types=[]` (empty list), **When** the batch API is called, **Then** no filtering is applied and all relation types are returned (same as `None`).

---

### User Story 3 - Consistent Ordering Across Adapters (Priority: P3)

A consumer generating deterministic output (e.g., serialized index snapshots) needs the items within each relation type list to arrive in a stable, predictable order regardless of which storage adapter is in use.

**Why this priority**: Correctness and reproducibility; important but the feature has value even if tested only against one adapter.

**Independent Test**: Can be tested by creating links with explicit sort indices and verifying the returned lists respect sort index order, with tie-breaking on target item ID.

**Acceptance Scenarios**:

1. **Given** multiple links sharing the same (source, relation_type) with different sort index values, **When** the batch API is called, **Then** the items in the list are ordered ascending by sort index.
2. **Given** two links with identical sort index, **When** the batch API is called, **Then** tie-breaking by target item ID ensures a stable, deterministic order.
3. **Given** results from any supported adapter (JSON, YAML, Django), **When** the same data is queried, **Then** the order of items is identical across adapters.

---

### User Story 4 - Backward Compatibility (Priority: P1)

Existing callers that use the per-item `list_related_items()` and `list_item_relation_links()` APIs must continue to work without any changes.

**Why this priority**: Breaking existing consumers is a regression; this must be guaranteed alongside the new capability.

**Independent Test**: Existing test suites for the per-item APIs must pass without modification.

**Acceptance Scenarios**:

1. **Given** existing code calling `list_related_items(item_id, ...)`, **When** the feature is deployed, **Then** the call returns the same result as before.
2. **Given** existing code calling `list_item_relation_links(item_id, ...)`, **When** the feature is deployed, **Then** the call returns the same result as before.

---

### Edge Cases

- What happens when all provided source item IDs have no outgoing relations? → Return empty dict.
- What happens when a target item referenced by a relation link no longer exists? → The service MUST raise `TaxomeshItemNotFoundError` for the missing target ID (fail-fast; consistent with Constitution Principle V and the behavior of `get_item()`).
- What happens when `source_item_ids` contains duplicates? → Deduplicate before querying; each source ID appears at most once as a key in the result.
- What happens when `relation_types` contains a type that matches no links? → That type simply does not appear in the result; no error is raised.
- What is the expected behavior for very large `source_item_ids` lists? → No hard limit defined; the adapter handles it using a single batch query (Django) or in-memory filter (JSON/YAML).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository layer MUST expose a batch method that accepts a collection of source item IDs and returns all their outgoing relation links in a single operation.
- **FR-002**: The batch repository method MUST support optional filtering by one or more relation type strings; if the filter is absent or empty, all relation types are returned.
- **FR-003**: The batch repository method MUST return results ordered deterministically by: source item ID, relation type, sort index, then target item ID.
- **FR-004**: The service layer MUST expose a batch method that accepts a collection of source item IDs and returns a nested structure grouped first by source ID, then by relation type, mapping to an ordered list of resolved items.
- **FR-005**: The service batch method MUST resolve target items in bulk (not one-by-one per link) to minimize storage round-trips. If any `target_item_id` referenced by a link does not exist in storage, the method MUST raise `TaxomeshItemNotFoundError`.
- **FR-006**: The service batch method MUST omit source item IDs that have no matching outgoing relations from the result keys.
- **FR-007**: The service batch method MUST return an empty result immediately when called with an empty source ID collection, without accessing storage.
- **FR-008**: The existing `list_item_relation_links()` repository method and `list_related_items()` service method MUST remain unchanged and fully functional.
- **FR-009**: All three storage adapters (Django ORM, JSON, YAML) MUST implement the batch repository method with identical observable contracts.
- **FR-010**: The Django adapter MUST implement the batch query using a single ORM query with a set-based filter on source item IDs rather than iterating per source.

### Key Entities

- **ItemRelationLink**: A directed link from a source item to a target item, tagged with a relation type and a sort index. The batch method returns collections of these.
- **Item**: The domain object resolved from a target item ID. The service layer materializes Items for all unique target IDs found across all links before grouping.
- **BatchRelationResult**: The structured return value keyed by source item ID, then by relation type, then an ordered list of resolved target Items.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An application that previously issued N storage queries (one per source item) can retrieve the same relational data with a single call, reducing query count from N to 1 for any N ≥ 1.
- **SC-002**: The batch result for any set of source IDs is logically equivalent to the union of individual `list_related_items()` calls for the same IDs, relation types, and direction.
- **SC-003**: All existing tests for single-item relation APIs continue to pass without modification after the feature is merged.
- **SC-004**: The batch API correctly handles boundary inputs — empty source list, all-unmatched relation types, source IDs with no relations — without errors or unexpected output.
- **SC-005**: The ordering of items within each relation type list is identical whether produced by the JSON, YAML, or Django adapter, given the same underlying data.

## Clarifications

### Session 2026-03-16

- Q: What happens when a target item referenced by a relation link no longer exists — raise an error or skip silently? → A: Raise `TaxomeshItemNotFoundError` (fail-fast; no silent omission).

## Assumptions

- Only **outgoing** links (where the queried item is the source) are in scope for this feature. Incoming or bidirectional batch queries are explicitly out of scope.
- Target item resolution uses an existing bulk-fetch capability in the service layer or repository, or iterates over unique target IDs once; the same item is never fetched more than once per call.
- Duplicate IDs in `source_item_ids` are silently deduplicated; the result contains at most one entry per unique source ID.
- No pagination is added at this stage; the full result is returned in one call.
- The `contrib.api` HTTP layer is out of scope for this feature; that is a separate extension if needed.
