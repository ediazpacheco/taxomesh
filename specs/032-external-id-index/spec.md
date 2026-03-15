# Feature Specification: External-ID Database Indexes & Lookup Promotion

**Feature Branch**: `032-external-id-index`
**Created**: 2026-03-14
**Status**: Draft
**Input**: User description: "Spec: Taxomesh performance improvements for external_id lookups and Django admin usage"

## Overview

`external_id` lookups are a primary integration path for consumers that bridge their own entity
identifiers into taxomesh. Currently, `CategoryModel.external_id` and `ItemModel.external_id`
have no database index, so every `filter(external_id=...)` call performs a full table scan.
In production Django deployments with large item/category tables this makes admin pages and
integration resolution loops effectively unusable.

The `TaxomeshRepositoryBase` protocol already declares `list_items_by_external_id` and
`list_categories_by_external_id`, and `DjangoRepository` already implements them via filtered
ORM queries. The missing piece is the database index that makes those filtered queries fast,
plus tests and documentation that make these methods an explicitly supported, visible API.

## Clarifications

No open clarification items. All design decisions are fully specified by the user's requirements
and the current codebase state:

- `external_id` remains non-unique and blank-allowed; duplicates are valid.
- No slug behaviour changes.
- No new protocol methods are needed — both lookup methods are already in `TaxomeshRepositoryBase`.

## User Scenarios & Testing

### User Story 1 - Fast item resolution by external_id in Django (Priority: P1)

A consumer integration loop processes thousands of inbound events per minute. Each event
carries the consumer's own entity ID as `external_id`. The loop calls
`list_items_by_external_id(external_id)` on each event to resolve the taxomesh `Item`.
Without an index, this scan dominates wall-clock time and makes the loop unusable at scale.

**Why this priority**: This is the direct performance bottleneck described in the problem
statement. Without the index, the entire feature purpose fails.

**Independent Test**: Verify that `ItemModel.external_id` is declared with `db_index=True` in
the Django model field definition, and that a migration adding the index exists and is
consistent with the model state.

**Acceptance Scenarios**:

1. **Given** `ItemModel.external_id` field is inspected, **When** its `db_index` attribute is
   read, **Then** it is `True`.
2. **Given** a Django migration is applied to a test database, **When** the schema for
   `taxomesh_item` is inspected, **Then** an index on `external_id` is present.
3. **Given** two items with `external_id = "dup-1"` and one item with `external_id = "unique-1"`
   exist, **When** `list_items_by_external_id("dup-1")` is called, **Then** exactly 2 items are
   returned; **When** `list_items_by_external_id("unique-1")` is called, **Then** exactly 1 item
   is returned; **When** `list_items_by_external_id("missing")` is called, **Then** an empty list
   is returned.

---

### User Story 2 - Fast category resolution by external_id in Django (Priority: P1)

A consumer maps external taxonomy nodes to taxomesh categories using `external_id`. Every
admin page render and every integration sync calls `list_categories_by_external_id` for each
displayed row. Without an index, each call is a table scan, causing timeouts on large tables.

**Why this priority**: Symmetric to item resolution; both are required for the feature to
deliver its performance goal.

**Independent Test**: Verify that `CategoryModel.external_id` has `db_index=True` and that
`list_categories_by_external_id` returns correct results for empty, unique, and duplicate
external IDs.

**Acceptance Scenarios**:

1. **Given** `CategoryModel.external_id` field is inspected, **When** its `db_index` attribute
   is read, **Then** it is `True`.
2. **Given** a Django migration is applied to a test database, **When** the schema for
   `taxomesh_category` is inspected, **Then** an index on `external_id` is present.
3. **Given** two categories with `external_id = "dup-cat"` and one with `external_id = "solo"`
   exist, **When** `list_categories_by_external_id("dup-cat")` is called, **Then** exactly 2
   categories are returned; **When** `list_categories_by_external_id("solo")` is called,
   **Then** exactly 1 is returned; **When** `list_categories_by_external_id("ghost")` is called,
   **Then** an empty list is returned.

---

### User Story 3 - Consumers discover and use the correct API for external_id resolution (Priority: P2)

A developer integrating taxomesh into their application reads the documentation and learns
that `list_items_by_external_id` / `list_categories_by_external_id` are the correct, supported
APIs for external ID resolution — not `list_items()` + Python filter.

**Why this priority**: Correct API usage prevents the performance issue from recurring in new
integrations. The index alone does not help if consumers are still doing full-table reads in Python.

**Independent Test**: The README or integration guide explicitly states: use
`list_items_by_external_id` / `list_categories_by_external_id` for point lookups; do not use
`list_items()` / `list_categories()` and filter in Python.

**Acceptance Scenarios**:

1. **Given** a developer reads the taxomesh README, **When** they search for external_id
   lookup guidance, **Then** they find explicit direction to use the dedicated lookup methods.
2. **Given** the documentation exists, **When** it is reviewed, **Then** it states that
   `external_id` is indexed but not unique and that multiple matches are a valid, expected state.

---

### Edge Cases

- `external_id` may be blank (`""`). A query for `external_id=""` must return all records with
  a blank external_id — no special handling; blank is a valid filter value.
- Multiple records with the same `external_id` must all be returned; the library performs no
  deduplication.
- The migration must be additive: existing rows with blank or duplicate `external_id` values
  must remain valid after it runs.
- The index covers both `taxomesh_item.external_id` and `taxomesh_category.external_id` in
  one migration.

## Requirements

### Functional Requirements

- **FR-001**: `ItemModel.external_id` MUST be declared with `db_index=True` in the Django
  model field definition.
- **FR-002**: `CategoryModel.external_id` MUST be declared with `db_index=True` in the Django
  model field definition.
- **FR-003**: A Django migration MUST exist in `taxomesh.contrib.django.migrations` that adds
  database indexes for `taxomesh_item.external_id` and `taxomesh_category.external_id`.
- **FR-004**: The migration MUST be additive and backward-compatible — no column removal, no
  data rewrite, no uniqueness constraint added.
- **FR-005**: `DjangoRepository.list_items_by_external_id(external_id: str) -> list[Item]`
  MUST use a filtered ORM query and MUST NOT call `list_items()` internally.
- **FR-006**: `DjangoRepository.list_categories_by_external_id(external_id: str) -> list[Category]`
  MUST use a filtered ORM query and MUST NOT call `list_categories()` internally.
- **FR-007**: Both lookup methods MUST preserve duplicate-friendly semantics: returning 0, 1, or
  many matches depending on what is stored.
- **FR-008**: Documentation (README) MUST explicitly direct consumers to use
  `list_items_by_external_id` / `list_categories_by_external_id` for point lookups and MUST
  warn against using `list_items()` / `list_categories()` and filtering in Python.
- **FR-009**: Documentation MUST state that `external_id` is indexed but not unique.

### Key Entities

- **ItemModel**: Django ORM model for taxomesh items. Gains a database index on `external_id`.
- **CategoryModel**: Django ORM model for taxomesh categories. Gains a database index on
  `external_id`.
- **Migration 0004**: Additive schema migration adding two indexes, no data changes required.

## Success Criteria

### Measurable Outcomes

- **SC-001**: After the migration runs, a database-level index exists on both
  `taxomesh_item.external_id` and `taxomesh_category.external_id` — verifiable by inspecting
  the applied schema.
- **SC-002**: `list_items_by_external_id` and `list_categories_by_external_id` return correct
  results for all three cardinality cases: zero matches, one match, and multiple matches.
- **SC-003**: Tests covering all three result-cardinality cases exist and pass for both
  lookup methods.
- **SC-004**: Documentation clearly steers consumers to the dedicated lookup methods with no
  ambiguity about `list_items()` / `list_categories()` being the wrong path for point lookups.
- **SC-005**: No existing test regressions — blank and duplicate `external_id` rows remain
  valid after the migration.

## Assumptions

- `DjangoRepository.list_items_by_external_id` and `list_categories_by_external_id` already
  use filtered ORM queries (`filter(external_id=external_id)`). This spec adds indexes and
  tests; it does not rewrite the query logic.
- `TaxomeshRepositoryBase` already declares both lookup methods as protocol methods. No
  protocol changes are needed.
- Non-Django repositories (`JsonRepository`, `YAMLRepository`) already implement the protocol
  methods via Python-level scan. No changes to those implementations are required — the
  performance improvement targets Django only.
- The next available migration number in `taxomesh.contrib.django.migrations` is `0004`.
