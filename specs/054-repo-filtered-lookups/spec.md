# Feature Specification: Repository-Level Filtered Lookups

**Feature Branch**: `054-repo-filtered-lookups`
**Created**: 2026-06-05
**Status**: Draft
**Input**: User description: "Repository-level filtered lookups to eliminate full-table scans in TaxomeshService read paths. Four call sites load the whole repo collection and filter in Python. Fix: new port method get_items_by_ids (bulk fetch by internal UUID, mirroring 052) and keyword filters item_id / category_ids on list_item_parent_links, implemented in all four adapters, with the four service call sites updated. No observable behavior change. Finish with version bump and CHANGELOG so letrastango can update its pin."

## Problem Statement

letrastango — the primary consumer of taxomesh, operating at ~7,300 items and
~14,000 item-to-category placement links — profiled cold detail-page renders and
found ~85% of render time (~0.41 s per page in development; multiple seconds in
production) is spent inside `TaxomeshService` read paths. The root cause is a
single bug family repeated at four call sites: the service loads an **entire**
repository collection (all items, or all item-parent links) and filters it in
Python, even when only a handful of records are needed. Every full item load
pays metadata decoding and identifier parsing for all ~7,300 items.

The four affected read paths:

1. **Related-items resolution** (`list_related_items_for_sources`): loads every
   item to build a lookup map, but only needs the items referenced by the
   matched relation links (sources + targets).
2. **Categories-for-item lookup** (`list_categories_by_item`): loads all
   ~14,000 placement links to find those of a single item. The per-item result
   cache means every *new* item repeats the full scan.
3. **Recursive items-in-category** (`_load_item_candidates`, recursive path):
   loads every item **and** every placement link, then filters by a descendant
   category-ID set in Python.
4. **Non-recursive items-in-category** (`list_items` with a category filter):
   loads all placement links to find those of a single category.
   *(Added to scope by explicit user approval — same bug family, same fix.)*

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast related-items resolution (Priority: P1)

A consumer application renders a detail page that shows items related to one or
more source items. Today this loads the entire item collection; after this
feature it loads only the items actually referenced by the matched relation
links. The results — content, grouping, ordering, error behavior, and
dangling-link handling — are exactly the same as before.

**Why this priority**: This is the dominant cost in the profiled detail-page
render (the full item-map build happens here on every cold render).

**Independent Test**: Call `list_related_items_for_sources` against a dataset
with many unrelated items; assert the returned structure is identical to the
previous implementation and that no full item listing is requested from the
repository.

**Acceptance Scenarios**:

1. **Given** a repository with N items where only K (K ≪ N) are referenced by
   relation links of the requested sources, **When**
   `list_related_items_for_sources` is called, **Then** the result is identical
   to the previous implementation and only the referenced items are fetched.
2. **Given** a relation link whose target item does not exist and
   `skip_on_error=True`, **When** the method is called, **Then** the dangling
   link is skipped and a WARNING is logged with the same content semantics as
   before (including the source-item representation).
3. **Given** the same dangling link and `skip_on_error=False`, **When** the
   method is called, **Then** `TaxomeshItemNotFoundError` is raised with an
   unchanged message format.
4. **Given** an empty `source_item_ids` collection, **When** the method is
   called, **Then** `{}` is returned without any repository access.

---

### User Story 2 - Fast categories-for-item lookup (Priority: P1)

A consumer application asks which categories a single item is placed in. Today
this scans every placement link; after this feature the repository returns only
the links of that item. Results, ordering (placement `sort_index` ascending),
enabled-state filtering, and the item-existence check are unchanged.

**Why this priority**: Called on every item detail page; the per-item cache
amplifies the cost because each newly viewed item triggers a full link scan.

**Independent Test**: Call `list_categories_by_item` on a dataset with many
links belonging to other items; assert identical results and that the
repository receives an item-scoped query.

**Acceptance Scenarios**:

1. **Given** an item with M placements among a much larger total link set,
   **When** `list_categories_by_item(item_id)` is called, **Then** exactly the
   same categories in the same `sort_index` order are returned as before.
2. **Given** a non-existent `item_id`, **When** the method is called, **Then**
   `TaxomeshItemNotFoundError` is raised, exactly as before.
3. **Given** placements pointing to disabled categories and `enabled=True`
   (default), **When** the method is called, **Then** disabled categories are
   excluded, exactly as before.

---

### User Story 3 - Fast items-in-category listing, recursive and non-recursive (Priority: P2)

A consumer application lists the items placed in a category — optionally
including all descendant categories. Today both paths scan the full link table
(and the recursive path additionally loads every item); after this feature the
repository returns only the links of the requested category set and only the
matched items are fetched. Result contents, deduplication order, ordering,
enabled filtering, validation errors, and silent skipping of dangling item
references are unchanged.

**Why this priority**: Significant cost on category pages, but less frequent on
the profiled detail-page path than stories 1–2.

**Independent Test**: Call the category-filtered item listing (recursive and
non-recursive) on a dataset where the category subtree holds a small fraction
of all items/links; assert identical results versus the previous
implementation.

**Acceptance Scenarios**:

1. **Given** a category with descendants, **When** the recursive
   items-in-category path runs, **Then** the same deduplicated items in the
   same order (first matching link wins per item) are returned as before.
2. **Given** a placement link whose item no longer exists, **When** the
   recursive path runs, **Then** that link is silently skipped, as before.
3. **Given** a non-existent category, **When** either path runs, **Then**
   `TaxomeshCategoryNotFoundError` is raised, exactly as before.
4. **Given** the non-recursive path (`list_items` with a category filter),
   **When** it runs, **Then** items are returned in placement `sort_index`
   order with unchanged enabled filtering.

---

### User Story 4 - Releasable version for the consumer (Priority: P3)

The letrastango maintainer needs a published version to update the dependency
pin (currently `taxomesh==0.1.0a40`). The release carries a version bump and a
CHANGELOG entry describing the performance fix.

**Why this priority**: Required for the consumer to benefit, but only after the
code changes land.

**Independent Test**: After implementation, the package version is greater than
`0.1.0a41` and the CHANGELOG documents the change.

**Acceptance Scenarios**:

1. **Given** the completed implementation, **When** the release is prepared,
   **Then** the version is bumped from `0.1.0a41` and CHANGELOG gains an entry
   describing the filtered-lookup performance fix.

---

### Edge Cases

- **Empty ID collections**: A bulk item lookup with an empty collection returns
  an empty mapping. A link query with an **empty** `category_ids` collection
  returns an empty list — explicitly *not* the unfiltered listing — to prevent
  accidental full scans. `None` (the default) means "no filter".
- **Both link filters supplied**: `item_id` and `category_ids` together apply
  AND semantics.
- **Missing IDs in bulk lookup**: silently absent from the result mapping —
  never an error (mirrors the established external-ID bulk lookup contract).
- **Duplicate IDs in bulk lookup input**: the caller (service) deduplicates;
  adapters perform no further normalisation (mirrors 052).
- **Ordering under filtering**: the link-listing ordering contract
  (`category_id ASC, sort_index ASC, item_id ASC`) holds for filtered results
  exactly as for unfiltered ones.
- **Storage failure**: bulk and filtered queries raise
  `TaxomeshRepositoryError` on storage failure, like all other repository
  operations.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository port MUST provide a bulk item lookup by internal
  identifier — `get_items_by_ids(item_ids, *, enabled=None)` — returning a
  mapping of found `item_id → Item`; missing IDs are silently absent; an empty
  input returns an empty mapping; the `enabled` tri-state (`True`/`False`/
  `None`) filters by enabled state. The contract mirrors feature 052's
  `get_items_by_external_ids` (pre-normalised input, no adapter-side
  normalisation, `TaxomeshRepositoryError` on storage failure).
- **FR-002**: The repository port's `list_item_parent_links` MUST accept
  optional keyword filters `item_id` (single ID) and `category_ids`
  (collection). `None` for both ⇒ identical to current unfiltered behavior;
  both supplied ⇒ AND semantics; empty `category_ids` collection ⇒ empty list.
  The existing ordering contract is preserved under all filter combinations.
- **FR-003**: All four adapters — `JsonRepository`, `YAMLRepository`,
  `DjangoRepository`, `InMemoryRepository` — MUST implement FR-001 and FR-002.
  `DjangoRepository` MUST push the filters into the database query (no
  client-side filtering of a full result set).
- **FR-004**: `list_related_items_for_sources` MUST build its item lookup map
  from only the item IDs referenced by the matched relation links (all source
  IDs and all target IDs), via the FR-001 bulk lookup, instead of listing all
  items. `skip_on_error` semantics, WARNING log content semantics (including
  source-item representation), the `TaxomeshItemNotFoundError` message format,
  result grouping, and ordering MUST be unchanged.
- **FR-005**: `list_categories_by_item` MUST obtain only the links of the
  requested item via the FR-002 `item_id` filter instead of scanning all
  links. Item-existence validation, result ordering, and `enabled` filtering
  MUST be unchanged.
- **FR-006**: The recursive items-in-category path MUST obtain only the links
  of the computed category-ID set via the FR-002 `category_ids` filter, and
  fetch only the matched items via the FR-001 bulk lookup. Deduplication order
  (first link wins per item), silent skipping of dangling item references,
  and category-existence validation MUST be unchanged.
- **FR-007**: The non-recursive category-filtered item listing MUST obtain only
  the links of the requested category via the FR-002 `category_ids` filter.
  Category-existence validation, `sort_index` ordering, and `enabled`
  filtering MUST be unchanged.
- **FR-008**: No observable behavior change at any of the four call sites:
  identical results, identical ordering, identical exceptions and messages,
  identical logging semantics, for all repository backends.
- **FR-009**: The package version MUST be bumped (from `0.1.0a41`) and the
  CHANGELOG MUST gain an entry describing the change, so the consumer can
  update its dependency pin.

### Key Entities

- **Item**: a tagged, categorizable record; looked up in bulk by its internal
  identifier (new) in addition to existing single and external-ID lookups.
- **ItemParentLink**: an item→category placement carrying `sort_index`; now
  queryable by owning item or by a set of categories at the repository level.
- **Repository port (`TaxomeshRepositoryBase`)**: the pluggable storage
  contract gaining one new method and two optional filters on an existing
  method.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a consumer-shaped dataset (~7,300 items / ~14,000 placement
  links), none of the four read paths requests the full item collection or the
  full link collection from the repository (verifiable by observing repository
  calls in tests).
- **SC-002**: Parity tests prove identical results (content + order) for all
  four read paths against all four storage backends, before vs. after.
- **SC-003**: All existing tests continue to pass with zero modifications to
  expected outputs; overall coverage remains ≥ 80%; linting, formatting, and
  strict type checking pass.
- **SC-004**: Cold detail-page render cost attributable to these read paths
  drops proportionally to the selectivity of the queries (in the consumer's
  profile, the ~85% full-scan share is eliminated; repository work scales with
  the number of matched records, not table size).
- **SC-005**: A new published version (> `0.1.0a41`) with a CHANGELOG entry is
  available for the consumer to pin.

## Assumptions

- The name `get_items_by_ids` and its mapping return shape were delegated to
  the implementer and chosen to mirror feature 052's bulk external-ID lookup.
- The keyword-filter shape for `list_item_parent_links` (vs. dedicated methods)
  was explicitly approved by the user, as was including the fourth call site.
- No new database indexes are needed: features 032/035 already cover the
  relevant columns.
- Out of scope: caching changes, Django admin, CLI, contrib API, pagination,
  new indexes.
