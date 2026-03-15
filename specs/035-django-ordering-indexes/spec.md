# Feature Specification: Database Indexes for Django Ordering Performance

**Feature Branch**: `035-django-ordering-indexes`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Add database indexes to DjangoRepository Django ORM models to support the ordering added in 034-default-sort-index. Specifically: index on CategoryModel.name, index on ItemModel.name, composite index on CategoryParentLinkModel(parent_category_id, sort_index), composite index on ItemParentLinkModel(category_id, sort_index). ItemRelationLinkModel.sort_index is excluded because list_item_relation_links() always filters by item_id first (FK-indexed), keeping the result set small."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Category and Item Listing Performs at Scale (Priority: P1)

A developer uses the taxomesh Django backend with a large taxonomy (hundreds or thousands
of categories and items). Calls to list_categories() and list_items() return results
quickly regardless of dataset size, because the database can satisfy the ORDER BY name
clause using an index rather than a full table sort.

**Why this priority**: These are the most frequently called collection methods. Without
an index on name, every call triggers a full table scan followed by an in-memory sort.
An index eliminates the sort step for ascending name queries.

**Independent Test**: Insert categories/items with names in non-alphabetical order; verify
that list_categories() and list_items() return results in alphabetical name order, and
that no regressions appear in existing ordering tests.

**Acceptance Scenarios**:

1. **Given** a Django-backed repository containing categories with names in non-alphabetical
   insertion order, **When** `list_categories()` is called, **Then** results are returned in
   ascending name order, consistent with spec 034 behaviour.

2. **Given** a Django-backed repository containing items with names in non-alphabetical
   insertion order, **When** `list_items()` is called, **Then** results are returned in
   ascending name order, consistent with spec 034 behaviour.

3. **Given** `list_categories_by_external_id(ext)` or `list_items_by_external_id(ext)` is
   called, **Then** results are ordered by name correctly (the `external_id` filter uses its
   own index from spec 032; the `name` index further optimises the secondary sort).

---

### User Story 2 - Link Listing Performs at Scale (Priority: P1)

A developer queries list_category_parent_links() or list_item_parent_links() on a
repository that holds many category/item relationships. Results are grouped by parent and
ordered by sort_index within each group efficiently, because the database can use a
composite index on (parent_id, sort_index) to satisfy the ORDER BY clause.

**Why this priority**: Link tables grow proportionally to the number of relationships in
the taxonomy. Without a composite index, ordering requires sorting the full link table
in memory. The composite index allows the database engine to return rows in the required
order directly from the index.

**Independent Test**: Insert many CategoryParentLink and ItemParentLink records spanning
multiple parents with mixed sort_index values; verify results are correctly grouped and
ordered, and that existing ordering tests continue to pass.

**Acceptance Scenarios**:

1. **Given** a CategoryParentLink table with rows spanning multiple parents, **When**
   `list_category_parent_links()` is called, **Then** results are returned grouped by
   parent and ordered by sort_index within each group, consistent with spec 034 behaviour.

2. **Given** an ItemParentLink table with rows spanning multiple categories, **When**
   `list_item_parent_links()` is called, **Then** results are returned grouped by category
   and ordered by sort_index within each group, consistent with spec 034 behaviour.

---

### Edge Cases

- What happens when the index is added to an existing database with data? The migration
  is additive — it creates indexes without modifying stored values or altering existing rows.
- What happens on an empty table? Indexes on empty tables have no effect on correctness;
  queries still return empty lists without error.
- What happens when two records share the same name? The index still serves ORDER BY
  (name, id) correctly; the secondary id sort is satisfied by the primary key index.
- What if an index already exists (e.g., applied manually)? The migration checks for
  existence before creating; duplicate creation is handled gracefully.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A single-column index MUST be added on the `name` field of the category
  storage model to optimise ascending-name ordering for category listing methods.

- **FR-002**: A single-column index MUST be added on the `name` field of the item
  storage model to optimise ascending-name ordering for item listing methods.

- **FR-003**: A composite index MUST be added on `(parent_category_id, sort_index)` of
  the category-parent-link storage model to optimise the grouped-by-parent, ordered-by-sort_index
  query issued by the category parent link listing method.

- **FR-004**: A composite index MUST be added on `(category_id, sort_index)` of the
  item-parent-link storage model to optimise the grouped-by-category, ordered-by-sort_index
  query issued by the item parent link listing method.

- **FR-005**: The item-relation-link model MUST NOT receive a sort_index index in this
  feature. The relation link listing method always filters by item first (via an existing
  foreign-key index), keeping result sets small enough that an additional sort_index index
  provides no measurable benefit.

- **FR-006**: A schema migration MUST be generated and included so that the indexes are
  applied automatically on deployment. No manual database intervention is required.

- **FR-007**: Existing data, query results, and public API behaviour MUST NOT change.
  The indexes are read-optimisation only and have no effect on stored values or ordering
  correctness.

- **FR-008**: All quality gates (linting, formatting, type checking, test coverage ≥ 80%)
  MUST continue to pass after the migration is added.

### Key Entities

- **Category storage model**: Represents a taxonomy category in the database. Gains a
  single-column index on the name field.
- **Item storage model**: Represents a taxonomy item in the database. Gains a
  single-column index on the name field.
- **Category-parent-link storage model**: Represents a directed edge in the category DAG.
  Gains a composite index on (parent_category_id, sort_index).
- **Item-parent-link storage model**: Represents an item's placement within a category.
  Gains a composite index on (category_id, sort_index).
- **Schema migration**: An auto-generated database change file that applies all four
  indexes atomically on deployment.

## Assumptions

- All four indexes are additive schema changes — no column alterations, no data migrations.
- Indexes are defined at the model layer (not applied manually to the database).
- The migration is compatible with both SQLite (used in tests) and PostgreSQL (production).
- No changes to domain models, repository adapter logic, service layer, or public API.
- The item-relation-link sort_index is intentionally excluded from this feature.
- Existing ordering tests from spec 034 serve as the correctness regression suite.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four indexes are present in the generated migration and are applied
  correctly on a clean database, verified by inspecting the schema after migration.

- **SC-002**: All existing ordering tests from spec 034 continue to pass without
  modification after the migration is applied — confirming no regression in result order.

- **SC-003**: No regressions in the broader test suite; coverage remains ≥ 80%.

- **SC-004**: The migration file and model changes pass all quality gates (linting,
  formatting, type checking) without modification.
