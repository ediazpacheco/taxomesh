# Feature Specification: Direction-Aware Batched Related-Items Traversal

**Feature Branch**: `056-batch-related-direction`  
**Created**: 2026-06-27  
**Status**: Draft  
**Input**: User description: "Add the missing batched, direction-symmetric counterpart to the existing batched outgoing traversal `list_related_items_for_sources`. Generalize it with a `direction` parameter so the same primitive resolves outgoing, incoming, and both-direction related items for many items at once, eliminating the N+1 pattern of looping single-item calls."

## Context

The service exposes one batched relation-traversal primitive,
`list_related_items_for_sources`, which resolves the **outgoing** related items
of many items in a bounded number of repository calls (one batched link query +
one bulk item lookup), explicitly to eliminate the N+1 pattern of calling the
single-item `list_related_items` in a loop.

There is **no batched counterpart for the incoming direction**. Code that needs
the incoming relations of many items today must loop over single-item calls
(`list_related_items` / `list_item_relations` with `direction="incoming"`),
reintroducing exactly the N+1 the batched method was built to remove. This is an
incompleteness in the public API, not a deliberate boundary: the single-item
methods are already direction-aware (`outgoing` / `incoming` / `both`), but the
batched method is hard-wired to outgoing.

This feature closes the gap by generalizing the batched method with a
`direction` parameter, defaulting to `outgoing` so existing behavior and callers
are unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Batched incoming relations without N+1 (Priority: P1)

A developer needs the **incoming** related items for a large set of items (for
example, "for each of these items, which items point at it?"). Today they must
loop the single-item incoming call, producing one query pair per item. They want
a single batched call that resolves them all in a bounded number of repository
calls, grouped exactly like the outgoing batched result.

**Why this priority**: This is the core gap. It removes the N+1 the outgoing
batched method already eliminated for its own direction, and is the primary
reason the feature exists.

**Independent Test**: Call the batched method with `direction="incoming"` over
many item ids and assert (a) the grouped result is correct and (b) the number of
repository calls is constant — exactly two — and does not grow with the number
of input items.

**Acceptance Scenarios**:

1. **Given** several items each with incoming relation links of one or more
   relation types, **When** the batched method is called with those item ids and
   `direction="incoming"`, **Then** it returns a dict keyed by queried item id,
   then by relation type, to the list of related (source-side) items.
2. **Given** the same query, **When** repository calls are counted, **Then**
   exactly two repository calls are made (one batched incoming-link query + one
   bulk item lookup), regardless of how many item ids were passed.
3. **Given** an item among the inputs that has no incoming links, **When** the
   batched method is called, **Then** that item is absent from the result (not
   present as an empty inner dict).

### User Story 2 - Default outgoing behavior is preserved (Priority: P1)

Existing callers of `list_related_items_for_sources` (and their tests) must
continue to behave identically with no code changes.

**Why this priority**: Backward compatibility is non-negotiable; the method is
already shipped and in use.

**Independent Test**: Call the method exactly as before (no `direction`
argument) and assert the result, grouping, ordering, caching, and error behavior
are unchanged from the current outgoing implementation.

**Acceptance Scenarios**:

1. **Given** items with outgoing links, **When** the method is called without a
   `direction` argument, **Then** the result is identical to the pre-feature
   outgoing behavior (default `direction="outgoing"`).
2. **Given** the existing outgoing test suite, **When** it runs against the
   generalized method, **Then** every test passes unchanged.

### User Story 3 - Both-direction batched relations (Priority: P2)

A developer needs, for many items at once, all related items regardless of
relation direction (the union of outgoing and incoming), grouped the same way.

**Why this priority**: Completes parity with the single-item method's
`direction="both"` option. Useful but secondary to closing the incoming gap.

**Independent Test**: Call the batched method with `direction="both"` over items
that have both incoming and outgoing links and assert the related items from both
sides are merged under the queried item id and relation type, with a bounded,
input-size-independent repository call count.

**Acceptance Scenarios**:

1. **Given** an item with both outgoing links (to targets) and incoming links
   (from sources) of a relation type, **When** the method is called with
   `direction="both"`, **Then** both the target-side and source-side related
   items appear under that item id and relation type.
2. **Given** a both-direction query over many items, **When** repository calls
   are counted, **Then** the count is bounded and constant (two calls: one
   combined `source OR target` link query, one bulk item lookup) and does not
   grow with the number of input items.

### Edge Cases

- **Empty input**: an empty collection of item ids returns an empty dict
  immediately, with zero repository calls, for every direction.
- **No matching links**: items with no links in the requested direction are
  absent from the result.
- **Dangling / disabled related item** with `skip_on_error=True` (default): the
  offending link is skipped and a warning is logged (same message shape and
  resilience as the outgoing path), in every direction.
- **Dangling / disabled related item** with `skip_on_error=False`: the same
  `TaxomeshItemNotFoundError` is raised, in every direction.
- **Relation-type casing/whitespace**: `relation_types` are normalized
  (stripped, lower-cased, deduplicated) so casing and ordering variants are
  equivalent, in every direction.
- **Duplicate / reordered input ids**: deduplicated and order-independent, in
  every direction.
- **Caching**: results are served from the service read cache; `direction` is
  part of the cache key so different directions are independent entries, and any
  write (or cache clear) invalidates them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The batched related-items method MUST accept a `direction`
  parameter with the values `outgoing`, `incoming`, and `both`, mirroring the
  direction values already accepted by the single-item `list_related_items` /
  `list_item_relations` methods.
- **FR-002**: The `direction` parameter MUST default to `outgoing`, and the
  method's observable behavior for the default MUST be identical to the current
  (pre-feature) outgoing behavior, including return shape, grouping, ordering,
  error handling, and caching.
- **FR-003**: With `direction="incoming"`, the method MUST return, for each
  queried item id, the related items reached via **incoming** links (the
  source-side items), grouped by relation type, in the same dict shape as the
  outgoing result (`{queried item id: {relation type: [related items]}}`).
- **FR-004**: With `direction="both"`, the method MUST return, for each queried
  item id, the union of the outgoing-side and incoming-side related items,
  grouped by relation type under that item id.
- **FR-005**: The incoming path MUST resolve in exactly **two** repository calls
  (one batched link query keyed by the queried item ids + one bulk item lookup),
  and this count MUST NOT grow with the number of input item ids. It MUST NOT
  degrade to a per-item query loop.
- **FR-006**: The both-direction path MUST resolve in exactly **two** repository
  calls (one combined `source OR target` batched link query + one bulk item
  lookup), constant regardless of input size. It MUST NOT issue a separate query
  per direction and MUST NOT degrade to a per-item query loop.
- **FR-007**: A single direction-aware batched link query MUST exist at the
  repository layer —
  `list_item_relation_links_for_items(item_ids, *, direction, relation_types)` —
  returning a flat, deterministically ordered list of links for `outgoing`,
  `incoming`, and `both` (the latter via one combined source-or-target query),
  with an optional relation-type allow-list and empty-input-returns-empty. It MUST
  be implemented by every repository adapter and replaces the prior
  outgoing-only batched query. On the Django backend, the incoming and both
  paths MUST be index-backed (a composite index mirroring the outgoing one) so
  the `ORDER BY` is an index scan rather than a filesort.
- **FR-008**: All conventions of the existing outgoing batched method MUST be
  preserved identically across all directions: case-insensitive relation-type
  normalization; `skip_on_error` semantics (default skip-and-warn; `False`
  raises the same missing-item error type); enabled-state resolution when
  materializing related items; deterministic ordering of related items within
  each group; absence of items that have no matching links; empty-input fast
  path; and read-cache participation.
- **FR-009**: The feature MUST be fully domain-agnostic — no assumptions about
  specific relation-type values, item kinds, or use cases.
- **FR-010**: The method docstring MUST be updated in the existing house style to
  document the `direction` parameter, the per-direction repository-call bounds,
  and the N+1 rationale, mirroring the existing batched docstring.
- **FR-011**: Documentation (CHANGELOG and any README/API references describing
  the batched method) MUST be updated, and the package version MUST be bumped
  following the established convention.

### Key Entities *(include if feature involves data)*

- **Relation link**: a directed edge between a source item and a target item,
  carrying a relation type and a sort index. The traversal direction selects
  whether the queried item is matched on the source side (outgoing), the target
  side (incoming), or either (both).
- **Related-items result**: a grouped mapping from each queried item id to a
  mapping from relation type to the ordered list of related items resolved for
  that item in the requested direction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A batched incoming related-items call over N items performs a
  constant number of storage-backend queries (two) that does not increase as N
  grows — verified by a counting test backend.
- **SC-002**: A batched both-direction call over N items performs a constant
  number of storage-backend queries (two) that does not increase as N grows —
  verified by a counting test backend.
- **SC-003**: 100% of the existing outgoing batched-method tests pass unchanged
  after the generalization (default behavior preserved).
- **SC-004**: The incoming and both-direction paths pass behavioral tests
  mirroring the existing outgoing suite — grouping correctness, multiple relation
  types, relation-type filtering and case-insensitivity, `skip_on_error` vs
  raising, empty input, and items with no matching links — across all repository
  backends covered by the existing parametrized suite.
- **SC-005**: A developer needing the incoming (or both-direction) relations of
  many items can do so with a single call, with no loop and no per-item query
  amplification.
