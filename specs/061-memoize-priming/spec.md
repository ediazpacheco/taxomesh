# Feature Specification: Repeated-access read costs after 060 — category priming and read-through

**Feature Branch**: `061-memoize-priming`
**Created**: 2026-09-10
**Updated**: 2026-09-12 — narrowed; re-scoped 2026-09-11. See Clarifications
**Status**: Draft
**Input**: User description (2026-09-10): "Restore the cache priming that release 060 removed, so repeated reads stop paying for rows the previous read already fetched."
Re-scope (2026-09-11): "A release that keeps every improvement 0.1.0a50 delivered AND has no query-count regression against 0.1.0a49 on any access pattern. Breaking changes are permitted. Do not prime `get_item` without eviction, and keep a gate that fails if anyone adds it."

## Context

### What 060 changed, and what it lost

Release `0.1.0a50` (spec 060) replaced per-row resolution with a single batch read in
three methods: `list_items(category_id=…)`, `list_categories(parent_id=…)` and
`list_categories_by_item(item_id)`. That removed a genuine N+1 and must not be reverted.
Measured by the one production consumer on its own corpus (8,351 items, 13,858
item-parent links): `list_items(category_id=<largest>)` went **5,220 → 3** queries and
**667 → 141 ms**; the pages that depend on it went `/buscar/?q=…` **286 → 43** and
`/milongas/<city>/<slug>/` **160 → 12**, both measured with the consumer's own per-node
walks already removed, so attributable to 060 alone.

It also had an unintended second effect. The per-row calls it replaced went through the
**memoized** accessors `get_category` and `get_item`; the batch reads go straight to the
repository. That lost two things, and the second was not visible until measured:

1. **Resolving a row as a result stopped priming the entry a later call needs when the row
   is passed as an argument.** `list_categories(parent_id=…)` validates its parent through
   `get_category`, so on a tree walk every node's validation — free on `0.1.0a49`, because
   the node had just been resolved as a child through that same accessor — became a miss.
2. **The batch read ignores the cache even when every row it needs is already in it.** On
   `0.1.0a49` a per-row read of a cached row cost nothing; on `0.1.0a50` a batch costs one
   read regardless. Priming alone does not touch this.

### The regression, measured

On the consumer's own category tree (a read-only copy of its database, its original
node-by-node walk copied verbatim, cold, counted per SQL query, median of 3; research.md
R5):

| | total | `category_parent_link` | `category` |
|---|---:|---:|---:|
| `0.1.0a49` | 150 | 75 | 75 |
| `0.1.0a50` | 177 | 75 | 102 |
| priming only | **103** | 75 | 28 |

The walk's output was identical across all three. The consumer's own measurement of the same
walk reads 151 / 177 / **102**; its 102 was taken with *every* category pre-cached, root
included. Real priming cannot pre-cache the walk's own root — nothing returns it as
anybody's child — so its validation remains the one genuine miss, and **103 is the floor for
this walk without changing the single-call cost that 060's gates fix at 3.**

The walk is not the only affected pattern. Measured on fixed fixtures, each release using
its own repository behind a read-counting proxy (research.md R6):

| pattern | `0.1.0a49` | `0.1.0a50` | priming only | priming + read-through |
|---|---:|---:|---:|---:|
| walk, 12 nodes, depth 2 | 26 | 30 | 18 | 18 |
| walk, 84 nodes, depth 3 | 170 | 191 | 107 | 107 |
| walk over shared children (multi-parent) | 12 | 16 | 11 | 9 |
| fetch children by id, then list them | 7 | 8 | **8** | 7 |
| `list_categories_by_item` over 40 items sharing 5 categories | 85 | 120 | **120** | 84 |

Priming alone still costs more than `0.1.0a49` on two of these, by up to 35 reads. The
second is the shape of a per-item URL builder the consumer measured and rejected on
`0.1.0a50`. **Priming plus read-through** — the batch consults the per-row cache and reads
only rows that are not in it — is at or below `0.1.0a49` on every category pattern
measured, and a single cold call still costs exactly 3.

### The goal, and the one exception this release accepts

On category reads the goal holds without exception: with priming and read-through, both
releases cache every category row they resolve, and a batch costs at most one read where
`0.1.0a49` paid one per missing row, so no category access pattern can cost more.

On the item path it does not hold, by decision (Clarifications). `list_items(category_id=…)`
keeps its batch read and does not prime `get_item`, so an item row that `0.1.0a49` would
later have served from cache — because a listing had just resolved it — costs one read
here. The excess is bounded: **at most one read per `list_items(category_id=…)` call in the
pattern.** Measured (research.md R6):

| pattern | `0.1.0a49` | this release |
|---|---:|---:|
| `list_items`, then `list_categories_by_item` per item (20) | 45 | 46 |
| `list_items`, then `get_item` per item (20) | 22 | 23 |
| 10 small `list_items` calls sharing the same 3 items | 23 | 30 |

Every other item pattern is cheaper than `0.1.0a49` by the 060 batch saving itself.

### Why the item path stays unprimed

- **The only production consumer asked for it explicitly**, and the goal's item exception is
  bounded and documented rather than hidden.
- **The cache has no eviction.** An entry lives until the next write, so anything primed is
  retained for the life of the process on a read-mostly deployment.
- **The consumer's memory figures**, relayed and not re-measured here: priming items retains
  108 MB per worker (≈13.6 KB per item, driven by `metadata`; cross-checked against 25.9 MB
  of metadata JSON on disk), on a host already swapping, reachable through a public
  unauthenticated endpoint.

Recorded so it is not assumed away: most of that retention **already happens today,
without any priming**. `list_items` is itself memoized, so its result list — the same item
objects — is retained until the next write. On a 2,000-item fixture (Django, ≈3.3 KB of
metadata per item; research.md R7), one `list_items(category_id=…)` call left **17.44 MB**
retained on `0.1.0a50` (20.09 MB on `0.1.0a49`); priming `get_item` on top added **2.37
MB**. Not priming items therefore avoids only the increment. The retention itself is a
pre-existing property of the unbounded cache and is out of scope here (see Out of Scope).

### The motivating consumer no longer walks node by node

The consumer has replaced both of its per-node walks with a two-read traversal of its own,
verified byte-identical against the old one. It is staying on `0.1.0a49` for reasons
unrelated to this feature. This release is therefore justified as a library defect in its
own right — any caller that walks a tree node by node still pays the cost — and not by
any consumer page. A measurement of priming on the consumer's remaining walk-shaped call
sites was not available when this spec was written.

## Clarifications

### Session 2026-09-11

- Q: How should the item path be handled, given the goal needs item priming and the hard constraint allows it only behind eviction? → A: Categories only — priming and read-through for categories; no eviction work; the item residual is accepted and documented.
- Q: How should the cache gain its new operations? → A: A descriptor class, so insert and lookup are typed methods on the decorated callable rather than a module-level helper reaching into a closure.
- Q: Class names in the caching utility? → A: `MemoizedFunction` (what `memoize(ttl)` returns) and `MemoizedMethod` (what accessing it on an instance returns). The decorator keeps its name.
- Q: Cache invalidation (module-level registry and `clear_all_caches()`)? → A: Leave as is. The Principle XI exception is recorded in the plan.

### Session 2026-09-12

- Q: The 2026-09-11 session added a subtree read, `list_descendant_categories(category_id, *,
  enabled=True) -> dict[UUID, list[Category]]`. Does it still belong in this feature? → A: No.
  Its name repeats the defect the API refactor exists to fix — a `list_*` that returns a
  mapping — so shipping it here would cement a name already known to be wrong. It moves out of
  061 in full: User Story 4, FR-008, FR-009, SC-004, the "Descendant map" entity and every
  clause naming it are removed, and the read is now owned by the API-UX and documentation
  refactor (see Out of Scope). Its behaviour and measurements are not lost: they survive in
  this file's 2026-09-11 revision and in `measurements/README.md` R8. Nothing else about the
  feature changes — priming, read-through, the item exception and the cache's typed operations
  are untouched.
- Q: Read-through means some rows are now resolved from the cache itself. Does a read-through
  hit re-prime the entry, refreshing its timestamp? → A: No. Priming is confined to rows
  actually fetched from storage; a row served from the cache leaves its timestamp untouched,
  exactly as a `get_category` cache hit does. The cache keeps fixed expiry from the fetch, not
  sliding expiry from the last access — re-priming hits would give a hot row an unbounded
  lifetime, which is a behaviour change nothing here asks for and which would make "its
  lifetime expires" untestable.
- Q: What are the two new cache operations called? → A: `prime(value, /, *args, **kwargs)` for
  the insert — already the vocabulary of the spec, the docstrings and the measurement
  scripts — and `cached(*args, **kwargs)` for the lookup, which names the question the call
  site asks rather than the mechanism. Not `get`/`set`: mapping vocabulary would advertise
  `dict` semantics the cache does not offer and would hide that a stale entry is a miss.
- Q: Other service reads also resolve full category rows without priming — `get_graph`, the
  search corpus builder, `get_category_by_slug`, `get_category_by_external_id`,
  `get_categories_by_external_ids`. Do they prime too? → A: No. Exactly the two reads FR-002
  names. None of the others primed on `0.1.0a49` either, so leaving them costs no parity;
  priming them would be a new improvement rather than a regression fix, with no measured
  caller that benefits, and each path added is another exact-count gate on four backends.
- Q: How does the FR-007 gate observe that nothing was added to the per-item cache? → A:
  Through the new public lookup — after `list_items(category_id=…)`, `get_item`'s `cached` must
  report a miss for every listed item. It gates the requirement with the API this feature
  already adds, is precise per item rather than an aggregate count, and needs no public
  surface that exists only for a test. No entry-count member is added, and no test reads the
  cache's internals.
- Q: `functools.wraps` currently gives a decorated method its own `__name__`, `__doc__` and
  signature; a class instance inherits none of that. What must survive? → A: All of it. The
  memoized object carries the decorated callable's `__name__`, `__qualname__`, `__module__`,
  `__doc__` and `__wrapped__`, gated by a test. Sixteen public service methods are memoized and
  each is required to carry a Google-style docstring; losing introspection would silently show
  the cache class's docstring in `help()` and every IDE, and degrade `inspect.signature` to
  `(*args, **kwargs)` — the exact failure an existing drift guard was written to catch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A category already in memory is not read again (Priority: P1)

An application reads categories through any category read, then reads some of those
categories again — as an argument to another call, individually, or as part of another
batch. It should not pay storage again for rows the library already holds.

**Why this priority**: This is the regression and its remedy.

**Independent Test**: Warm the cache with a category read, then perform a read that needs
only those rows, and assert it costs zero row reads.

**Acceptance Scenarios**:

1. **Given** a category with children, **When** the caller lists the children and then
   fetches one by id, **Then** the fetch costs no storage read.
2. **Given** an item placed in several categories, **When** the caller lists those
   categories and then fetches one by id, **Then** the fetch costs no storage read.
3. **Given** categories already in the cache, **When** a batch read needs only those
   categories, **Then** it reads no category row from storage.
4. **Given** a batch read that needs some cached and some uncached categories, **When** it
   runs, **Then** it reads only the uncached ones, in a single read.
5. **Given** a multi-level tree, **When** the caller walks it node by node, **Then** the walk
   pays exactly one category validation — its own root — whatever the tree's size or depth.
6. **Given** any category access pattern, **When** it runs, **Then** it costs no more storage
   reads than it did on `0.1.0a49`.

---

### User Story 2 - Release 060's gains and gates are untouched (Priority: P1)

**Why this priority**: Equal to P1. Those gates exist so that later work cannot silently
undo 060; this feature is exactly the later work they were written to catch.

**Independent Test**: Run 060's gate files and the full suite unmodified.

**Acceptance Scenarios**:

1. **Given** the 060 read-count gates, **When** this feature lands, **Then** every gate
   passes with its constants unchanged and no test edited.
2. **Given** a single cold call to any of the three batched methods, **When** this feature
   lands, **Then** it costs exactly what it costs on `0.1.0a50`.

---

### User Story 3 - Cached values stay correct (Priority: P1)

A primed entry must be indistinguishable from one the accessor itself would have stored,
and a value served by read-through must be exactly what a direct read would return.

**Why this priority**: Equal to P1. A caching change that trades correctness for speed is
not acceptable at any speed.

**Independent Test**: Prime an entry, mutate the underlying row, and assert the next read
reflects the mutation.

**Acceptance Scenarios**:

1. **Given** a primed entry, **When** any write occurs, **Then** the entry is invalidated
   exactly as a normally cached entry would be.
2. **Given** a primed entry, **When** its lifetime expires, **Then** it is treated as absent —
   by the accessor and by read-through alike.
3. **Given** a category that does not exist, **When** a batch read omits it, **Then** a later
   individual lookup still raises the same not-found error, with the same message, as today.
4. **Given** a batch read that deliberately ignores the enabled filter, **When** its results
   are primed, **Then** a later individual lookup returns exactly what a direct read returns.

---

### User Story 5 - The item path is left alone, and its cost is stated (Priority: P2)

**Why this priority**: P2 because it is a constraint rather than a capability — but it is the
constraint the only production consumer asked for, so it is tested rather than assumed.

**Independent Test**: List a category's items, then assert the per-item accessor's `cached`
lookup reports a miss for every one of them.

**Acceptance Scenarios**:

1. **Given** a category holding items, **When** the caller lists them, **Then** no per-item
   cache entry is added.
2. **Given** a category holding items, **When** the caller lists them and fetches one by id,
   **Then** that fetch costs one storage read.
3. **Given** the item patterns measured in Context, **When** they run, **Then** each costs
   exactly the recorded value, and no pattern exceeds `0.1.0a49` by more than one read per
   `list_items(category_id=…)` call it contains.

---

### User Story 6 - Existing uses of the caching utility keep working, now fully typed (Priority: P2)

Applications that decorate their own functions with the library's caching decorator —
including functions with no parameters and keyword-only functions — keep working without
change, and the new insert and lookup paths are statically checked against the decorated
function's own signature and return type.

**Why this priority**: P2. The consumer decorates six of its own functions this way; a
break here would cost it more than this feature saves it.

**Independent Test**: Decorate a zero-argument, a keyword-only and a positional function
and a method; call, prime, look up and clear each; inspect each one's name, docstring and
signature; run strict type checking over deliberate misuse.

**Acceptance Scenarios**:

1. **Given** a decorated plain function of any parameter shape, **When** it is called, primed
   or cleared, **Then** it behaves as it does today.
2. **Given** a decorated method, **When** it is accessed through an instance, **Then** calls and
   priming use that instance's cache entries exactly as calls do today.
3. **Given** priming with a value of the wrong type or arguments of the wrong type, **When**
   strict type checking runs, **Then** it reports an error.
4. **Given** a decorated function or method, **When** its name, docstring or signature is
   inspected, **Then** each is the decorated callable's own, not the cache object's.

---

### Edge Cases

- **The same category appears in two batches.** The second batch finds the row cached, serves
  it through read-through and does not fetch or re-prime it, so its timestamp is untouched —
  exactly what a second `get_category` call does. Once the entry has expired, the next batch
  fetches the row again and primes it afresh, as a second real call after expiry would.
  Priming itself stays idempotent: writing the same key twice overwrites rather than raising.
- **An entry expires between the read-through check and its use.** The check is the
  decision: a row found fresh is served, a row found expired is re-read. No row is served
  that the accessor itself would have refused.
- **A category is deleted between a batch read and a later lookup.** A write clears every
  cache, so the later lookup misses and behaves exactly as today.
- **A batch read returns nothing.** Priming is a no-op, not an error.
- **Unhashable arguments.** The cache already declines to store entries it cannot key;
  priming and lookup decline in exactly the same circumstances rather than raising.
- **A placement link points at a category row that no longer exists.** Every read raises the
  same not-found error it raises today.
- **Ties in sort order.** Children with equal sort positions come back in the same relative
  order as from `list_categories(parent_id=…)`, on every backend.
- **A very large category tree.** Priming is bounded by the number of categories (93 in the
  largest corpus measured). If a corpus ever makes that material, the answer is eviction in
  the cache, not a threshold here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The caching utility MUST let a caller insert a value for a given set of
  arguments (`prime`) and look up whether a fresh value exists for them (`cached`), keyed
  exactly as a call with those arguments is keyed. Both MUST be statically checked against
  the decorated callable's own parameters and return type. `cached` MUST report a stale entry
  as a miss, and MUST distinguish a miss from a cached value that is itself falsy or `None`.
- **FR-002**: `list_categories(parent_id=…)` and `list_categories_by_item(item_id)` MUST prime
  the per-category accessor with every category row they **fetch from storage**, before any
  enabled filter is applied. A row they resolve from the cache instead MUST NOT be re-primed.
- **FR-003**: Those same reads MUST resolve category rows through the per-category cache
  first and read from storage only the rows not freshly cached, in at most one read; when
  every row is cached they MUST read no category row. The cache consultation MUST be
  read-only: it MUST NOT write, refresh or evict any entry.
- **FR-004**: A primed entry MUST be indistinguishable from a normally cached one in value,
  lifetime and invalidation. No new staleness window may be introduced. Lifetime is measured
  from the fetch that produced the entry and MUST NOT be extended by later access, whether
  that access is a call or a read-through lookup.
- **FR-005**: Priming MUST NOT create an entry for a row that was not read, and MUST NOT
  change any not-found error or its message.
- **FR-006**: The cost of a single cold call to each of the three batched methods MUST be
  unchanged. Release 060's exact-constant gates MUST pass with their constants unmodified
  and no test edited.
- **FR-007**: `list_items(category_id=…)` MUST NOT prime the per-item accessor, and a test
  MUST fail if it ever does. The gate MUST observe this through the per-item accessor's own
  `cached` lookup — a miss for every listed item — not through an entry count and not by
  reading the cache's internals.
- **FR-008**: *(removed 2026-09-12 — the descendant read moved to the API refactor; see
  Clarifications and Out of Scope.)*
- **FR-009**: *(removed 2026-09-12 — same.)*
- **FR-010**: Repeated-access gates MUST assert exact read counts, not bounds, for: the
  node-by-node walk at two sizes and two depths; the multi-parent walk; fetch-then-list;
  repeated `list_categories_by_item`; and the three item patterns in Context. Removing
  priming or read-through MUST fail the build.
- **FR-011**: Exact read counts MUST be asserted on all four storage backends — in-memory,
  JSON, YAML and Django — and the observable contract (true values served, writes
  invalidate) MUST hold on all four.
- **FR-012**: Decorating plain functions of every parameter shape (none, keyword-only,
  positional) and methods MUST keep working unchanged, including the per-callable manual
  clear and `clear_all_caches()`.
- **FR-013**: Consumer documentation MUST state which reads prime and read through, that
  listing items does neither and what that costs relative to `0.1.0a49`, the cache lifetime,
  that every write clears everything, and that `list_items`'s own result cache retains a
  listing until the next write.
- **FR-014**: Every read-count or memory figure cited in documentation or the changelog MUST
  either be reproduced by a test in this repository or carry its external provenance.

### Non-Functional Requirements

- **NFR-001**: No new runtime dependency.
- **NFR-002**: No change to stored data and no migration.
- **NFR-003**: No existing public method changes signature or return type, and no public
  method is added. The caching decorator's return type changes from a plain callable to a
  typed callable object; calling behaviour is unchanged, and so is introspection — a decorated
  callable MUST still report its own `__name__`, `__qualname__`, `__module__`, `__doc__` and
  its own signature, exactly as it does today under `functools.wraps`.
- **NFR-004**: The existing quality gates MUST pass: linting, formatting, strict type
  checking, and the test suite at or above its coverage floor.
- **NFR-005**: No new type-checker suppression, no unjustified `Any`, and no new
  module-level function with side effects.

### Key Entities

- **Cached entry**: A stored result keyed by the arguments that produced it, with a
  timestamp governing its lifetime, cleared wholesale on any write. This feature adds a
  second way for one to come into existence (priming) and a way to consult it without
  calling the accessor (lookup).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A node-by-node walk pays exactly one category validation, its own root,
  asserted as exact constants at two sizes and two depths on all four backends. On the
  consumer's own tree the walk costs 103 reads, against 150 on `0.1.0a49` and 177 on
  `0.1.0a50` (external provenance: research.md R5).
- **SC-002**: Every category pattern in Context costs at most its `0.1.0a49` value, asserted
  as exact constants on all four backends; the two that priming alone left above
  `0.1.0a49` (8 vs 7, 120 vs 85) come in at 7 and 84.
- **SC-003**: A single cold call to each batched method costs exactly what it costs on
  `0.1.0a50`, verified by 060's unmodified gates.
- **SC-004**: *(removed 2026-09-12 — the descendant read moved to the API refactor; see
  Clarifications and Out of Scope.)*
- **SC-005**: Removing priming or read-through fails the build.
- **SC-006**: Listing a category's items adds zero entries to the per-item cache.
- **SC-007**: Each item pattern in Context costs exactly its recorded value, and none exceeds
  `0.1.0a49` by more than one read per `list_items(category_id=…)` call it contains.
- **SC-008**: A write invalidates a primed entry exactly as it invalidates a normally cached
  one, on all four backends.
- **SC-009**: Decorated plain functions of every parameter shape and decorated methods pass
  strict type checking with no suppression, and deliberate misuse of priming is reported.
- **SC-010**: Every figure in the documentation and changelog is reproduced by a test here or
  labelled with its external provenance.

## Assumptions

- Release 060 stays exactly as it is. This feature restores and extends what its batch
  reads bypassed; it does not revert, re-tune or reshape them.
- The batch reads deliberately ignore the enabled filter so that a disabled row stays
  distinguishable from a deleted one. Priming inherits that unfiltered value, which matches
  what the per-row accessor returns.
- Cache invalidation stays exactly as it is today: every write clears everything.
- Category counts are small in every corpus measured (93 in the largest), so unbounded
  priming of categories needs no cap. This is an assumption about scale, not a guarantee.

## Out of Scope

- Priming, or reading through, the per-item accessor.
- Eviction, a size limit or expiry reclamation in the caching utility — including for the
  retention `list_items`'s own result cache already has (Context). Reclaiming expired
  entries is the candidate fix: an expired entry is never served, so dropping it cannot
  change any read count. Recorded as follow-up.
- Priming, or reading through, any category read other than the two FR-002 names — including
  `get_graph`, the search corpus builder, `get_category_by_slug`, `get_category_by_external_id`
  and `get_categories_by_external_ids`. None of them primed on `0.1.0a49`, so none of them is
  a regression; extending to them is a separate improvement and needs its own evidence.
- **Any new public read for tree walks — the subtree read included.** The 2026-09-11 revision
  of this spec specified one as `list_descendant_categories(category_id, *, enabled=True) ->
  dict[UUID, list[Category]]`; it is removed here because that name is an instance of the
  defect the API-UX refactor exists to fix — a `list_*` that returns a mapping — and naming
  it correctly needs the convention that refactor will decide. Ownership, and the behaviour
  and measurements already established for it, are carried in
  `docs/backlog/prompt-api-refactor.md` (defect 6), which points back at this file's
  2026-09-11 revision and at `measurements/README.md` R8. Two shapes stay out regardless of
  what that refactor decides: a per-level read keyed by parent, whose cost grows with depth
  (`measurements/README.md` R8), and a descendant read from the implicit taxonomy root, which
  `get_graph` already covers.
- Reverting or re-tuning any part of release 060.
- Changing the cache lifetime, the invalidate-everything-on-write policy, the module-level
  cache registry, or how method caches are keyed.

## Dependencies

- Release `0.1.0a50` (spec 060), which introduced the batch reads this feature primes from
  and whose regression gates constrain it.
