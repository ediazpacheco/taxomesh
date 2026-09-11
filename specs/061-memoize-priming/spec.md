# Feature Specification: Memoize priming for batch category reads

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

The cache does not absorb it: entries live five seconds in per-process memory, and the
origin where this was measured serves roughly one request an hour behind a CDN, so the
walk is cold on essentially every render. The added cost is incurred within a single
render in any case.

### The motivating consumer no longer needs this

Recorded because it changes why the feature exists. The consumer whose pages produced
the measurements above has since replaced its per-node walk: the helper now reads the
category-parent link table and the enabled categories — two reads — and assembles the
tree in Python, verified byte-identical against the old implementation across its whole
corpus. Its affected page went 195 reads to 48, and on `0.1.0a50` it is now *below* where
it was on `0.1.0a49`.

So this feature is **not** justified by that consumer's page, and no performance claim
about that site should be attached to it. It is justified as a library defect in its own
right: any caller that walks a tree node by node still pays the doubled cost, and the
library offers no way to avoid it other than the rewrite that consumer performed for
itself. Whether priming measurably helps the walks that consumer did *not* rewrite is
being measured separately; a null result there does not invalidate the defect, it only
removes the last consumer-specific argument for urgency.

### Why categories only

The same bypass exists on the item path: `list_items(category_id=…)` resolves through a
batch read and skips `get_item`'s cache identically. Priming it is nevertheless **out of
scope**, for two measured reasons.

**It buys nothing observed.** The regression is entirely on the category path. On the
consumer's traffic-weighted measurements nothing on the item path got worse — one page
was flat at 25 reads, the landings were flat, and the item-heavy surfaces improved
sharply without any priming (search 434 → 218, one detail page 160 → 12, the public API
endpoint 5,226 → 6).

**It is expensive and exposed.** The cache has no eviction and no size cap, so a primed
row is held until a write clears everything. Measured on the consumer's corpus:

| Primed set | Rows | Memory |
|---|---:|---:|
| All categories | 93 | **0.17 MB** |
| One large item listing | 7,334 | **98.1 MB** |
| Whole item corpus | 8,351 | **108.1 MB** |

Items are not small — the metadata column alone is 25.9 MB of JSON on disk, averaging
3,258 bytes per row, which expands roughly fourfold once parsed. On that deployment 108
MB is 21.6% of a worker's resident size, across two workers, on a host already
swapping. And because the endpoint that triggers the largest listing is public and
unauthenticated, a single anonymous request would pin ~98 MB until a write or a worker
recycle — on a read-mostly deployment, effectively for the life of the worker. As a
library default that is a memory-exhaustion vector for any consumer with a large,
metadata-heavy corpus, not merely a large cache.

Priming categories costs 0.17 MB and captures the entire measured win. Priming items
costs two orders of magnitude more for no measured win. The item path stays unprimed
until the cache has an eviction policy, which is separate work.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second read does not re-fetch a category the first already returned (Priority: P1)

An application reads a set of categories through one of the two category batch methods,
then passes one of them as the argument to another read — most commonly by walking a
tree, where each node returned as a child becomes the parent of the next call. It should
not pay storage again for rows the library just held in memory.

**Why this priority**: This is the regression and its remedy. Every other story here
exists to keep this one from breaking something else.

**Independent Test**: Perform a category batch read, then look up a returned category
individually, and assert the second lookup costs zero storage reads.

**Acceptance Scenarios**:

1. **Given** a category with children, **When** the caller lists those children and
   then fetches one of them by id, **Then** the fetch costs no storage read.
2. **Given** an item placed in several categories, **When** the caller lists those
   categories and then fetches one of them by id, **Then** the fetch costs no storage
   read.
3. **Given** a multi-level tree, **When** the caller walks it node by node, **Then** the
   total read count is materially lower than both the current release and the one before
   it, and the per-node parent validation costs nothing.
4. **Given** the cache has been cleared, **When** either category method runs once,
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
2. **Given** a single cold call to either category method, **When** priming is added,
   **Then** it costs exactly what it costs today — priming writes to memory, it does not
   read from storage.

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
3. **Given** a category that does not exist, **When** a batch read omits it, **Then** a
   later individual lookup still raises the same not-found error as today — priming must
   never manufacture a hit for an absent row.
4. **Given** a batch read that deliberately ignores the enabled filter, **When** its
   results are primed, **Then** a later individual lookup returns exactly what a direct
   read would return, with no filter leaking into the cached value.

---

### User Story 4 - The item path is left measurably alone (Priority: P2)

An application reading a large category listing must not acquire a large resident cache
as a side effect. `list_items(category_id=…)` keeps its current behaviour exactly.

**Why this priority**: P2 because it is a constraint rather than a capability — but it
is the constraint that keeps this feature from introducing a worse problem than it
solves, so it is tested rather than assumed.

**Independent Test**: List a large category's items, then assert the cache holds no
entry for any of them.

**Acceptance Scenarios**:

1. **Given** a category holding many items, **When** the caller lists them, **Then** no
   item entry is added to the cache and memory does not grow with the result size.
2. **Given** a category holding many items, **When** the caller lists them and then
   fetches one by id, **Then** that fetch costs one storage read, exactly as today.

---

### Edge Cases

- **The same category appears in two batches.** Priming must be idempotent; the second
  write must not extend or shorten the entry's life in a way a direct read would not.
- **A category is deleted between the batch read and the later lookup.** A write clears
  the cache, so the later lookup must miss and behave exactly as it does today.
- **A batch read returns nothing.** Priming must be a no-op, not an error.
- **Unhashable arguments.** The cache already declines to store entries it cannot key;
  priming must decline in exactly the same circumstances rather than raising.
- **A very large category tree.** Priming is bounded by the number of categories, which
  is small in every corpus measured. The bound is documented rather than enforced; if a
  corpus ever makes it material, the answer is eviction in the cache, not a special case
  here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The caching utility MUST provide a way to insert a value for a given set
  of arguments, so that a later call with those arguments is served without reading
  storage.
- **FR-002**: `list_categories(parent_id=…)` and `list_categories_by_item(item_id)` MUST
  prime the per-category accessor with the categories they already fetched.
- **FR-003**: A primed entry MUST be indistinguishable from a normally cached one in
  value, lifetime and invalidation. No new staleness window may be introduced.
- **FR-004**: Priming MUST NOT create an entry for a row that was not actually read, and
  MUST NOT suppress the not-found error a later lookup of an absent row raises today.
- **FR-005**: The cost of a single cold call to either method MUST be unchanged. Release
  060's exact-constant gates MUST pass with their constants unmodified and no test
  edited.
- **FR-006**: The reduction MUST be asserted by tests that count storage reads across a
  repeated-access pattern — the case the 060 gates deliberately do not measure — so that
  removing priming later fails the build.
- **FR-007**: `list_items(category_id=…)` MUST NOT prime the per-item accessor, and a
  test MUST assert that listing a category's items adds no item entry to the cache.
  Rationale is recorded in "Why categories only": measured at 108 MB against 0.17 MB for
  categories, for no measured benefit, and reachable through a public unauthenticated
  endpoint on at least one real deployment.
- **FR-008**: Coverage MUST span all four storage backends, split by what each can
  assert. Exact read counts MUST be asserted on the spy-instrumented in-memory backend,
  which is the only one whose repository calls can be counted directly. The observable
  contract — the value served after a batch read is the true row, and a write still
  invalidates it — MUST be asserted on all four: JSON, YAML, Django and in-memory.
- **FR-009**: The behaviour MUST be documented for consumers, including which reads
  prime, which deliberately do not and why, the interaction with the cache lifetime, and
  what a write invalidates.

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

- **SC-001**: A tree walk pays exactly **one** category validation — its own root, which
  nothing returns as a child — regardless of how many nodes it visits or how deep the
  tree is. Asserted at two sizes so the constant is shown to be size-invariant; without
  priming this number tracks the node count, which is the regression. The downstream
  figures that motivated the work (151 → 177 → 102 on a 75-node tree) are cited as
  provenance, not as an acceptance target: they depend on that consumer's tree shape and
  are not reproducible in a fixture.
- **SC-002**: Looking up a category individually immediately after it was returned by
  either category batch method costs zero storage reads.
- **SC-003**: A single cold call to each affected method costs exactly what it costs
  today, verified by release 060's unmodified gates.
- **SC-004**: A write invalidates a primed entry exactly as it invalidates a normally
  cached one, verified per backend.
- **SC-005**: Removing priming fails the build.
- **SC-006**: Listing a category's items adds zero entries to the per-item cache,
  verified by test, so the 108 MB worst case cannot reappear unnoticed.

## Assumptions

- Release 060 stays exactly as it is. This feature restores a side effect its batch
  reads removed; it does not revert, re-tune or reshape them.
- The batch reads deliberately ignore the enabled filter so that a disabled row stays
  distinguishable from a deleted one. Priming inherits that unfiltered value, which
  matches what the per-row accessor returns, since that accessor applies no enabled
  filter either.
- Cache invalidation stays exactly as it is today: every write clears everything.
  Priming introduces no new invalidation path.
- Category counts are small in every corpus measured (93 in the largest), so unbounded
  priming of categories needs no cap. This is an assumption about scale, not a
  guarantee; if a consumer reports a category corpus large enough to matter, the answer
  is eviction in the cache rather than a threshold here.
- The tree-walk access pattern — a public call resolving a whole tree level or subtree in
  a constant number of reads — remains worth exposing eventually, but is out of scope and
  stops being urgent once priming lands, because it requires the consumer to migrate
  whereas this does not.

## Out of Scope

- Priming the per-item accessor. Revisit only after the cache has an eviction policy.
- Adding eviction or a size limit to the caching utility. Worth doing — the cache is
  already unbounded today and priming does not change that — but it touches all nine
  memoized reads and needs its own gates, so bundling it would put this fix behind
  unrelated risk.
- Reverting or re-tuning any part of release 060.
- Any new public API, including a batched tree-level or subtree read.
- Changing the cache lifetime or the invalidate-everything-on-write policy.

## Dependencies

- Release `0.1.0a50` (spec 060), which introduced the batch reads this feature primes
  from, and whose regression gates constrain it.
