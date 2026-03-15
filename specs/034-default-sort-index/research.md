# Research: Default sort_index Ordering for All Collection-Returning Methods

**Feature**: 034-default-sort-index
**Date**: 2026-03-15

---

## Finding 1 — Domain Models: Which Entities Have sort_index

| Entity | Has sort_index? | Sort field for unfiltered listing |
|--------|----------------|-----------------------------------|
| `Category` | **No** | `name` (alphabetical) |
| `Item` | **No** | `name` (alphabetical) |
| `CategoryParentLink` | **Yes** (`sort_index: int`, default=0) | `sort_index` |
| `ItemParentLink` | **Yes** (`sort_index: int`, default=0) | `sort_index` |
| `ItemRelationLink` | **Yes** (`sort_index: int`, default=0) | `sort_index` |
| `Tag` | **No** | Out of scope (spec decision) |

**Decision**: For entities without a direct `sort_index`, use `name` as the primary sort
key for unfiltered listing. This is already implemented in the service layer for
`list_categories(external_id=X)` (sorts by name). Consistent with the spec decision
documented in FR-004.

---

## Finding 2 — Spec Correction: FR-005 list_items() Unfiltered

**Issue**: FR-005 states `list_items()` MUST sort by `sort_index`. `Item` has no
`sort_index` field. The spec assumption was incorrect.

**Correction**: `list_items()` without `category_id` filter MUST sort by `item.name`
(ascending alphabetical), matching the FR-004 decision for `list_categories()` unfiltered.
When `category_id` is provided, the service layer already sorts by `ItemParentLink.sort_index`
(existing correct behavior — no change needed).

**Rationale**: Consistent pattern across both primary entity types. Name is the only
stable, user-meaningful field available on both `Category` and `Item` for a global sort.

---

## Finding 3 — Current Ordering Gaps (what is NOT yet sorted)

| Method | Layer | Current behavior | Gap |
|--------|-------|-----------------|-----|
| `list_categories()` | Repo (JSON/YAML) | `dict.values()` — insertion order | No sort |
| `list_categories()` | Repo (Django) | ORM `.all()` — DB order | No sort |
| `list_items()` | Repo (JSON/YAML) | `dict.values()` — insertion order | No sort |
| `list_items()` | Repo (Django) | ORM `.all()` — DB order | No sort |
| `list_category_parent_links()` | All repos | Unsorted | No sort |
| `list_item_parent_links()` | All repos | Unsorted | No sort |
| `list_items_by_external_id()` | All repos | Unsorted | No sort |
| `list_categories_by_external_id()` | All repos | Unsorted | No sort |
| `list_item_relation_links()` | All repos | Unsorted | No sort |
| `list_item_relations()` | Service | Delegates to repo | No sort (will be fixed by repo) |
| `get_items_by_external_id()` | Service | Delegates to repo | No sort (will be fixed by repo) |
| `get_categories_by_external_id()` | Service | Delegates to repo | No sort (will be fixed by repo) |

**Already correct (no change needed)**:

| Method | Layer | Current behavior |
|--------|-------|-----------------|
| `list_categories(parent_id=X)` | Service | Sorts links by `sort_index`, returns items in link order |
| `list_categories(external_id=X)` | Service | Sorts by `category.name` |
| `list_items(category_id=X)` | Service | Sorts links by `sort_index`, returns items in link order |

---

## Finding 4 — Sort Keys Per Method

| Method | Primary sort key | Secondary sort key (tie-breaker) |
|--------|-----------------|----------------------------------|
| `list_categories()` | `category.name` | `category.category_id` |
| `list_items()` | `item.name` | `item.item_id` |
| `list_category_parent_links()` | `link.parent_category_id` | `(link.sort_index, link.category_id)` |
| `list_item_parent_links()` | `link.category_id` | `(link.sort_index, link.item_id)` |
| `list_item_relation_links()` | `link.sort_index` | `(link.source_item_id, link.target_item_id)` |
| `list_items_by_external_id()` | `item.name` | `item.item_id` |
| `list_categories_by_external_id()` | `category.name` | `category.category_id` |

---

## Finding 5 — Where to Apply Sorting (Layer Strategy)

**Decision**: Sort at the **repository layer** for all repository-level methods.

**Rationale**:
- FR-012 mandates this.
- Service-layer methods that delegate directly (`list_item_relations()`,
  `get_items_by_external_id()`, `get_categories_by_external_id()`) get sorted output
  for free without changes to service code.
- Service-layer methods that already sort (the parent-filtered `list_categories()` and
  `list_items()` paths) remain unchanged — their sorting is already correct.
- Sorting at the repo layer also makes raw repo usage correct for direct callers.

**Implementation patterns by adapter**:

- **JSON / YAML repositories**: Pure Python `sorted()` on the returned list.
  ```python
  return sorted(self._categories.values(), key=lambda c: (c.name, c.category_id))
  ```

- **DjangoRepository**: ORM `.order_by()` clause — delegated to DB, efficient.
  ```python
  self._CategoryModel.objects.using(self._using).all().order_by("name", "category_id")
  ```

---

## Finding 6 — Service Layer Changes

**Decision**: No sorting logic changes needed in `TaxomeshService`.

The service's existing sorting (for filtered paths) is correct. The repo-layer fix
propagates automatically to:
- `list_item_relations()` → delegates to `list_item_relation_links()`
- `get_items_by_external_id()` → delegates to `list_items_by_external_id()`
- `get_categories_by_external_id()` → delegates to `list_categories_by_external_id()`

**Protocol docstrings** (`TaxomeshRepositoryBase`) must be updated to document the
ordering contract for each affected method.

---

## Finding 7 — Existing Tests That Exercise Ordering

`tests/service/test_service_reorder_reparent.py` covers `list_items(category_id=X)` and
`list_categories(parent_id=X)` ordering (both already correct). No existing tests cover
unfiltered `list_categories()`, `list_items()`, or any repo-level link listing ordering.
New tests needed for all gaps.

---

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| Sort at service layer only | Breaks raw repo usage; repo results would still be unordered for direct consumers |
| Add `sort_index` field to `Category` and `Item` | Out of scope; requires model change, migration, data backfill |
| Sort in tests only (assert ordering) | Does not fix the actual behavior |
| Sort at call site in callers | Violates DRY; every caller must remember to sort |
