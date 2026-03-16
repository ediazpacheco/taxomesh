# Feature Specification: HTTP Search Support for contrib.api

**Feature Branch**: `037-contrib-api-search`
**Created**: 2026-03-15
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Search Items via HTTP (Priority: P1)

An HTTP consumer sends a search query with optional filters (category scope, enabled-only flag, fuzzy toggle) and receives a ranked list of matching items serialized as a plain JSON-friendly structure, ready to embed in any HTTP response.

**Why this priority**: Item search is the most frequent discovery operation. Consumers need to autocomplete, filter, and rank items without knowing internal UUIDs up front.

**Independent Test**: Can be fully tested by calling `search_items(service, SearchItemsRequest(q="tango"))` and asserting it returns a list of `Item` domain objects that match the query.

**Acceptance Scenarios**:

1. **Given** a service with items in the repository and a `SearchItemsRequest(q="troilo")`, **When** `search_items(service, params)` is called, **Then** a list of `Item` objects ranked by relevance is returned.
2. **Given** a `SearchItemsRequest(q="troilo", enabled_only=True)`, **When** `search_items` is called, **Then** only enabled items appear in the result.
3. **Given** a `SearchItemsRequest(q="troilo", category_id=<uuid>, recursive=True)`, **When** `search_items` is called, **Then** only items placed in that category or its descendants are considered.
4. **Given** a `SearchItemsRequest(q="troilo", limit=5)`, **When** `search_items` is called, **Then** at most 5 items are returned.
5. **Given** a `SearchItemsRequest(q="troilo", fuzzy=False)`, **When** `search_items` is called, **Then** the result is produced using exact/substring matching only.
6. **Given** a `SearchItemsRequest(q="")` (blank query), **When** `search_items` is called, **Then** an empty list is returned.
7. **Given** a `SearchItemsRequest(q="troilo", category_id=<nonexistent-uuid>)`, **When** `search_items` is called, **Then** a `TaxomeshCategoryNotFoundError` propagates to the caller.

---

### User Story 2 - Search Categories via HTTP (Priority: P2)

An HTTP consumer sends a search query with optional filters (parent scope, enabled-only flag, fuzzy toggle) and receives a ranked list of matching categories ready for embedding in any HTTP response.

**Why this priority**: Category search enables navigation and autocomplete for taxonomy management UIs. It mirrors the item search contract, so parity matters for a consistent API surface.

**Independent Test**: Can be fully tested by calling `search_categories(service, SearchCategoriesRequest(q="tango"))` and asserting it returns a list of `Category` domain objects.

**Acceptance Scenarios**:

1. **Given** a service with categories and a `SearchCategoriesRequest(q="jazz")`, **When** `search_categories(service, params)` is called, **Then** a ranked list of matching `Category` objects is returned.
2. **Given** a `SearchCategoriesRequest(q="jazz", enabled_only=True)`, **When** `search_categories` is called, **Then** only enabled categories appear.
3. **Given** a `SearchCategoriesRequest(q="jazz", parent_id=<uuid>)`, **When** `search_categories` is called, **Then** only direct children of that parent are considered.
4. **Given** a `SearchCategoriesRequest(q="jazz", limit=3)`, **When** `search_categories` is called, **Then** at most 3 categories are returned.
5. **Given** a `SearchCategoriesRequest(q="")` (blank query), **When** `search_categories` is called, **Then** an empty list is returned.

---

### User Story 3 - Serialize Search Results to JSON-friendly Lists (Priority: P3)

A consumer converts a list of `Item` or `Category` domain objects returned by the search handlers into plain, JSON-serializable dicts for inclusion in an HTTP response body.

**Why this priority**: Serialization is a required step before any HTTP layer can emit the results, but it carries no business logic. The value is completeness of the API surface.

**Independent Test**: Can be fully tested by calling `items_to_list([item1, item2])` and asserting each entry is a plain dict with the expected fields (item_id, name, slug, external_id, enabled, metadata).

**Acceptance Scenarios**:

1. **Given** a non-empty list of `Item` objects, **When** `items_to_list(items)` is called, **Then** a list of plain dicts is returned, each containing at minimum: `item_id`, `name`, `slug`, `external_id`, `enabled`, `metadata`.
2. **Given** an empty list, **When** `items_to_list([])` is called, **Then** an empty list is returned.
3. **Given** a non-empty list of `Category` objects, **When** `categories_to_list(categories)` is called, **Then** a list of plain dicts is returned, each containing at minimum: `category_id`, `name`, `slug`, `external_id`, `enabled`, `metadata`.
4. **Given** fields containing UUID values, **When** serialized, **Then** UUIDs are represented as strings (JSON-compatible).

---

### Edge Cases

- What happens when `q` contains only whitespace? The service returns an empty list; the handler returns it unchanged.
- What happens when `limit` is 0 or negative? The service raises `ValueError`; the handler propagates it to the caller without catching.
- What happens when `category_id` / `parent_id` refers to a non-existent entity? `TaxomeshCategoryNotFoundError` propagates unchanged.
- What happens when the repository contains no items/categories? An empty list is returned without error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide a `SearchItemsRequest` schema with fields: `q` (str, required), `limit` (int, default 20), `category_id` (UUID or None, default None), `recursive` (bool, default False), `enabled_only` (bool, default True), `fuzzy` (bool, default True).
- **FR-002**: The library MUST provide a `SearchCategoriesRequest` schema with fields: `q` (str, required), `limit` (int, default 20), `parent_id` (UUID or None, default None), `enabled_only` (bool, default True), `fuzzy` (bool, default True).
- **FR-003**: The library MUST provide a `search_items(service, params)` handler that delegates 1:1 to `service.search_items()` using all fields from `SearchItemsRequest` and returns `list[Item]`.
- **FR-004**: The library MUST provide a `search_categories(service, params)` handler that delegates 1:1 to `service.search_categories()` using all fields from `SearchCategoriesRequest` and returns `list[Category]`.
- **FR-005**: The handlers MUST NOT add any ranking, scoring, or filtering logic of their own; all business logic resides in the service.
- **FR-006**: The library MUST provide an `items_to_list(items)` serializer that converts `list[Item]` to `list[dict[str, Any]]` using `model_dump(mode="json")`.
- **FR-007**: The library MUST provide a `categories_to_list(categories)` serializer that converts `list[Category]` to `list[dict[str, Any]]` using `model_dump(mode="json")`.
- **FR-008**: All exceptions raised by the service (e.g., `TaxomeshCategoryNotFoundError`, `ValueError` for invalid limit) MUST propagate to the caller without being caught or wrapped by the handlers.
- **FR-009**: The new schemas MUST be importable from `taxomesh.contrib.api.schemas`.
- **FR-010**: The new handlers MUST be importable from `taxomesh.contrib.api.handlers`.
- **FR-011**: The new serializers MUST be importable from `taxomesh.contrib.api.serializers`.

### Key Entities

- **SearchItemsRequest**: A validated request object encapsulating all search parameters for items. Fields map directly to `TaxomeshService.search_items()` keyword arguments.
- **SearchCategoriesRequest**: A validated request object encapsulating all search parameters for categories. Fields map directly to `TaxomeshService.search_categories()` keyword arguments.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Calling `search_items` with a valid query returns only `Item` objects that the underlying service would return — no additions, omissions, or reordering introduced by the handler layer.
- **SC-002**: Calling `search_categories` with a valid query returns only `Category` objects the service would return — with identical ordering and count.
- **SC-003**: `items_to_list` and `categories_to_list` produce dicts where every UUID field is a string and every value is JSON-serializable without further transformation.
- **SC-004**: All new public callables are covered by unit tests and all existing quality gates (lint, type checks, coverage ≥ 80%) continue to pass.
- **SC-005**: A consumer can import schemas, handlers, and serializers from a single, stable public path without importing internal service modules directly.

## Assumptions

- `service.search_items()` and `service.search_categories()` already exist with the exact signatures observed in `taxomesh/application/service.py` (spec 033-fuzzy-search). No changes to the service are required.
- The `q` field in the request schemas is not validated for minimum length; an empty `q` simply results in an empty list (consistent with service behavior).
- `limit` validation (must be ≥ 1) is enforced entirely by the service; the schema accepts any `int`.
- The serializers produce the full model dump of each domain object; no field whitelisting or projection is applied.
- The `SearchItemsRequest` and `SearchCategoriesRequest` schemas do not need to be Pydantic models — plain dataclasses would suffice — but for consistency with the existing `schemas.py` conventions, Pydantic `BaseModel` is the assumed implementation approach.
