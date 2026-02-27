# Research: Unique Parent Link Constraint

**Feature**: 010-unique-parent-links
**Date**: 2026-02-27

## Research Summary

No external research required. This feature applies an existing internal
pattern (`save_item_parent_link()` upsert) to `save_category_parent_link()`.

## Decisions

### D-001: Upsert pattern for category-parent links

- **Decision**: Linear scan + in-place replacement (same pattern as item links)
- **Rationale**: All three repository implementations use `list[CategoryParentLink]`
  as their backing store. The existing `save_item_parent_link()` uses a linear
  scan with `enumerate()` to find a matching `(item_id, category_id)` pair and
  replaces the element in-place. This pattern is proven, simple, and consistent.
- **Alternatives considered**:
  - Set/dict keyed by composite tuple — would require data structure change
    across all repos; not worth the complexity for the expected link count.
  - Pre-check at service level — would duplicate logic; repository is the
    correct deduplication boundary (same as item links).

### D-002: Composite key for category-parent uniqueness

- **Decision**: `(category_id, parent_category_id)` — matches the
  `CategoryParentLink` model's identity fields.
- **Rationale**: A category can have multiple parents (DAG), but each
  `(child, parent)` edge must be unique. The `sort_index` is the only
  mutable attribute on a link with the same composite key.
- **Alternatives considered**: None — this is the natural key.

### D-003: No service-level deduplication guard

- **Decision**: Upsert lives in the repository only; service delegates.
- **Rationale**: Matches existing pattern for item links. The service calls
  `check_no_cycle()` before saving, then delegates to the repository. Adding
  a service-level check would be redundant.
- **Alternatives considered**:
  - Service-level "link exists?" check before `check_no_cycle()` — rejected
    because `check_no_cycle()` is harmless on existing edges (the edge is
    already in the adjacency list, so no new cycle is possible).
