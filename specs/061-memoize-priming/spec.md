# Feature Specification: Memoize priming for batch reads

**Feature Branch**: `061-memoize-priming`
**Created**: 2026-09-10
**Status**: Draft
**Input**: User description: "Restore the cache priming that release 060 removed, so repeated reads stop paying for rows the previous read already fetched."

## Context

Release `0.1.0a50` (spec 060) replaced per-row resolution with a single batch read in
three methods: `list_items(category_id=…)`, `list_categories(parent_id=…)` and
`list_categories_by_item(item_id)`. That removed a genuine N+1 — one listing went from
5,220 reads to 3 — and it must not be reverted.

It also had an unintended second effect. The per-row calls it replaced went through the
**memoized** accessors `get_category` and `get_item`. The batch reads go straight to the
repository and bypass that layer. So resolving a row as a **result** no longer primes
the cache entry that a later call needs when that same row is passed as an
**argument** — and every such lookup that used to be a free cache hit is now a fresh
read.

The clearest case is a tree walk. `list_categories(parent_id=…)` begins by validating
its parent through `get_category`. Before 060, each child had already been resolved
through that same memoized accessor while being returned as a *result* of the previous
call, so validating it as a *parent* one step later cost nothing. After 060 nothing
primes it, and every validation is a miss.

Measured downstream on a 75-node, 3-level walk, with reads split by table:

| | link reads | category reads | total |
|---|---:|---:|---:|
| `0.1.0a49` | 75 | 76 | **151** |
| `0.1.0a50` as shipped | 75 | 102 | **177** |
| `0.1.0a50` with priming | 75 | 27 | **102** |

The batch read is not the cost — 27 batch resolves are far cheaper than 76 per-row
ones. The cost is the 75 validations that stopped being free. Priming does not merely
restore the old behaviour, it beats it: the batch saving is kept **and** the free
lookups come back.

This affects the consumer's two highest-traffic pages, which are 67.1% of its traffic,
and nothing absorbs it — the cache holds entries for five seconds in per-process
memory, and that origin serves roughly one request an hour, so the walk is cold on
essentially every render.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second read does not re-fetch what the first already returned (Priority: P1)

An application reads a set of rows through one of the three batch methods, then looks
up some of those same rows individually — or passes one of them as the argument to
another read. It should not pay storage again for rows the library just held in memory.

**Why this priority**: This is the regression and its remedy. Every other story here
exists to keep this one from breaking something else.

**Independent Test**: Perform a batch read, then look up a returned row individually,
and assert the second lookup costs zero storage reads.

**Acceptance Scenarios**:

1. **Given** a category with children, **When** the caller lists those children and
   then fetches one of them by id, **Then** the fetch costs no storage read.
2. **Given** a category holding items, **When** the caller lists those items and then
   fetches one of them by id, **Then** the fetch costs no storage read.
3. **Given** a multi-level tree, **When** the caller walks it node by node, **Then**
   the total read count is materially lower than both the current release and the one
   before it, and the walk's per-node validation costs nothing.
4. **Given** the cache has been cleared, **When** any of the three methods runs once,
   **Then** its cost is unchanged from the current release.

---

### User Story 2 - Release 060's gains and guarantees are untouched (Priority: P1)

The exact-constant read gates that release 060 shipped must pass with their constants
unmodified, and the N+1 it removed must stay removed.

**Why this priority**: Equal to P1. Those gates exist precisely so that later work
cannot silently undo 060, and this feature is exactly the kind of later work they were
written to catch.

**Independent Test**: Run the 060 gates and the full suite unmodified.

**Acceptance Scenarios**:

1. **Given** the 060 read-count gates, **When** priming is added, **Then** every gate
   passes with its constants unchanged and no test is edited to accommodate the change.
2. **Given** a single cold call to any of the three methods, **When** priming is added,
   **Then** it costs exactly what it costs today — priming writes to memory, it does
   not read from storage.

---

### User Story 3 - Cached values stay correct (Priority: P1)

A primed entry must be indistinguishable from one the accessor itself would have
stored: same value, same lifetime, same invalidation. A caller must never see a row
through the cache that it would not have seen through a direct read.

**Why this priority**: Equal to P1. A caching change that trades correctness for speed
is not acceptable at any speed, and this is the risk that has to be closed explicitly
rather than assumed.

**Independent Test**: Prime an entry, then mutate the underlying row, and assert the
next read reflects the mutation rather than the primed value.

**Acceptance Scenarios**:

1. **Given** a primed entry, **When** any write occurs, **Then** the entry is
   invalidated exactly as a normally cached entry would be.
2. **Given** a primed entry, **When** its lifetime expires, **Then** it is refreshed
   exactly as a normally cached entry would be.
3. **Given** a row that does not exist, **When** a batch read omits it, **Then** a
   later individual lookup still raises the same not-found error as today — priming
   must never manufacture a hit for an absent row.
4. **Given** a batch read that deliberately ignores the enabled filter, **When** its
   results are primed, **Then** a later individual lookup returns exactly what a direct
   read would return, with no filter leaking into the cached value.

---

### Edge Cases

- **A batch returns a very large number of rows.** The cache has no size limit and no
  eviction: entries are written and only removed when cleared wholesale by a write, so
  an expired entry that is never accessed again is never reclaimed. Priming a listing of
  several thousand rows inserts that many entries and holds them until the next write.
  Per FR-007 this is accepted rather than bounded; the requirement is that it be
  measured and documented, not avoided.
- **The same row appears in two batches.** Priming must be idempotent; the second write
  must not extend or shorten the entry's life in a way a direct read would not.
- **A row is deleted between the batch read and the later lookup.** A write clears the
  cache, so the later lookup must miss and behave exactly as it does today.
- **A batch read returns nothing.** Priming must be a no-op, not an error.
- **Unhashable arguments.** The cache already declines to store entries it cannot key;
  priming must decline in exactly the same circumstances rather than raising.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The caching utility MUST provide a way to insert a value for a given set
  of arguments, so that a later call with those arguments is served without reading
  storage.
- **FR-002**: The three batch-reading methods MUST prime the corresponding per-row
  accessor with the rows they already fetched.
- **FR-003**: A primed entry MUST be indistinguishable from a normally cached one in
  value, lifetime and invalidation. No new staleness window may be introduced.
- **FR-004**: Priming MUST NOT create an entry for a row that was not actually read, and
  MUST NOT suppress the not-found error a later lookup of an absent row raises today.
- **FR-005**: The cost of a single cold call to any of the three methods MUST be
  unchanged. Release 060's exact-constant gates MUST pass with their constants
  unmodified and no test edited.
- **FR-006**: The reduction MUST be asserted by tests that count storage reads across a
  repeated-access pattern — the case the 060 gates deliberately do not measure — so
  that removing priming later fails the build.
- **FR-007**: Priming MUST apply to all three methods with no size cap and no
  threshold. The memory cost is accepted as a deliberate tradeoff: a batch of any size
  is primed in full, and those entries are held until the next write clears the cache.
  Worst case on the largest measured corpus is the full item set — 8,352 rows — resident
  per process, and on a read-mostly deployment where writes are rare that is effectively
  for the life of the process. This is a decision, not an oversight, and MUST be
  documented as such for consumers under FR-009 so that an operator sizing a deployment
  can see it. Note that the cache is already unbounded today; priming increases how
  quickly it fills, not whether it is capped.
- **FR-008**: All four storage backends MUST be covered by tests: the JSON file backend,
  the YAML file backend, the Django backend, and the in-memory test fixture.
- **FR-009**: The behaviour MUST be documented for consumers, including its interaction
  with the cache lifetime and what a write invalidates.

### Non-Functional Requirements

- **NFR-001**: No new runtime dependency.
- **NFR-002**: No change to stored data and no migration.
- **NFR-003**: No change to any public method signature or return type.
- **NFR-004**: The existing quality gates MUST pass: linting, formatting, strict type
  checking, and the test suite at or above its coverage floor.

### Key Entities

- **Cached entry**: An existing concept. A stored result keyed by the arguments that
  produced it, with a timestamp governing its lifetime, cleared wholesale on any write.
  This feature adds a second way for one to come into existence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A 75-node, 3-level tree walk costs materially fewer storage reads than
  both the current release and the release before it — the measured target is 102,
  against 177 today and 151 before release 060.
- **SC-002**: Looking up a row individually immediately after it was returned by one of
  the three batch methods costs zero storage reads.
- **SC-003**: A single cold call to each of the three methods costs exactly what it
  costs today, verified by release 060's unmodified gates.
- **SC-004**: A write invalidates a primed entry exactly as it invalidates a normally
  cached one, verified per backend.
- **SC-005**: Removing priming fails the build.
- **SC-006**: Worst-case memory for the largest measured corpus is measured and
  recorded — priming a listing of several thousand rows, then reporting resident entry
  count and footprint — so the accepted cost in FR-007 is a known number rather than an
  estimate.

## Assumptions

- Release 060 stays exactly as it is. This feature restores a side effect its batch
  reads removed; it does not revert, re-tune or reshape them.
- The batch reads deliberately ignore the enabled filter so that a disabled row stays
  distinguishable from a deleted one. Priming inherits that unfiltered value, which
  matches what the per-row accessor returns, since that accessor applies no enabled
  filter either.
- Cache invalidation stays exactly as it is today: every write clears everything.
  Priming introduces no new invalidation path.
- Unbounded priming was chosen over the alternatives (categories only, a row threshold,
  or adding eviction to the cache) with the memory cost understood and accepted. Adding
  a size limit to the caching utility remains available later if a deployment reports
  pressure; it is deliberately not bundled here because it would touch all nine memoized
  reads and needs gates of its own.
- The tree-walk access pattern — a public call that resolves a whole tree level or
  subtree in a constant number of reads — remains worth exposing eventually, but is out
  of scope here and stops being urgent once priming lands, because it requires the
  consumer to migrate whereas this does not.

## Out of Scope

- Reverting or re-tuning any part of release 060.
- Any new public API, including a batched tree-level or subtree read.
- Changing the cache lifetime or the invalidate-everything-on-write policy.
- Any change to items, placements, tags or relations beyond priming the accessor for
  rows the three named methods already read.

## Dependencies

- Release `0.1.0a50` (spec 060), which introduced the batch reads this feature primes
  from, and whose regression gates constrain it.
