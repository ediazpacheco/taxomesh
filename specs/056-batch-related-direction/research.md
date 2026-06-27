# Phase 0 Research: Direction-Aware Batched Related-Items Traversal

All Technical Context items were resolvable from the existing codebase; no open
NEEDS CLARIFICATION remained. This document records the design decisions and the
evidence behind them.

## Decision 1 — API shape: generalize with a `direction` parameter

- **Decision**: Add `direction: Literal["outgoing", "incoming", "both"] = "outgoing"`
  to the existing `list_related_items_for_sources` rather than adding a new
  `list_related_items_for_targets` method.
- **Rationale**: User-selected. Keeps a single batched primitive whose direction
  vocabulary matches the already-shipped single-item methods
  (`list_related_items` / `list_item_relations`, which use the same
  `Literal["outgoing", "incoming", "both"]`). Default `outgoing` preserves
  backward compatibility.
- **Alternatives considered**: A new symmetric method
  `list_related_items_for_targets` (cleaner name symmetry with the repository
  layer, fully additive). Rejected by the user in favor of one direction-aware
  method. Trade-off accepted: the method name `..._for_sources` and parameter
  `source_item_ids` become slightly inaccurate for the incoming/both cases; the
  docstring documents that the ids are the *queried* items interpreted per
  direction.

## Decision 2 — Scope includes `"both"`

- **Decision**: Support all three direction values, including `"both"`.
- **Rationale**: User-selected; completes parity with the single-item method's
  `direction="both"`.
- **Repository-call cost**: all three directions = 2 calls (one link query + one
  bulk item lookup), constant w.r.t. input size — the anti-N+1 property holds in
  every direction. (`both` was initially designed as 3 calls; see Decision 7,
  which collapses it to a single combined query → 2 calls.)
- **Alternatives considered**: outgoing + incoming only (strict two-call wording,
  callers compose `both` themselves). Rejected by the user.

## Decision 3 — Add a batched incoming-link query at the repository layer

> **Amendment (post-review)**: superseded by Decision 7. The repository layer is
> unified into a single direction-aware method
> `list_item_relation_links_for_items(item_ids, *, direction, relation_types)`
> rather than a separate `..._for_targets` sibling, and `both` collapses to one
> combined query. See Decision 7.

- **Decision**: Add `list_item_relation_links_for_targets(target_item_ids, *,
  relation_types=None) -> list[ItemRelationLink]` to the
  `TaxomeshRepositoryBase` Protocol and all adapters.
- **Rationale**: The repository currently exposes only
  `list_item_relation_links_for_sources` (batched outgoing) and the single-item
  `list_item_relation_links` (direction-aware but one item at a time). A batched
  incoming query keyed by target ids is required to keep the incoming path at two
  calls; without it the service would have to loop the single-item query
  (re-introducing N+1).
- **Evidence**: `taxomesh/ports/repository.py:501` declares
  `list_item_relation_links_for_sources`; no `..._for_targets` exists. All four
  adapters implement the outgoing batched query with an identical
  filter-then-`sorted(...)` (in-memory) or `.filter(source_item_id__in=...)`
  (Django) shape.
- **Contract symmetry**: deterministic order
  `(target_item_id, relation_type, sort_index, source_item_id)` — the mirror of
  the outgoing order. Empty input → `[]`; optional relation-type allow-list; flat
  list return.

## Decision 4 — Reuse existing conventions verbatim

Confirmed from `taxomesh/application/service.py:1159-1279`:

- **Grouping shape**: `dict[UUID, dict[str, list[Item]]]` keyed by the queried id,
  then relation type, to a list of related items.
- **relation_type normalization**: `strip().lower()`, deduplicated, sorted tuple;
  case-insensitive filtering. (Domain model also normalizes on construction.)
- **Missing/disabled item**: `skip_on_error=True` (default) skips + logs a WARNING
  with the same message shape; `skip_on_error=False` raises
  `TaxomeshItemNotFoundError`.
- **Enabled policy**: `get_items_by_ids(needed_ids, enabled=True)` — only enabled
  related items are materialized; a link to a disabled item is treated as
  dangling. Unchanged across directions.
- **Empty input**: fast path returns `{}` with zero repository calls.
- **Caching**: public wrapper normalizes args (`frozenset` ids, sorted tuple
  types) and delegates to a `@memoize(DEFAULT_CACHE_TTL)` private method.
  `direction` becomes part of the cache key (independent entries per direction);
  writes and `clear_all_caches()` invalidate.

## Decision 5 — `both` union ordering

- **Decision**: For `direction="both"`, within each
  `{queried_id: {relation_type: [...]}}` group, concatenate outgoing-derived
  related items first (in `(sort_index, target_item_id)` order), then
  incoming-derived related items (in `(sort_index, source_item_id)` order).
- **Rationale**: Deterministic, reproducible, and trivially testable. A single
  link cannot contribute to both halves because the domain model rejects
  self-relations (`source_item_id == target_item_id`), so no de-duplication across
  the two halves is needed.

## Decision 6 — Versioning & docs

- **Decision**: Bump `0.1.0a45 → 0.1.0a46` in `pyproject.toml` and
  `taxomesh/__init__.py`; add a CHANGELOG entry under the new version; update the
  method docstring and any README/API reference to the batched method.
- **Rationale**: Matches the established per-feature pre-alpha release convention
  (see CHANGELOG history and spec 055).

## Decision 7 — Unify the repository batched query + collapse `both` to one call (post-review)

- **Decision**: Replace the two batched link queries with one direction-aware
  method `list_item_relation_links_for_items(item_ids, *, direction="outgoing"|
  "incoming"|"both", relation_types=None)` on the Protocol and all adapters. The
  `both` path uses a single combined `Q(source_item_id__in) | Q(target_item_id__in)`
  query, so every direction costs exactly two repository calls (was three for
  `both`).
- **Rationale**: User-directed performance + simplicity pass. One method matches
  the direction-parameter shape of the single-item `list_item_relation_links`,
  removes the sibling-method duplication flagged in review, and drops `both`
  from three repository calls to two. The user explicitly waived backward
  compatibility, so the shipped `list_item_relation_links_for_sources` is removed
  rather than kept as a wrapper.
- **Ordering**: the service materialises `both` from the single query and sorts
  the derived entries so each `(group, relation_type)` still lists
  outgoing-derived items first, then incoming-derived ones (FR-004 preserved).
- **Consequence**: `both` = 2 calls (FR-006 / SC-002 updated). A counting test
  backend pins the two-call bound; a Django `CaptureQueriesContext` test pins the
  single combined SQL query.

## Decision 8 — Mirror Django index for the incoming/both query (post-review)

- **Decision**: Add composite index `taxomesh_rl_tgt_type_sort_idx` on
  `(target_item_id, relation_type, sort_index, source_item_id)` (migration
  `0010`), the mirror of `taxomesh_rl_src_type_sort_idx` (migration `0006`).
- **Rationale**: The outgoing batched query is fully index-covered (filter +
  `ORDER BY`); the incoming/both query filters via the FK index but its
  `ORDER BY` was a filesort. The mirror index makes it an index scan, giving the
  incoming path the same performance characteristics as outgoing.
