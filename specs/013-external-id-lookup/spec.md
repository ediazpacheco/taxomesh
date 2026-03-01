# Feature Specification: External-ID Lookup & Assignable Categories

**Feature Branch**: `013-external-id-lookup`
**Created**: 2026-02-28
**Status**: Draft
**Input**: User description: "Spec 013 — External-ID Lookup & Assignable Categories. Add two new service methods (get_items_by_external_id, get_categories_by_external_id) that let consumers look up items and categories by their external_id field (bridge between consumer app UUIDs and taxomesh internal IDs). Also add two new protocol methods on TaxomeshRepositoryBase (list_items_by_external_id, list_categories_by_external_id) implemented by all three backends (DjangoRepository via ORM filter, YAMLRepository and JsonRepository via Python scan). DjangoRepository gets an extra non-protocol method assignable_categories_qs() returning a Django ORM QuerySet of enabled non-root categories for admin autocomplete widgets. No new migrations needed. Consumer derives orphan/duplicate state from returned list length."

## Overview

taxomesh assigns each item and category an internal UUID (`item_id`, `category_id`). Consumer
applications typically identify their entities by their own identifier — a UUID, an integer PK,
or a string slug — stored in taxomesh as `external_id`. Until now, consumers had no direct way
to bridge from their own IDs to taxomesh's internal IDs without scanning all items or categories
manually. This feature exposes that bridge through `TaxomeshService` and extends the repository
protocol so all storage backends provide it natively.

A secondary consumer need is a pre-filtered list of categories for UI widgets (e.g., a Django
admin autocomplete): only enabled, non-root categories should appear. `DjangoRepository` gains
a dedicated method returning a lazy ORM queryset suitable for direct use in admin configuration.

## Clarifications

### Session 2026-02-28

- Q: How should consumers distinguish "not found" from "duplicates exist"? → A: By list length — `len == 0` means orphan (not found), `len == 1` means unique match, `len > 1` means duplicates exist. No automatic resolution is performed by the library.
- Q: Should `assignable_categories_qs()` be part of the repository protocol? → A: No — it is Django-ORM-specific (returns a Django QuerySet) and has no generic equivalent. It is an extra method on `DjangoRepository` only. Consumer must import `DjangoRepository` directly for this one method.
- Q: Are new database migrations required? → A: No — all columns already exist on `CategoryModel` and `ItemModel` from spec 012.
- Q: Should `get_categories_by_external_id` ever return the `__root__` category? → A: No — the root category is always excluded from results, filtered by `category_id == self._root_id`. Root is an implementation detail consumers must never see.
- Q: Should `get_items_by_external_id` and `get_categories_by_external_id` propagate `TaxomeshRepositoryError` on backend failure? → A: Yes — errors propagate unchanged to the caller, consistent with all other `TaxomeshService` methods.

## User Scenarios & Testing

### User Story 1 — Look Up Item by External ID (Priority: P1)

A consumer application stores items in taxomesh with their own entity UUIDs as `external_id`.
When processing a business event (e.g., an order placed for entity `abc-123`), the consumer
needs to retrieve the taxomesh `Item` for that entity to check its categories or tags.

**Why this priority**: This is the primary bridge between the consumer's data model and
taxomesh's internal model. Without it, consumers must fetch all items and filter client-side.

**Independent Test**: Create an item with a known `external_id`, call
`get_items_by_external_id(external_id)`, assert the returned list contains exactly that item.

**Acceptance Scenarios**:

1. **Given** an item exists with `external_id = "entity-uuid-1"`, **When**
   `get_items_by_external_id("entity-uuid-1")` is called, **Then** a list containing exactly
   that item is returned.
2. **Given** no item with `external_id = "missing"` exists, **When**
   `get_items_by_external_id("missing")` is called, **Then** an empty list is returned.
3. **Given** two items with the same `external_id` exist, **When**
   `get_items_by_external_id(external_id)` is called, **Then** a list of length 2 is returned
   (consumer detects the duplicate condition via `len > 1`).
4. **Given** an item created with `external_id = 42` (integer) exists, **When**
   `get_items_by_external_id(42)` is called, **Then** that item is returned; calling with `"42"`
   (string) **also** returns that item, because both `42` and `"42"` coerce to the stored value
   `"42"` (all external IDs are stored as strings).
5. **Given** an item created with `external_id = UUID("…")` exists, **When**
   `get_items_by_external_id(UUID("…"))` **or** `get_items_by_external_id("…")` is called,
   **Then** that item is returned (UUID is coerced to its canonical string representation at
   storage time; the string form matches equally).

---

### User Story 2 — Look Up Category by External ID (Priority: P1)

A consumer application assigns `external_id` to categories to map them to external taxonomy
nodes (e.g., a product catalogue category from an ERP). The consumer needs to resolve the
taxomesh `Category` by that external identifier.

**Why this priority**: Symmetric to item lookup; both are required for the bridge to work in
practice. Categories are looked up as frequently as items in typical integration flows.

**Independent Test**: Save a category with `external_id = "ext-cats-1"` directly via the
repository, call `get_categories_by_external_id("ext-cats-1")`, assert the result contains
exactly that category.

**Acceptance Scenarios**:

1. **Given** a category with `external_id = "ext-cats-1"` exists, **When**
   `get_categories_by_external_id("ext-cats-1")` is called, **Then** a list containing that
   category is returned.
2. **Given** no category with `external_id = "nonexistent"` exists, **When**
   `get_categories_by_external_id("nonexistent")` is called, **Then** an empty list is returned.
3. **Given** two categories share `external_id = "shared"`, **When**
   `get_categories_by_external_id("shared")` is called, **Then** both are returned (length 2).
4. **Given** only the `__root__` category exists (with `external_id = ""`), **When**
   `get_categories_by_external_id("any-non-empty")` is called, **Then** an empty list is returned.
5. **Given** the `__root__` category has `external_id = ""`, **When**
   `get_categories_by_external_id("")` is called, **Then** an empty list is returned (root is
   excluded regardless of external_id match).

---

### User Story 3 — Assignable Categories for Admin Autocomplete (Priority: P2)

A Django-backed consumer application uses the Django admin to assign categories to items. The
admin autocomplete widget needs a filtered queryset of categories — only those that are enabled
and can be meaningfully assigned (i.e., not the internal `__root__` category).

**Why this priority**: Operationally important for Django consumers, but secondary to the core
lookup capability. The root category is an implementation detail; exposing it in the UI would
confuse operators.

**Independent Test**: Create a mix of enabled/disabled and root/non-root categories; call
`assignable_categories_qs()`, assert only enabled non-root entries appear and the result
supports queryset chaining (`.filter()`, `.order_by()`).

**Acceptance Scenarios**:

1. **Given** enabled non-root categories exist, **When** `assignable_categories_qs()` is called,
   **Then** all enabled non-root categories are included in the result.
2. **Given** a disabled category exists, **When** `assignable_categories_qs()` is called,
   **Then** the disabled category is excluded.
3. **Given** the `__root__` category exists (always enabled), **When**
   `assignable_categories_qs()` is called, **Then** `__root__` is excluded.
4. **Given** no categories exist, **When** `assignable_categories_qs()` is called, **Then** the
   result is empty.
5. **Given** a non-empty result, **When** `.filter(name="X")` is chained on the result, **Then**
   the chain works without error (result is a lazy queryset).

---

### Edge Cases

- What happens when `external_id` is an integer `0` or an empty string `""`? → Integer `0`
  is coerced to `"0"` at storage time; the lookup `get_items_by_external_id(0)` or
  `get_items_by_external_id("0")` are equivalent. For categories, `""` will never return
  `__root__` because the root is always excluded from `get_categories_by_external_id` results;
  it will only match user-created categories explicitly saved with `external_id = ""`.
- How does the system handle inputs of different Python types (`"123"` str vs `123` int)? →
  Both are coerced to the string `"123"` at domain model construction time. There is no
  type discrimination at storage or lookup — `"123"` and `123` resolve to the same stored value
  and will match each other.
- What happens when `external_id` is a `UUID` vs its string representation? → `UUID("…")` is
  coerced to its canonical hyphenated string at storage time. Both `get_items_by_external_id(UUID("…"))`
  and `get_items_by_external_id("…")` (with the same string) will match the same item.
- How does `assignable_categories_qs()` behave if the database is unavailable? → It raises
  `TaxomeshRepositoryError` (wrapping the underlying database error).
- How do `get_items_by_external_id` and `get_categories_by_external_id` behave if the repository
  raises an error? → `TaxomeshRepositoryError` propagates unchanged to the caller; no swallowing
  or empty-list fallback is performed.

## Requirements

### Functional Requirements

- **FR-001**: `TaxomeshService` MUST expose `get_items_by_external_id(external_id)` returning
  a list of all items whose stored `external_id` (always a `str`) matches `str(external_id)`.
- **FR-002**: `TaxomeshService` MUST expose `get_categories_by_external_id(external_id)`
  returning a list of all categories whose stored `external_id` (always a `str`) matches
  `str(external_id)`. The `__root__` category MUST always be excluded from results,
  regardless of its `external_id` value.
- **FR-003**: Both lookup methods MUST return an empty list when no match is found (orphan
  signal) and return multiple entries when more than one entity shares the same `external_id`
  (duplicate signal). No automatic resolution or deduplication is performed.
- **FR-004**: `TaxomeshRepositoryBase` protocol MUST declare `list_items_by_external_id` and
  `list_categories_by_external_id` so all conforming backends are required to implement them.
- **FR-005**: All three repository backends (DjangoRepository, YAMLRepository, JsonRepository)
  MUST implement the two protocol methods with identical observable behaviour.
- **FR-006**: `DjangoRepository` MUST additionally expose `assignable_categories_qs()` returning
  a lazy, filterable collection of enabled, non-`__root__` categories suitable for use in admin
  autocomplete widgets. This method is outside the protocol (Django-specific only).
- **FR-007**: `assignable_categories_qs()` MUST exclude: (a) any category with `enabled=False`,
  and (b) the reserved root category (`__root__`).
- **FR-008**: All `external_id` values are stored as plain strings. Any consumer-provided
  `UUID` or `int` is coerced to `str` at domain model construction time (via a Pydantic
  `mode='before'` validator). Lookup methods accept `ExternalId` (`str | int | UUID`) as a
  convenience; inputs are cast to `str` before comparison. As a result, `42` and `"42"` resolve
  to the same stored value and will match each other — there is no type discrimination.
- **FR-009**: No new domain-level database schema changes are required for the lookup feature;
  the `external_id` column already exists on both `CategoryModel` and `ItemModel`. (Note: the
  spec 012 / 013 implementation cycle included an ORM model cleanup — removal of the
  `external_id_type` discriminator and switch from `JSONField` to `CharField` — which required
  regenerating the initial migration. This cleanup is captured in the same migration file as
  spec 012's schema.)
- **FR-010**: Both service-level lookup methods MUST be documented with orphan/duplicate
  semantics in their docstrings (i.e., what `len == 0`, `len == 1`, `len > 1` means).
- **FR-011**: Tags are out of scope for this feature; no tag lookup by `external_id` is added.
- **FR-012**: Both `get_items_by_external_id` and `get_categories_by_external_id` MUST propagate
  `TaxomeshRepositoryError` unchanged if the underlying repository raises it. No swallowing or
  wrapping is performed at the service layer.

### Key Entities

- **ExternalId**: A union type (`UUID | int | str`) representing a consumer-provided identifier.
  Used as the lookup key in all new methods.
- **Item**: Domain entity with an `item_id` (internal UUID) and an `external_id` (consumer ID).
- **Category**: Domain entity with a `category_id` (internal UUID) and an `external_id`
  (consumer ID); also carries `enabled` (bool) and `name` (str) fields used in filtering.
- **TaxomeshRepositoryBase**: The structural protocol that all backends must satisfy; extended
  with two new lookup method signatures.
- **DjangoRepository**: The ORM-backed backend; gains the two protocol methods plus the
  non-protocol `assignable_categories_qs()` extra.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A consumer can resolve a taxomesh `Item` from any `ExternalId` in a single
  method call on `TaxomeshService`, with no client-side filtering required.
- **SC-002**: A consumer can resolve a taxomesh `Category` from any `ExternalId` in a single
  method call on `TaxomeshService`, with no client-side filtering required.
- **SC-003**: The returned list length unambiguously communicates the entity state to the
  consumer: `0` = orphan, `1` = unique, `> 1` = duplicates.
- **SC-004**: The `DjangoRepository` assignable-categories result can be passed directly to a
  Django admin autocomplete widget without additional filtering by the consumer.
- **SC-005**: All three repository backends produce identical observable results for the same
  lookup inputs (cross-backend consistency).
- **SC-006**: All quality gates pass with no regressions: linting, formatting, strict type
  checking, and test coverage ≥ 80%.

## Assumptions

- `external_id` values are not required to be unique within taxomesh by design; uniqueness
  enforcement is the consumer's responsibility if needed.
- The `__root__` category always has `name = "__root__"` as its identifying characteristic for
  the purpose of the `assignable_categories_qs()` filter.
- Django admin consumers are expected to import `DjangoRepository` directly to access
  `assignable_categories_qs()`. This is the one sanctioned exception to the rule that consumers
  never interact with the repository layer directly.
- All `external_id` values are coerced to `str` at domain model construction time via a Pydantic
  `mode='before'` validator (`str(v)`). The `ExternalId` type alias (`str | int | UUID`) describes
  valid input types at service method call sites only; storage and lookup always operate on `str`.
  There is no type discrimination — `42`, `"42"`, and any value whose `str()` is `"42"` are
  equivalent from the library's perspective.
