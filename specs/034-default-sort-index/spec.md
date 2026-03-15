# Feature Specification: Default sort_index Ordering for All Collection-Returning Methods

**Feature Branch**: `034-default-sort-index`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "list_item_relation_links() y todos los métodos list (tanto de items, categories, items relacionados a items/categorias, etc) deben ordenarse, por default, por sort_index. Si hay métodos que tengan prefijo get_ pero que también devuelvan listas de items/categories deben hacer lo mismo"

## Clarifications

### Session 2026-03-15

- Q: `Item` has no direct `sort_index` field (confirmed by codebase research). Should unfiltered `list_items()`, `list_items_by_external_id()`, and `get_items_by_external_id()` sort by `item.name`, consistent with the Category fallback decision? → A: Yes — sort by `item.name` (Option A). Consistent with FR-004 category pattern.
- Q: For `list_category_parent_links()` and `list_item_parent_links()` (which return ALL links across ALL parents), should the primary sort group by parent entity first then sort_index within parent, or sort purely by sort_index globally? → A: Group by parent first — sort by `(parent_id, sort_index, child_id)` (Option B).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent Link-List Ordering (Priority: P1)

A developer calls `list_item_relation_links()`, `list_category_parent_links()`, or
`list_item_parent_links()`. The returned list reflects the intentional sort order
defined by the `sort_index` field on each link record, without any additional sorting
code in the caller.

**Why this priority**: Link methods carry an explicit `sort_index` that was introduced
precisely to control display/traversal order. Returning them unsorted defeats that feature.

**Independent Test**: Call any of the three link-list methods on a repository that has
records with non-sequential insertion order; verify the returned list is ordered
ascending by `sort_index`.

**Acceptance Scenarios**:

1. **Given** a repository containing `CategoryParentLink` records spanning two parents (P1 and P2),
   with links inserted in mixed order, **When** `list_category_parent_links()` is called,
   **Then** all links under P1 appear before all links under P2 (ascending by `parent_category_id`),
   and within each parent group links are ordered ascending by `sort_index`.

2. **Given** a repository containing `ItemParentLink` records spanning two categories (C1 and C2),
   with links inserted in mixed order, **When** `list_item_parent_links()` is called,
   **Then** all links under C1 appear before all links under C2 (ascending by `category_id`),
   and within each category group links are ordered ascending by `sort_index`.

3. **Given** a repository containing `ItemRelationLink` records for item X with `sort_index`
   values `[10, 3, 7]`, **When** `list_item_relation_links(item_id=X)` is called (with or
   without `relation_type`/`direction` filters), **Then** the returned list is ordered
   `[3, 7, 10]` by `sort_index`.

---

### User Story 2 - Consistent Category and Item Listing Order (Priority: P1)

A developer calls `list_categories()` or `list_items()` (with or without filters) and
receives results in a predictable, stable order without writing custom sorting code.

**Why this priority**: `list_categories()` and `list_items()` are the primary collection
methods used by callers. Inconsistent ordering produces non-deterministic UIs and broken
tree rendering.

**Independent Test**: Call `list_categories()` and `list_items()` on a repository with
records inserted in non-alphabetical order; verify results come back in alphabetical order
by name (unfiltered), or by `sort_index` via the parent link (filtered).

**Acceptance Scenarios**:

1. **Given** categories named `["Zebra", "Alpha", "Mango"]` inserted in that order,
   **When** `list_categories()` is called with no filter, **Then** results are ordered
   `["Alpha", "Mango", "Zebra"]` by name. (Note: `Category` has no `sort_index` field;
   name is the fallback sort for unfiltered listing.)

2. **Given** `list_categories(parent_id=X)` is called where X has child categories
   with varying `sort_index` on their parent links, **Then** results are ordered ascending
   by `sort_index` of the `CategoryParentLink` joining each child to X.

3. **Given** items named `["Zeta", "Alpha", "Mu"]` inserted in that order,
   **When** `list_items()` is called with no filter, **Then** results are ordered
   `["Alpha", "Mu", "Zeta"]` by name. (Note: `Item` has no `sort_index` field;
   name is the fallback sort for unfiltered listing.)

4. **Given** `list_items(category_id=X)` where X contains items with varying `sort_index`
   on their parent links, **Then** results are ordered ascending by `sort_index` of the
   `ItemParentLink` joining each item to X.

---

### User Story 3 - get_* Collection Methods Also Ordered (Priority: P2)

A developer calls `get_items_by_external_id()` or `get_categories_by_external_id()` and
receives results sorted by name, consistent with the unfiltered `list_*` fallback.

**Why this priority**: These `get_*` methods return lists; inconsistent ordering relative
to `list_*` methods creates surprises for callers.

**Independent Test**: Call `get_items_by_external_id("ext-123")` where multiple items
share that external ID and have names in non-alphabetical order; verify alphabetical order.

**Acceptance Scenarios**:

1. **Given** multiple items share `external_id = "ext-123"` with names `["Zeta", "Alpha"]`
   (in insertion order), **When** `get_items_by_external_id("ext-123")` is called, **Then**
   the returned list is ordered `["Alpha", "Zeta"]` by name.

2. **Given** multiple categories share `external_id = "ext-abc"` with names `["Omega", "Beta"]`
   (in insertion order), **When** `get_categories_by_external_id("ext-abc")` is called,
   **Then** the returned list is ordered `["Beta", "Omega"]` by name.

---

### User Story 4 - Tag Listing (Out of Scope)

`list_tags()` is explicitly excluded from this feature. `Tag` domain objects have no
`sort_index` field and no ordering requirement is introduced here.

**Why this priority**: N/A — out of scope.

**Independent Test**: N/A — out of scope.

**Acceptance Scenarios**:

1. `list_tags()` is out of scope for this feature. `Tag` domain objects do not have a
   `sort_index` field and no ordering requirement is imposed on `list_tags()` by this spec.

---

### Edge Cases

- What happens when two records share the same `sort_index` value? A stable secondary sort
  (ascending by record `id`) MUST be applied to guarantee deterministic output.
- What happens when two items/categories share the same `name`? A stable secondary sort
  ascending by the entity's primary `id` field MUST be applied.
- What happens when a `sort_index` is negative? Negative values are valid and MUST sort
  before non-negative values.
- What happens when the collection is empty? An empty list is returned without error.
- What happens when filtered list methods (e.g., `list_items(category_id=X)`) produce
  zero results? An empty list is returned without error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `list_category_parent_links()` MUST return results ordered by
  `(parent_category_id ASC, sort_index ASC, category_id ASC)` across all repository adapters.
  Links are grouped by parent first, then ordered by `sort_index` within each parent group.

- **FR-002**: `list_item_parent_links()` MUST return results ordered by
  `(category_id ASC, sort_index ASC, item_id ASC)` across all repository adapters.
  Links are grouped by category first, then ordered by `sort_index` within each category group.

- **FR-003**: `list_item_relation_links()` MUST return results ordered ascending by
  `sort_index`, regardless of which `relation_type` or `direction` filters are applied,
  across all repository adapters.

- **FR-004**: `list_categories()` behaviour depends on whether a `parent_id` filter is
  applied:
  - With `parent_id` filter: results MUST be ordered ascending by the `sort_index` of the
    `CategoryParentLink` joining each category to that parent.
  - Without `parent_id` filter: results MUST be ordered ascending alphabetically by category
    name. `Category` has no direct `sort_index` field; name is the defined fallback for
    unfiltered listing. **Decision documented**: chosen because `Category` carries no
    entity-level `sort_index` and name provides a stable, predictable global ordering.

- **FR-005**: `list_items()` behaviour depends on whether a `category_id` filter is applied:
  - With `category_id` filter: results MUST be ordered ascending by the `sort_index` of the
    `ItemParentLink` joining each item to that category.
  - Without `category_id` filter: results MUST be ordered ascending alphabetically by item
    name. `Item` has no direct `sort_index` field; name is the defined fallback for unfiltered
    listing. **Decision documented**: consistent with FR-004 Category pattern; `item.name`
    is the only stable, user-meaningful field available for a global item sort.

- **FR-006**: `list_items_by_external_id()` MUST return results ordered ascending by
  `item.name` across all repository adapters. (`Item` has no `sort_index` field.)

- **FR-007**: `list_categories_by_external_id()` MUST return results ordered ascending by
  `category.name` across all repository adapters. (`Category` has no `sort_index` field.)

- **FR-008**: `TaxomeshService.list_item_relations()` MUST return results ordered
  ascending by `sort_index` (delegates to `list_item_relation_links()`, which is sorted
  at the repository layer).

- **FR-009**: `TaxomeshService.get_items_by_external_id()` MUST return results ordered
  ascending by `item.name` (delegates to `list_items_by_external_id()`, sorted at the
  repository layer).

- **FR-010**: `TaxomeshService.get_categories_by_external_id()` MUST return results ordered
  ascending by `category.name` (delegates to `list_categories_by_external_id()`, sorted at
  the repository layer).

- **FR-011**: When two records share the same primary sort key value (whether `sort_index`
  or `name`), a stable secondary sort ascending by the record's primary `id` field MUST be
  applied to guarantee deterministic output.

- **FR-012**: Sorting MUST be applied at the repository layer for all repository-level
  methods. The service layer MAY additionally enforce ordering on service-level methods
  that aggregate or filter repository results.

- **FR-013**: The Protocol contract (`TaxomeshRepositoryBase`) MUST document in its
  docstrings that all collection-returning methods return results in a defined order
  (by `sort_index` for link entities; by `name` for `Category` and `Item`).

### Key Entities

- **Category**: Domain entity. Has **no** direct `sort_index` field. Sorted by `name`
  for unfiltered listing; sorted by parent-link `sort_index` when filtered by parent.
- **Item**: Domain entity. Has **no** direct `sort_index` field. Sorted by `name`
  for unfiltered listing; sorted by parent-link `sort_index` when filtered by category.
- **Tag**: Domain entity. Has no `sort_index` field. `list_tags()` is out of scope for this feature.
- **CategoryParentLink**: Junction entity with a `sort_index` field controlling display order
  of a category under a specific parent.
- **ItemParentLink**: Junction entity with a `sort_index` field controlling display order of
  an item within a specific category.
- **ItemRelationLink**: Junction entity with a `sort_index` field controlling display order
  of an item-to-item relation.

## Assumptions

- All repository adapters (JsonRepository, YAMLRepository, DjangoRepository) are in scope
  and must implement ordering consistently.
- All three link models (`CategoryParentLink`, `ItemParentLink`, `ItemRelationLink`) have
  `sort_index` fields — no schema changes required.
- `Category` and `Item` domain models have **no** `sort_index` field; `name` is used as
  the fallback sort key for their unfiltered list methods.
- Ordering is ascending (lowest/earliest first). No descending variant is introduced.
- No new `sort_index` parameter is added to any method signature; sorting is a
  non-negotiable default, not a caller option.
- `list_tags()` is out of scope. `Tag` has no `sort_index` field and no ordering
  requirement is imposed on tag listing by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every collection-returning method listed in this spec returns results in the
  defined order (ascending `sort_index` for link entities; ascending `name` for `Category`
  and `Item` unfiltered methods) on all three repository adapters, verified by automated tests.

- **SC-002**: Callers receive stable, reproducible ordering without any change to call
  sites — no new parameters, no changed method signatures.

- **SC-003**: Records with equal primary sort key values are returned in a deterministic order
  (stable secondary sort by primary `id` field), verified by tests with intentional duplicate
  sort key values.

- **SC-004**: All quality gates pass with no regressions: linting, formatting, type
  checking, and test coverage ≥ 80%.
