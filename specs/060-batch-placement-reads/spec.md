# Feature Specification: Batch resolution for the placement read paths

**Feature Branch**: `060-batch-placement-reads`
**Created**: 2026-09-09
**Status**: Draft
**Input**: User description: "Kill the N+1 in the three placement read paths (backlog finding F1, P0 — docs/backlog/findings.md § F. Scale limits in the read and write paths)."

## Context

Three of the most-used read methods on the public facade resolve one stored row
per result row:

| Method | Offending line |
| --- | --- |
| `list_items(category_id=…)` | `taxomesh/application/service.py:526` — `items = [self.get_item(lnk.item_id) for lnk in links]` |
| `list_categories(parent_id=…)` | `taxomesh/application/service.py:346` — `cats = [self.get_category(lnk.category_id) for lnk in links]` |
| `list_categories_by_item(item_id)` | `taxomesh/application/service.py:562` — same shape |

Measured on the Django adapter against an 8,352-item corpus
(`docs/backlog/measurements.md § F1`, counted with `CaptureQueriesContext`):

```
list_items(category_id=<5,218 placements>)  [cold]   705.4 ms   5220 queries
list_items()  (whole corpus, larger result)          265.8 ms      1 query
```

The unfiltered call over a *larger* result set costs one query and 2.7× less
time — the signature of the defect. The measurement is on local SQLite and is
therefore the optimistic case; on a network-attached database each of those
5,220 queries carries a round-trip.

The equivalent work was already done for the relation traversal in `a44`–`a46`
using the existing batch item primitive, and was never carried across to the
placement traversal. There is no batch *category* primitive in the port at all,
which is why the two category-resolving paths had nothing to reach for.

`list_categories(parent_id=…)` carries a second, independent defect: it loads
**every** category-parent link in the store and filters by parent in memory
(`service.py:343-345`), because the port's link listing accepts no filter
(`taxomesh/ports/repository.py:225`). The other two paths already push their
filter down. Removing only the per-row resolution would leave this path at one
query that scans the whole link table — a constant query count that is not
evidence of a scale-clean path.

## Clarifications

### Session 2026-09-09

- Q: A placement link whose endpoint row is missing — raise, or skip and warn?
  → A: Raise, preserving current behaviour exactly (FR-012). The batch
  retrieval is therefore requested unfiltered by enabled state so that a
  disabled endpoint is never mistaken for a missing one (FR-011). Defining a
  cascade policy stays with finding E2.
- Q: Is the unfiltered category-link scan in the children path in scope?
  → A: Yes — the port's category-link listing gains a parent filter, in all
  four backends (FR-009, FR-010, SC-003).
- Q: Which vehicle proves adapter parity, given no conformance suite exists?
  → A: The existing parametrised service fixture plus adapter-level tests.
  Building a conformance suite stays out of scope.
- Q: Oversized batch input — how many of the operations that pass an unbounded
  identifier list to a single query are repaired here?
  → A: None. The new operation mirrors the existing one exactly and does not
  split (FR-006). Old SQLite builds, whose limit is 999, are not supported; the
  modern limit is high enough for the corpus sizes in evidence. Exceeding it
  must still surface as the library's repository error, not a raw backend
  exception (FR-006a, SC-007), and the observed limit is recorded rather than
  worked around (FR-006b). All the affected operations are written up together
  as a backlog item.
- Q: The call-shape spy subclasses the in-memory repository, so it cannot run
  on the other three backends. Rework it, or narrow the requirement?
  → A: Narrow FR-020. The service layer has no backend-conditional branching,
  so its sequence of port calls is invariant across adapters and the spy proves
  the same thing whichever backend sits underneath. Per-backend evidence stays
  with the round-trip counts (FR-019) and the parity assertions (FR-008).
- Q: Should the new parent filter accept a single parent or a collection?
  → A: A collection (FR-009). Categories form a DAG, so expanding a whole
  frontier of parents in one read is a real traversal primitive, and the
  collection form is the direct analogue of the filter the item-link listing
  already offers. The reverse child→parents direction is deferred (FR-009a).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Listing the contents of a category stays affordable as it grows (Priority: P1)

An application renders "the contents of this category" — a catalog page, a
navigation panel, an admin change list. Today the cost of that screen grows
linearly in the number of placements: a category with 5,218 items costs 5,220
separate trips to storage. The consumer expects the cost of retrieving a
category's contents to be governed by the size of the result transferred, not
by a per-row round-trip.

**Why this priority**: This is the single most-called read path in the library
and the one with the largest measured penalty. It is the finding's headline
number and the reason F1 is rated P0.

**Independent Test**: Populate one category with a large number of placements,
retrieve its contents, and count storage round-trips. Shipping only this story
delivers the headline fix and a durable regression gate for it.

**Acceptance Scenarios**:

1. **Given** a category holding N placements, **When** its contents are listed,
   **Then** the number of storage round-trips is the same for N=5 and N=200.
2. **Given** the same category, **When** its contents are listed, **Then** the
   returned items, their order, and their content are identical to what the
   current implementation returns.
3. **Given** a category identifier that does not exist, **When** its contents
   are listed, **Then** a category-not-found error is raised, exactly as today.

---

### User Story 2 - Navigating the category tree stays affordable as it widens (Priority: P1)

An application renders the children of a category — a tree control, a
breadcrumb drill-down, a picker. Today this costs one round-trip per child
*and* reads every category-parent link in the store regardless of how many
children the parent has. The consumer expects the cost to be governed by the
number of children actually returned.

**Why this priority**: Same defect class and same call frequency as Story 1,
and it carries the additional full-scan defect that the batch rewrite alone
does not remove. Tree navigation is on the critical path of the admin and of
any hierarchical UI.

**Independent Test**: Build a parent with many children alongside unrelated
categories elsewhere in the tree, list the children, and confirm both that the
round-trip count is constant and that unrelated links are never read.

**Acceptance Scenarios**:

1. **Given** a parent with N children, **When** its children are listed,
   **Then** the number of storage round-trips is the same for N=5 and N=200.
2. **Given** a store containing many categories under other parents, **When**
   one parent's children are listed, **Then** links belonging to other parents
   are not retrieved.
3. **Given** a leaf category, **When** its children are listed, **Then** an
   empty result is returned and no batch resolution is attempted.

---

### User Story 3 - Reading an item's placements stays affordable (Priority: P2)

An application shows which categories an item belongs to — an item detail page,
a breadcrumb trail, an export. The same per-row resolution applies.

**Why this priority**: Same defect, but the fan-out is bounded in practice by
how many categories a single item is placed in, which is typically far smaller
than a category's item count. Lower measured impact, identical fix.

**Independent Test**: Place one item in many categories, read its categories,
and count round-trips.

**Acceptance Scenarios**:

1. **Given** an item placed in N categories, **When** its categories are
   listed, **Then** the number of storage round-trips is the same for N=5 and
   N=200.
2. **Given** an item identifier that does not exist, **When** its categories
   are listed, **Then** an item-not-found error is raised, exactly as today.

---

### User Story 4 - A regression to per-row resolution fails the build (Priority: P1)

A maintainer changes one of these read paths, or adds a fourth path of the same
shape, and reintroduces per-row resolution. The build must fail on the
regression itself, not merely run slower and go unnoticed.

**Why this priority**: The backlog states the gate is the deliverable and the
code change is the easy half. The existing single-query guards never covered
these three methods, which is why a regression gate that already existed did
not catch the defect. Without this story the fix has no protection.

**Independent Test**: Revert any one of the three methods to per-row
resolution; the suite must fail.

**Acceptance Scenarios**:

1. **Given** an instrumented storage layer, **When** any of the three methods
   runs, **Then** the single-row retrieval operations are invoked zero times.
2. **Given** the same instrumentation, **When** any of the three methods runs,
   **Then** the batch retrieval operation is invoked exactly once, with the
   complete set of identifiers.
3. **Given** the round-trip gates, **When** they run, **Then** they measure a
   cold path and cannot be satisfied by a warm cache.
4. **Given** the four supported backends, **When** the behaviour and
   round-trip assertions run, **Then** they hold on all of them, not only on
   the database-backed one. The call-shape spy is the exception and runs on one
   backend, for the reason given in FR-020.

### Edge Cases

- A placement link whose endpoint row no longer exists (reachable on the file
  backends, where deletion does not cascade): the read raises the same
  not-found error it raises today. See FR-012.
- An endpoint row that exists but is disabled while the caller filters for
  enabled rows: it is filtered out, never mistaken for a missing row. See
  FR-011.
- Placements with equal `sort_index`, negative `sort_index`, or the default
  `sort_index` assigned by feature 034: ordering is unchanged from today,
  including the tie-break.
- A category with no placements, an item in no categories, a category with no
  children: an empty result, with no batch resolution attempted.
- The same identifier appearing more than once in a batch request.
- A batch request larger than the underlying store's limit on a single query.
  See FR-006.
- A caller passing an empty filter collection, which means "match nothing", not
  "no filter" — the rule already documented for the item-link listing.
- An endpoint row deleted concurrently, between the link retrieval and the
  batch retrieval: the read raises, exactly as it does today when the row is
  deleted between the link retrieval and the per-row retrieval. The race
  window narrows but does not change character, and these reads are not
  wrapped in a snapshot — doing so would be new behaviour, not preserved
  behaviour.

## Requirements *(mandatory)*

### Functional Requirements

#### Batch category retrieval

- **FR-001**: The repository port MUST expose a batch category retrieval
  operation that takes a collection of category identifiers and returns a
  mapping from identifier to category, mirroring the existing batch item
  retrieval operation exactly.
- **FR-002**: The input MUST be treated as pre-normalised — the caller has
  already removed duplicates and the adapter MUST NOT normalise further.
- **FR-003**: Identifiers with no matching row MUST be silently absent from the
  returned mapping; the operation MUST NOT raise for them.
- **FR-004**: An empty input collection MUST return an empty mapping without
  reaching storage.
- **FR-005**: A storage failure MUST surface as the library's repository error
  type.
- **FR-006**: The operation MUST pass the input collection to the store as a
  single request and MUST NOT split it internally. The store's own per-query
  limit is therefore the library's limit, matching what the existing batch item
  retrieval does today.
- **FR-006a**: Where that limit is exceeded, the failure MUST surface as the
  library's repository error type per FR-005, never as a raw backend exception.
- **FR-006b**: The test suite MUST prove that a collection past the *legacy*
  parameter ceiling (999, the pre-3.32 SQLite value) is sent as exactly one
  unsplit request and returns every matching row — establishing that nothing
  truncates and nothing splits. The *modern* ceiling is documented rather than
  exercised: building a corpus of that size in CI would cost far more than the
  risk it retires, and the failure mode past it is covered by FR-006a. No
  existing batch operation is modified by this feature.
- **FR-007**: The operation MUST accept an enabled filter with three states —
  enabled only, disabled only, or unfiltered — defaulting to unfiltered.
- **FR-008**: All four backends — the JSON file backend, the YAML file backend,
  the database-backed backend, and the in-memory test backend — MUST implement
  the operation with identical observable semantics.

#### Filtered category-link retrieval

- **FR-009**: The port's category-parent link listing MUST accept a filter
  naming a *collection* of parents, so that the children of one parent — or of
  a whole set of parents — can be retrieved without reading links belonging to
  other parents. The collection form mirrors the filter the item-link listing
  already offers on its parent side.
- **FR-009a**: The reverse direction — filtering by the child category to
  retrieve its parents — is NOT added by this feature. It is a legitimate query
  in a multi-parent graph, but no path in scope issues it.
- **FR-010**: The documented ordering contract of that listing MUST hold under
  the new filter, and an empty filter collection MUST return an empty result
  rather than being treated as "no filter" — matching the rule already
  documented for the item-link listing.

#### The three read paths

- **FR-011**: Each of the three read paths MUST resolve its endpoints with
  exactly one batch retrieval, and MUST request that retrieval unfiltered by
  enabled state, applying the caller's enabled filter to the resolved rows
  afterwards. This keeps a disabled endpoint distinguishable from a missing
  one.
- **FR-012**: When a placement link's endpoint row is absent from the batch
  result, the read MUST raise the same not-found error the current
  implementation raises, carrying the same message text naming the missing
  identifier. Behaviour is preserved exactly; no row is silently skipped. The
  message wording is part of what is preserved, not incidental: at least one
  existing test matches on it.
- **FR-013**: The existing check that the requested category or item exists
  MUST be retained, and MUST continue to raise a not-found error before any
  link retrieval.
- **FR-014**: The number of storage round-trips performed by each of the three
  paths MUST be constant with respect to the number of rows returned, as that
  term is defined in A-001.
- **FR-015**: Result ordering MUST be unchanged from the current
  implementation, including ties, negative values, duplicate sort values, and
  the default sort value assigned at placement time.
- **FR-016**: An empty link set MUST short-circuit to an empty result without
  attempting a batch retrieval.
- **FR-017**: The public signatures, return types, and raised error types of
  the three methods MUST NOT change.
- **FR-018**: Existing cache behaviour MUST be unchanged — results remain
  cached for their configured lifetime and remain invalidated on write.

#### Regression protection

- **FR-019**: The suite MUST assert an exact, constant storage round-trip count
  for each of the three paths, parametrised over at least two result sizes, and
  MUST assert those counts are identical across sizes.
- **FR-020**: The suite MUST assert, through a recording spy at the repository
  boundary, that batch retrieval is invoked exactly once with the complete
  identifier set, and that single-row retrieval is invoked **at most once** per
  call — that one being the existence check required by FR-013 — and never once
  per returned row. This gate runs on a single backend by design: the service
  layer contains no backend-conditional branching, so the sequence of port
  calls it makes is invariant across adapters, and running the same code path
  four times would prove nothing further. Per-backend evidence is FR-019's
  round-trip counts and FR-008's parity assertions, not this spy.
  The exact figure differs per path and MUST be asserted as such: resolving a
  category's items performs zero single-row *item* retrievals; reading an
  item's categories performs zero single-row *category* retrievals; listing a
  category's children performs exactly one single-row category retrieval,
  because there the existence check and the resolution concern the same entity
  type. A blanket "zero" assertion is wrong for that third path and MUST NOT be
  written.
- **FR-021**: The round-trip assertions MUST be measured on a cold path and
  MUST NOT be satisfiable by a warm cache.

### Key Entities

- **Category placement link**: the record binding an item to a category,
  carrying the sort position that determines result order.
- **Category parent link**: the record binding a category to its parent,
  carrying the sort position that determines sibling order.
- **Batch retrieval result**: a mapping from requested identifier to the row
  found for it; requested identifiers with no row are absent from the mapping,
  which is what makes the absent-key policy in FR-012 a required decision
  rather than an implementation detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Retrieving the contents of a category costs the same number of
  storage round-trips whether the category holds 5 placements or 200.
- **SC-002**: The same holds for listing a category's children and for listing
  an item's categories.
- **SC-003**: Listing a category's children reads only the links belonging to
  that parent; adding unrelated categories elsewhere in the tree does not
  change what is read.
- **SC-004**: Reverting any one of the three paths to per-row resolution causes
  the automated suite to fail. The regression lives in the service layer, which
  is backend-invariant, so it is caught by the call-shape spy and the
  round-trip counts rather than by a per-backend fence — consistent with
  FR-020. Which test catches each reversion is verified explicitly, not
  assumed.
- **SC-005**: Every existing behavioural assertion covering the three methods
  continues to pass unmodified — the change is invisible to callers in
  ordering, filtering, error type, and error timing.
- **SC-006**: The batch category retrieval behaves identically across all four
  backends under the same assertions.
- **SC-007**: An input collection large enough to exceed a store's per-query
  limit fails as the library's own repository error on every backend that
  imposes such a limit — never as a raw backend exception leaking through the
  port.

## Assumptions

- **A-001**: "Storage round-trip" is counted per query on the database-backed
  adapter and per port-method invocation on the file and in-memory adapters.
  The file adapters load a whole document per call, so a constant *invocation*
  count is the meaningful gate there; this feature does not change how those
  adapters read their file.
- **A-002**: The measured baseline in `docs/backlog/measurements.md § F1` is
  the reference point. This feature does not re-run the full benchmark; it
  asserts operation counts, which are deterministic, rather than wall-clock
  times, which are not.
- **A-003**: The default enabled filter values of the three public methods are
  unchanged. Only where the filter is *applied* changes, never its outcome.
- **A-004**: No storage migration is required. The feature adds read
  operations to the port and changes how the application layer composes
  existing reads.
- **A-005**: The supported SQLite floor is a modern build, whose single-query
  parameter limit is an order of magnitude above the 999 of pre-3.32 builds and
  comfortably above the largest placement count in evidence (5,218). Older
  builds are explicitly not supported, which is what makes FR-006's no-split
  rule safe.

## Out of Scope

- Pagination and counting (finding F2).
- The whole-graph read path (finding F3).
- Cascade-on-delete (finding E2). This spec preserves current behaviour on
  dangling links per FR-012 and does not define a cascade policy; E2 remains
  free to change that policy for all paths at once later.
- Bulk write paths (finding F4) and search pushdown (finding H1).
- Building a general repository conformance suite. Adapter parity for the two
  new port operations is asserted through the existing parametrised fixture and
  adapter-level tests instead.
- Splitting oversized batch requests, in the new operations or the existing
  ones. Four shipped operations pass an unbounded identifier list to a single
  query — bulk item retrieval by identifier, bulk item and category retrieval
  by external identifier, and bulk relation retrieval — and the two operations
  this feature adds do the same. None is repaired here; all are recorded
  together as a backlog item.
- Any change to the relation traversal paths, which were already batched in
  `a44`–`a46`.

## Dependencies

- The batch item retrieval operation already in the port, which the new batch
  category retrieval mirrors and which the item-resolving path will use.
- The cross-backend parametrised service fixture, which already covers all four
  backends and is the vehicle for the parity assertions required by FR-008 and
  SC-006, together with adapter-level tests for the two new port operations.
  No repository conformance suite exists in the project; building one is a
  separate action-plan item and is out of scope here.
- The existing recording-repository pattern used by the no-full-scan tests,
  which is the vehicle for the call-shape gate. It is built by subclassing the
  in-memory test repository, so it exercises one backend; FR-020 explains why
  that is sufficient for what this gate asserts.
