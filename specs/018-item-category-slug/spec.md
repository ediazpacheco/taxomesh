# Feature Specification: Item & Category Slug Field

**Feature Branch**: `018-item-category-slug`
**Created**: 2026-03-01
**Status**: Draft
**Input**: Add `slug` as a first-class optional field to Item and Category domain models, with uniqueness enforcement, canonical __str__ format, CLI graph rendering, and Django admin integration.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Assign a Slug to a Category (Priority: P1)

An operator creating a new category wants to give it a short, URL-friendly identifier so that the category can be referenced in links and admin interfaces by a human-readable key rather than a UUID.

**Why this priority**: Slug is the core deliverable. All other stories depend on the field existing on the domain model.

**Independent Test**: Create a category with `slug="electronics"`, retrieve it, and confirm the slug is stored and returned correctly.

**Acceptance Scenarios**:

1. **Given** no categories exist, **When** a category is created with `slug="books"`, **Then** the category is persisted with `slug="books"` and the field is readable on the returned object.
2. **Given** a category exists with `slug="books"`, **When** a second category creation is attempted with `slug="books"`, **Then** a `TaxomeshDuplicateSlugError` is raised and no second category is created.
3. **Given** two categories, **When** both are created with `slug=""`, **Then** both succeed — empty string is not subject to uniqueness.
4. **Given** a category with `slug="books"`, **When** that category is updated with `slug="books"` (same value), **Then** no error is raised and the slug is retained.
5. **Given** a category with `slug="books"`, **When** updated with `slug=""`, **Then** the slug is cleared and no uniqueness conflict is raised.

---

### User Story 2 — Assign a Slug to an Item (Priority: P1)

An operator creating or updating an item wants to attach a stable, human-readable slug so that the item can be identified in URLs and logs without using the internal UUID.

**Why this priority**: Symmetric with category slug; both entity types need the feature equally.

**Independent Test**: Create an item with `slug="iphone-15"`, verify it is stored; attempt to create a second item with the same slug and confirm the error.

**Acceptance Scenarios**:

1. **Given** no items exist, **When** an item is created with `slug="iphone-15"`, **Then** the item is persisted with `slug="iphone-15"`.
2. **Given** an item with `slug="iphone-15"`, **When** a second item creation uses `slug="iphone-15"`, **Then** `TaxomeshDuplicateSlugError` is raised.
3. **Given** two items, **When** both are created with `slug=""`, **Then** both succeed.
4. **Given** an item with `slug="a"`, **When** updated with `slug="b"` (where `"b"` is not taken), **Then** the slug is updated successfully.
5. **Given** item A with `slug="a"` and item B with `slug="b"`, **When** item B is updated to take `slug="a"`, **Then** `TaxomeshDuplicateSlugError` is raised.

---

### User Story 3 — Human-Readable String Representation (Priority: P2)

A developer or operator inspecting an item or category object (in logs, admin dropdowns, or the CLI) sees a consistent, informative string that leads with the slug when present, then the UUID, then the external ID.

**Why this priority**: Improves debuggability everywhere objects are printed or logged; depends on the field existing (Story 1/2).

**Independent Test**: Construct a Category and Item with and without slugs and assert the exact `str()` output matches the canonical format.

**Acceptance Scenarios**:

1. **Given** a Category with `slug="books"`, **When** `str(category)` is called, **Then** the output is `"Books (s: books - id: {category_id})"`.
2. **Given** a Category with `slug=""`, **When** `str(category)` is called, **Then** the output is `"Books (id: {category_id})"` — name always shown, no slug segment when slug is empty.
3. **Given** an Item with `slug="iphone"` and `external_id="sku-001"`, **When** `str(item)` is called, **Then** the output is `"iphone ({item_id}) -> sku-001"`.
4. **Given** an Item with `slug=""`, **When** `str(item)` is called, **Then** the output starts with `"("` — no slug prefix.

---

### User Story 4 — CLI Graph Renders Slug with UUID (Priority: P2)

An operator running `taxomesh graph` wants to see the slug alongside the UUID in the tree output so they can quickly identify categories and items by their human-readable slug.

**Why this priority**: Enhances the existing graph command output; depends on the slug field.

**Independent Test**: Build a graph with a category and item that have slugs, render it, and confirm the slug appears before the UUID in the output.

**Acceptance Scenarios**:

1. **Given** a category with `slug="electronics"`, **When** the graph is rendered, **Then** the category row shows `"electronics (uuid)"` in the identifier segment.
2. **Given** a category with `slug=""`, **When** the graph is rendered, **Then** only the raw UUID is shown (no slug prefix, no parentheses around UUID).
3. **Given** an item with `slug="phone"`, **When** the graph is rendered, **Then** the item row shows `"phone (uuid)"` in the identifier segment.

---

### User Story 5 — Django Admin Shows and Persists Slug (Priority: P3)

An admin user managing categories and items via the Django admin interface sees a `slug` column in the list view and can set/edit the slug through the standard form, with duplicate validation surfaced as a user-facing error.

**Why this priority**: Admin integration is secondary to the domain and CLI work; depends on Stories 1–3.

**Independent Test**: In the Django admin, create a category with a slug, save it, and confirm the slug appears in the list and is stored via the service layer.

**Acceptance Scenarios**:

1. **Given** the Django admin category list, **When** it is loaded, **Then** the `slug` column is visible.
2. **Given** a category form in admin, **When** a slug is entered and saved, **Then** the service layer `create_category(slug=...)` is called and the slug is persisted.
3. **Given** an existing category with a non-empty slug, **When** an admin user tries to save another category with the same slug, **Then** a validation error is displayed and the save is rejected.

---

### Edge Cases

- A slug with 256 characters (maximum length) must be accepted; a slug with 257 characters must be rejected at the domain model level.
- `slug=""` (empty string) is the canonical "no slug" value — it is never subject to uniqueness. Multiple items or categories may share `slug=""`.
- Slug uniqueness is per entity type: an item and a category may share the same non-empty slug without conflict.
- Updating an entity's slug to its own current slug must not raise a duplicate error (same-entity self-assign).
- Updating an entity's slug to `""` (clearing it) must always succeed, even if another entity holds the same non-empty slug.
- A slug lookup (`get_item_by_slug`, `get_category_by_slug`) for a slug that does not exist must return `None`, not raise an error.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both `Item` and `Category` domain models MUST expose a `slug` field (string, max 256 chars, default `""`).
- **FR-002**: An empty slug (`""`) MUST NOT be subject to uniqueness enforcement — many entities may share `slug=""`.
- **FR-003**: A non-empty slug MUST be unique within its entity type (items separate from categories). Attempting to create or update an entity with a slug already held by a different entity of the same type MUST raise `TaxomeshDuplicateSlugError`.
- **FR-004**: `TaxomeshDuplicateSlugError` MUST be a subclass of `TaxomeshValidationError`, preserving the existing exception hierarchy.
- **FR-005**: `str(Item)` MUST return `"{slug} ({item_id}) -> {external_id}"` when `slug` is non-empty; `"({item_id}) -> {external_id}"` when `slug` is `""`.
- **FR-006**: `str(Category)` MUST return `"{name} (s: {slug} - id: {category_id})"` when `slug` is non-empty; `"{name} (id: {category_id})"` when `slug` is `""`. The category name is always included; `external_id` is not part of the string representation.
- **FR-007**: The `create_category(slug="")` and `update_category(slug=None)` service methods MUST accept an optional slug parameter and enforce uniqueness before persisting.
- **FR-008**: The `create_item(slug="")` and `update_item(slug=None)` service methods MUST accept an optional slug parameter and enforce uniqueness before persisting.
- **FR-009**: All repository implementations (JSON, YAML, Django ORM) MUST persist and retrieve the slug field without data loss.
- **FR-010**: All repository implementations MUST expose `get_item_by_slug(slug: str) -> Item | None` and `get_category_by_slug(slug: str) -> Category | None` lookup methods.
- **FR-011**: The CLI graph command MUST render the identifier segment as `"slug (uuid)"` when slug is non-empty, and as `"uuid"` when slug is `""`.
- **FR-012**: The Django admin `CategoryModel` and `ItemModel` list views MUST include a `slug` column.
- **FR-013**: Django admin `save_model` for categories and items MUST pass the slug value through the service layer (not bypass it via direct ORM writes).
- **FR-014**: The Django ORM migration (`0001_initial`) MUST include the `slug` field with a partial unique constraint (`slug != ""`) on both `taxomesh_category` and `taxomesh_item` tables.
- **FR-015**: The `slug` field MUST be indexed in the database (both Django ORM and any file-based repository support fast lookup by slug).
- **FR-016**: The CLI `category add`, `category update`, `item add`, and `item update` commands MUST accept an optional `--slug` argument wired through to the corresponding service method.

### Key Entities

- **Item**: Gains a `slug` attribute (string, max 256 chars, default `""`). Slug uniqueness is enforced per item namespace.
- **Category**: Gains a `slug` attribute (string, max 256 chars, default `""`). Slug uniqueness is enforced per category namespace.
- **TaxomeshDuplicateSlugError**: New exception in the `TaxomeshValidationError` hierarchy. Raised when a non-empty slug conflicts with an existing entity of the same type.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A slug can be assigned, stored, and retrieved on both Item and Category across all three storage backends (JSON, YAML, Django ORM) with no data loss.
- **SC-002**: Attempting to create or update two entities of the same type with an identical non-empty slug raises `TaxomeshDuplicateSlugError` 100% of the time, with no silent failures.
- **SC-003**: Two entities of the same type can both hold `slug=""` without any uniqueness error — empty slug is never rejected.
- **SC-004**: The canonical `str()` output for Item and Category matches the specified format in all cases: Category always shows name and UUID, with slug segment present only when non-empty; Item always shows UUID and external_id, with slug prefix only when non-empty.
- **SC-005**: The CLI graph output shows `slug (uuid)` for entities with a non-empty slug, and bare `uuid` for entities without a slug — verified in automated tests.
- **SC-006**: All existing tests continue to pass with no regressions after the slug field is introduced (backward-compatible default `""`).
- **SC-007**: Test coverage for the `taxomesh` package remains at or above 80% after the changes.

---

## Assumptions

- Slug format validation (e.g., restricting to URL-safe characters) is intentionally out of scope for this feature. Any non-empty string up to 256 chars is accepted.
- Slug values are case-sensitive: `"Books"` and `"books"` are treated as distinct slugs.
- Slug uniqueness is not enforced across entity types: an Item and a Category may share the same non-empty slug without conflict.
- The project has not shipped to production, so the DB migration is edited in-place (`0001_initial`) rather than adding a new migration.
- File-based repositories (JSON, YAML) achieve "indexing" through linear scan (`O(n)`), which is acceptable at the expected data volumes for a local taxonomy tool.

---

## Out of Scope

- Slug format/pattern validation (URL-safety, charset restrictions, length beyond the 256-char max).
- Slug auto-generation from name or external_id.
- Slug history or change-log tracking.
- Cross-entity-type slug uniqueness enforcement.
- REST API or GraphQL exposure of slug (not part of taxomesh's current interface layer).
