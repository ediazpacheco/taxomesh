# Feature Specification: Service Slug Lookup Methods

**Feature Branch**: `020-slug-lookup`
**Created**: 2026-03-02
**Status**: Implemented
**Input**: User description: "Add TaxomeshService.get_category_by_slug(slug: str) -> Category and TaxomeshService.get_item_by_slug(slug: str) -> Item methods. These methods look up a Category or Item by their slug field and return the matching domain object, raising an appropriate error if not found."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Look Up Category by Slug (Priority: P1)

A developer has a slug string (e.g. from a URL path segment) and needs to retrieve the
corresponding Category domain object. They call `service.get_category_by_slug("my-slug")`
and receive the Category directly, or get a clear error if no category holds that slug.

**Why this priority**: This is half of the feature's stated goal. Slug-based lookup is the
primary use case — it is more natural for URL-driven code than UUID-based lookup.

**Independent Test**: Can be fully tested by creating a category with a known slug,
calling `get_category_by_slug` with that slug, and asserting the returned Category matches.

**Acceptance Scenarios**:

1. **Given** a category with `slug="electronics"` exists in the repository,
   **When** `service.get_category_by_slug("electronics")` is called,
   **Then** the matching Category is returned.

2. **Given** no category with `slug="does-not-exist"` exists,
   **When** `service.get_category_by_slug("does-not-exist")` is called,
   **Then** `TaxomeshCategoryNotFoundError` is raised.

3. **Given** a category with `slug="electronics"` exists,
   **When** `get_category_by_slug("electronics")` is called twice in rapid succession,
   **Then** both calls return the same Category object (result is served from cache on the second call).

---

### User Story 2 - Look Up Item by Slug (Priority: P1)

A developer has a slug string and needs to retrieve the corresponding Item domain object.
They call `service.get_item_by_slug("my-item-slug")` and receive the Item directly,
or get a clear error if no item holds that slug.

**Why this priority**: Symmetric to the category lookup; equally central to the feature.
Both lookups form a single coherent addition to the service API.

**Independent Test**: Can be fully tested by creating an item with a known slug,
calling `get_item_by_slug` with that slug, and asserting the returned Item matches.

**Acceptance Scenarios**:

1. **Given** an item with `slug="product-42"` exists in the repository,
   **When** `service.get_item_by_slug("product-42")` is called,
   **Then** the matching Item is returned.

2. **Given** no item with `slug="unknown-slug"` exists,
   **When** `service.get_item_by_slug("unknown-slug")` is called,
   **Then** `TaxomeshItemNotFoundError` is raised.

3. **Given** an item with `slug="product-42"` exists,
   **When** `get_item_by_slug("product-42")` is called twice in rapid succession,
   **Then** both calls return the same Item object (result is served from cache on the second call).

---

### Edge Cases

- What happens when an empty string is passed as slug?
  No entity is ever persisted with an empty slug, so the repository returns `None`
  and the service raises `TaxomeshCategoryNotFoundError` / `TaxomeshItemNotFoundError`.

- What happens if multiple entities share the same slug?
  Slugs are enforced as unique at write time (`TaxomeshDuplicateSlugError`); no two
  categories (or items) can share a slug. The lookup is therefore always unambiguous.

- Does slug lookup ever return the root category?
  The root category carries an empty slug (`""`). The service filters it out — if the
  repository returns the root category for a slug query, the service treats the result as
  not found and raises `TaxomeshCategoryNotFoundError`. This guard is required because
  an empty-slug query would otherwise match the root.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `TaxomeshService` MUST expose a `get_category_by_slug(slug: str) -> Category`
  method that delegates to the repository and returns the matching Category.

- **FR-002**: `TaxomeshService` MUST expose a `get_item_by_slug(slug: str) -> Item`
  method that delegates to the repository and returns the matching Item.

- **FR-003**: `get_category_by_slug` MUST raise `TaxomeshCategoryNotFoundError` when
  no category with the given slug exists in the repository.

- **FR-004**: `get_item_by_slug` MUST raise `TaxomeshItemNotFoundError` when
  no item with the given slug exists in the repository.

- **FR-005**: Both methods MUST apply the same TTL-based memoisation as `get_category`
  and `get_item` to maintain consistent caching behaviour across the service.

- **FR-006**: Neither method modifies any repository state; they are read-only operations.

### Key Entities

- **Category**: Domain model with a `slug` field. Slugs are unique within the category
  namespace (enforced at write time).
- **Item**: Domain model with a `slug` field. Slugs are unique within the item namespace
  (enforced at write time).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can retrieve a Category or Item by slug in a single method call
  without manually iterating over all entities.

- **SC-002**: Calling either method with a non-existent slug always results in a typed
  not-found exception, never a `None` return or an untyped exception.

- **SC-003**: All existing quality gates continue to pass after the addition
  (linting, formatting, strict type checking, test coverage ≥ 80 %).

- **SC-004**: The new methods are covered by dedicated unit tests that exercise
  both the found and not-found paths for each method.

## Assumptions

- The repository protocol already exposes `get_category_by_slug` and `get_item_by_slug`
  as nullable lookups. The service layer adds not-found error raising on top.
- No new repository method or migration is required; this feature adds only two service-layer methods.
- Memoisation is applied consistently with the existing `get_category` and `get_item` methods.
