# Research: Memoize Batched Related-Items Lookup

**Feature**: 055-memoize-batch-related | **Date**: 2026-06-11

No NEEDS CLARIFICATION markers remained in the Technical Context. The decisions below
resolve the design choices the spec left to planning.

## D1 — Memoization pattern: public normaliser + private `@memoize` implementation

**Decision**: Keep the public `list_related_items_for_sources` undecorated; it
normalises arguments into hashable forms and delegates to a new private
`_fetch_related_items_for_sources` decorated with `@memoize(DEFAULT_CACHE_TTL)`.

**Rationale**: Direct decoration cannot work — the public signature takes unhashable
arguments (`Collection[UUID]`, `Collection[str] | None`), and `memoize` silently
*bypasses* the cache on unhashable keys (`taxomesh/utils/memoize.py` catches
`TypeError` and calls through). The split pattern is already established in this exact
file by `get_items_by_external_ids` → `_fetch_items_by_external_ids` and
`get_categories_by_external_ids` → `_fetch_categories_by_external_ids`, so it is the
consistent, reviewed approach.

**Alternatives considered**:
- *Decorate the public method and require hashable args* — breaking API change,
  violates FR-006.
- *Make `memoize` convert unhashable args itself* — generic deep-freezing is fragile
  (cannot know `["a","b"]` ≡ `["b","a"]` is semantically true here) and would change
  cache-key behaviour of every other memoized method.

## D2 — Relation-types cache key: deduplicated **sorted tuple**, `None` for "no filter"

**Decision**: `tuple(sorted({t.strip().lower() for t in relation_types})) if relation_types else None`.

**Rationale**: A sorted tuple of the deduplicated, normalised types is hashable,
order-insensitive, and duplicate-insensitive (FR-002), and — unlike a `frozenset` — has
deterministic iteration order, so the downstream repository call receives a stable
argument (useful for query plans, logging, and test assertions). The existing
`if relation_types else None` falsy check already collapses `None` and `[]` into one
"no filter" representation; keeping it satisfies the spec's `None`≡`[]` scenario.

**Alternatives considered**:
- *`frozenset[str]`* — equally valid for the cache key, but iteration order is
  non-deterministic across processes; sorted tuple is strictly more predictable at no
  cost.
- *Preserve caller order* — would fragment the cache for reordered calls, violating
  FR-002.

## D3 — `skip_on_error` stays in the cache key

**Decision**: Pass `skip_on_error` through to the memoized private method as a keyword
argument, making it part of the cache key.

**Rationale**: The flag changes observable behaviour (skip-and-warn vs raise) *and*
the result contents when dangling links exist (skipped links are absent from the
result). Sharing entries across flag values could return a `skip_on_error=True`-shaped
result to a `skip_on_error=False` caller, silently suppressing the error contract
(FR-003). The cost — at most two entries per logical query — is negligible.

**Alternatives considered**: *Exclude it and document why* — rejected; correctness
depends on it whenever dangling links exist.

## D4 — Error results are not cached

**Decision**: Rely on `memoize`'s existing behaviour: only returned values are stored;
exceptions propagate without creating a cache entry.

**Rationale**: Satisfies the spec edge case ("a raised error MUST NOT poison the
cache") with zero new code. Matches sibling methods (`get_item`, `get_item_by_slug`)
whose not-found errors are likewise un-cached.

## D5 — FR-009: bulk target resolution in `list_related_items` is included

**Decision**: Implement the optional FR-009 — resolve targets via one
`self._repo.get_items_by_ids(ids, enabled=None)` call instead of per-link
`self.get_item(...)`.

**Rationale**: The replacement is ~8 lines, removes N cold-cache queries, and
preserves behaviour exactly:
- `get_item` returns items **regardless of enabled state** → the bulk call must use
  `enabled=None` (NOT `enabled=True`, which `list_related_items_for_sources` uses for
  its different, documented contract).
- `get_item` raises `TaxomeshItemNotFoundError("Item not found: {id}")` on a dangling
  target → the bulk path re-raises the same error with the same message for the first
  missing ID in link order.
- Result order (link order, duplicates preserved) is reconstructed from the ordered ID
  list, not from the dict.

**Alternatives considered**:
- *Skip FR-009* — allowed by the spec, but the implementation stays simple, so the
  cold-path win is taken.
- *Use `enabled=True`* — would silently drop disabled related items, changing
  behaviour; rejected.
- *Route through `list_related_items_for_sources`* — different contract (groups by
  relation type, filters `enabled=True`, skips dangling links by default); adapting it
  would complicate the code rather than simplify.

## D6 — `frozenset` for source IDs, computed where `set` is today

**Decision**: `unique_ids = frozenset(source_item_ids)` replaces `set(...)`; the
empty-input short-circuit stays in the public method, before the cache.

**Rationale**: The deduplicated set already exists; freezing it makes it hashable at
no extra pass. Returning `{}` for empty input before delegation avoids a useless cache
entry and keeps today's "no repository call on empty input" behaviour.

## D7 — Release conventions

**Decision**: New CHANGELOG entry `## [0.1.0a44] — <date>` under a `### Performance`
heading (mirroring 0.1.0a42's style for feature 054); bump `pyproject.toml` `version`
and keep `taxomesh.__version__` in sync (regression noted in 0.1.0a43 notes).

**Rationale**: Matches Keep-a-Changelog + SemVer pre-release conventions already used
by the repo; the `__version__` sync issue recurred before, so it is an explicit step.
