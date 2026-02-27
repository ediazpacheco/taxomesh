# Data Model: Unique Parent Link Constraint

**Feature**: 010-unique-parent-links
**Date**: 2026-02-27

## Entities (unchanged)

No domain model changes. The existing models are used as-is.

### CategoryParentLink

| Field | Type | Constraint |
|-------|------|------------|
| `category_id` | `UUID` | FK → Category |
| `parent_category_id` | `UUID` | FK → Category |
| `sort_index` | `int` | Default `0` |

**Uniqueness**: `(category_id, parent_category_id)` — enforced at repository
level via upsert. If a link with the same pair exists, `sort_index` is updated
in-place.

### ItemParentLink

| Field | Type | Constraint |
|-------|------|------------|
| `item_id` | `UUID` | FK → Item |
| `category_id` | `UUID` | FK → Category |
| `sort_index` | `int` | Default `0` |

**Uniqueness**: `(item_id, category_id)` — already enforced at repository level
via upsert. Formalized as a requirement in this spec.

## Behavioral Changes

### save_category_parent_link() — Before vs After

**Before**: Unconditional `append(link)` → duplicates possible.

**After**: Scan existing links for matching `(category_id, parent_category_id)`.
If found, replace in-place (updating `sort_index`). If not found, append.

### save_item_parent_link() — No change

Already implements upsert. Behavior formalized as contractual requirement.
