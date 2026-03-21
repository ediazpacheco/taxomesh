# Feature Specification: Item-to-Categories Lookup

**Feature Branch**: `045-item-categories-lookup`
**Created**: 2026-03-21
**Status**: Draft

## Overview

Add a public API to TaxomeshService that answers the question *"which categories does this item belong to?"*, returning them in their configured display order. This closes the only missing traversal direction in the service layer and eliminates the need for consuming applications to reach down to storage internals.

## Motivation

TaxomeshService already supports the forward traversal:

- **Category → Items**: `list_items(category_id=...)`

But it does not expose the inverse:

- **Item → Categories**: *(currently missing)*

Without this, applications that need to know a given item's categorical placement — for example, to build breadcrumb navigation, canonical URLs, or location-aware rendering — must bypass the service and query storage directly. This couples consumers to internal models, breaks the intended encapsulation, and means any change to storage layout can silently break those consumers.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Resolve item placement from the service (Priority: P1)

A developer building a content page needs to know which categories a given item belongs to, without importing or querying internal storage models directly.

**Why this priority**: This is the entire deliverable of the feature. Without it, no other story has value.

**Independent Test**: Create an item, place it in one or more categories, call `list_categories_by_item(item_id)`, verify the returned list contains the correct categories in sort order.

**Acceptance Scenarios**:

1. **Given** an item that belongs to exactly one category, **when** `list_categories_by_item(item_id)` is called, **then** a list containing that single category is returned.
2. **Given** an item that belongs to multiple categories with different sort positions, **when** `list_categories_by_item(item_id)` is called, **then** all categories are returned, ordered from lowest to highest sort index.
3. **Given** an item that has been placed in a category and subsequently removed from it, **when** `list_categories_by_item(item_id)` is called, **then** that category is no longer included in the result.

---

### User Story 2 — Handle items with no categorical placement (Priority: P2)

A developer calls `list_categories_by_item` on an item that exists but has not yet been assigned to any category.

**Why this priority**: This is a legitimate and expected state — new items may not be categorised immediately. The API must handle it gracefully.

**Independent Test**: Create an item without placing it in any category, call `list_categories_by_item(item_id)`, verify an empty list is returned.

**Acceptance Scenarios**:

1. **Given** an item that has never been placed in any category, **when** `list_categories_by_item(item_id)` is called, **then** an empty list is returned.

---

### User Story 3 — Reject lookup for non-existent items (Priority: P2)

A developer calls `list_categories_by_item` with an item ID that does not exist in the system.

**Why this priority**: Silent failures on unknown entities violate the library's error contract. Callers must receive a clear signal.

**Independent Test**: Call `list_categories_by_item` with a fabricated UUID that has never been created; verify the appropriate error is raised.

**Acceptance Scenarios**:

1. **Given** an item ID that does not correspond to any known item, **when** `list_categories_by_item(item_id)` is called, **then** `TaxomeshItemNotFoundError` is raised.

---

### User Story 4 — Include disabled categories in structural reads (Priority: P3)

A developer calls `list_categories_by_item` when one of the item's categories has been disabled.

**Why this priority**: This is a deliberate design choice — the method performs a structural graph read, not a filtered display query. Filtering by enabled state is the consumer's responsibility.

**Independent Test**: Place an item in a category, disable the category, call `list_categories_by_item(item_id)`, verify the disabled category is still returned.

**Acceptance Scenarios**:

1. **Given** an item that belongs to a category which has been disabled, **when** `list_categories_by_item(item_id)` is called, **then** the disabled category is still returned in the result list.

---

### Edge Cases

- What happens when the same item is placed in the same category multiple times? The item appears in that category exactly once (deduplication is handled by existing placement semantics).
- What happens when the sort index values are identical across multiple categories? The relative order of same-index categories is unspecified and should not be relied upon by callers.
- What happens when the item ID is valid but of the wrong type? A validation error is raised before any lookup is attempted.
- What happens when placement and removal operations are interleaved rapidly? The method always reflects the current committed state at the time it is called.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST expose a public method `list_categories_by_item(item_id)` that accepts a single item identifier and returns a list of categories.
- **FR-002**: The returned list MUST be ordered by the sort position of the item-to-category link, from lowest to highest.
- **FR-003**: If the item does not exist, the method MUST raise `TaxomeshItemNotFoundError`.
- **FR-004**: If the item exists but has no category placement, the method MUST return an empty list.
- **FR-005**: Disabled categories MUST be included in the result; the method MUST NOT filter by enabled state.
- **FR-006**: The method result MUST be subject to the same read-cache TTL as all other service read methods.
- **FR-007**: The cache entry for a given item MUST be invalidated whenever the item is placed into a category, removed from a category, or the sort order of its links is updated.
- **FR-008**: The method signature and behaviour MUST be consistent across all supported storage backends (JSON file, YAML file, Django ORM, in-memory).
- **FR-009**: The method MUST be documented with a docstring covering: input, output, sort order guarantee, and the deliberate choice not to filter by enabled state.
- **FR-010**: All user-facing documentation (README public API section) MUST be updated to include this method.
- **FR-011**: A changelog entry MUST be added describing the new method and its behaviour.

### Key Entities

- **Item**: An entity managed by the taxonomy service, identified by a UUID. Has zero or more category placements.
- **Category**: A node in the taxonomy DAG, identified by a UUID. May be enabled or disabled.
- **Item-Category Link**: The association between an item and a category, carrying a sort index that determines display order. This is the structural record that drives the lookup.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Calling `list_categories_by_item` with a valid item ID returns all and only the categories that item belongs to, verified across all supported storage backends.
- **SC-002**: Categories in the returned list are in ascending sort-index order in 100% of test cases.
- **SC-003**: Calling `list_categories_by_item` with a non-existent item ID raises `TaxomeshItemNotFoundError` in 100% of test cases.
- **SC-004**: No consuming application needs to import or query any storage model directly to resolve an item's category placement — this lookup is fully satisfied by `TaxomeshService`.
- **SC-005**: All existing quality gates (linting, formatting, type checking, test coverage ≥ 80%) continue to pass after this feature is merged.
- **SC-006**: The new method has test coverage across at minimum: empty result, single category, multiple categories (sort order verified), not-found error, and disabled-category passthrough.

---

## Assumptions

- `list_item_parent_links()` is confirmed present in all supported repository backends (`TaxomeshRepositoryBase` protocol, `JsonRepository`, `YAMLRepository`, `DjangoRepository`, and `InMemoryRepository` test fixture).
- The cache invalidation mechanism (`clear_all_caches()`) already covers write operations (`place_item_in_category`, `remove_item_from_category`); this feature does not need to introduce a new invalidation mechanism.
- "Sort index" refers to the integer field already present on the item-to-category link model, as used by drag-and-drop ordering (spec 030).
- The minimum deliverable is `list_categories_by_item`; related traversals (e.g. `list_parent_categories`, `get_category_path`) are explicitly out of scope for this feature.

---

## Out of Scope

- `list_parent_categories(category_id)` — resolving category ancestry upward.
- `get_category_path(category_id)` — building breadcrumb/navigation paths.
- Any changes to how items are placed in or removed from categories.
- Filtering results by `enabled` state — that responsibility stays with the consumer.
- Exposing this method via the HTTP contrib handlers (can be a follow-up).
