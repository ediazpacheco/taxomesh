# Contract: Repository External-ID Lookup API

**Feature**: 032-external-id-index
**Date**: 2026-03-14

## Overview

These two methods are part of `TaxomeshRepositoryBase` (the structural protocol all backends
must implement). They were declared in spec 013. This spec promotes them to first-class,
documented, and tested API surface.

---

## `list_items_by_external_id(external_id: str) -> list[Item]`

**Contract**:

- Accepts a string `external_id`.
- Returns all `Item` instances whose `external_id` field equals the given string.
- Returns an empty list when no item matches.
- Returns one item when exactly one matches.
- Returns two or more items when duplicates exist.
- MUST NOT call `list_items()` internally.
- MUST use a filtered backend query (ORM `filter()` for Django; Python comprehension for
  file-based backends).

**Postconditions**:

| Result length | Consumer interpretation |
|---------------|------------------------|
| 0             | Orphan — no item registered with this `external_id` |
| 1             | Unique match — normal case |
| ≥ 2           | Duplicates — application must decide how to handle |

---

## `list_categories_by_external_id(external_id: str) -> list[Category]`

**Contract**: Identical semantics to `list_items_by_external_id`, applied to `Category`.

| Result length | Consumer interpretation |
|---------------|------------------------|
| 0             | Orphan — no category registered with this `external_id` |
| 1             | Unique match — normal case |
| ≥ 2           | Duplicates — application must decide how to handle |

---

## Backend implementations

| Backend | Query mechanism | Performance |
|---------|-----------------|-------------|
| `DjangoRepository` | `objects.filter(external_id=external_id)` — ORM filtered query | O(log n) with DB index (added in this spec) |
| `JsonRepository` | Python list comprehension over in-memory dict | O(n) — acceptable for file-based use |
| `YAMLRepository` | Python list comprehension over in-memory dict | O(n) — acceptable for file-based use |
