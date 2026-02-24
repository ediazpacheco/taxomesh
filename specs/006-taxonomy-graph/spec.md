# Feature Specification: Taxonomy Graph

**Feature Branch**: `006-taxonomy-graph`
**Created**: 2026-02-23
**Status**: Draft
**Input**: User description: "Add a graph feature. It should be provided by TaxomeshService. The TaxomeshService should return a TaxomeshGraph instance type. The graph should include the category and items related. Tags are out of scope. Add a graph command in CLI that shows up the TaxomeshGraph in a beautiful way using colors and all that a fancy terminal CLI can do."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve Taxonomy Graph from Service (Priority: P1)

A developer using the taxomesh library calls a method on `TaxomeshService` and receives a `TaxomeshGraph` object that represents the full taxonomy: all categories with their parent-child relationships and all items assigned to each category. Tag data is excluded.

**Why this priority**: This is the foundational capability. The CLI command and any other consumer depend on the service being able to produce this graph object. Without it, nothing else works.

**Independent Test**: Can be tested by calling the service method with a known taxonomy and asserting the returned `TaxomeshGraph` contains the correct categories and items, without any tag data.

**Acceptance Scenarios**:

1. **Given** a taxonomy with categories and items assigned to those categories, **When** the developer calls the graph method on the service, **Then** a `TaxomeshGraph` is returned containing all categories, all parent-child category relationships, and all items per category — with no tag data included.
2. **Given** an empty taxonomy (no categories, no items), **When** the graph method is called, **Then** a `TaxomeshGraph` is returned that is empty but valid (not an error).
3. **Given** a category that has no items assigned, **When** the graph method is called, **Then** that category still appears in the `TaxomeshGraph` with an empty item list.
4. **Given** an item assigned to multiple categories, **When** the graph method is called, **Then** that item appears in the graph associated with every category it belongs to (repeated under each applicable category).
5. **Given** a category with multiple items, **When** the graph method is called, **Then** the items within that category are ordered by their `sort_index` value in ascending order.

---

### User Story 2 - Display Taxonomy Graph in the Terminal (Priority: P2)

A user runs the `graph` CLI command and sees a visually rich, color-coded representation of the full taxonomy — categories in their hierarchical structure and the items belonging to each category — rendered directly in the terminal.

**Why this priority**: The visual display is the primary user-facing output of this feature. It depends on P1 (the service graph method) being in place first.

**Independent Test**: Can be tested by running the `graph` command against a populated taxonomy and verifying the output includes color-coded category names, visible parent-child nesting, item names under each category, and no tag data.

**Acceptance Scenarios**:

1. **Given** a taxonomy with multiple categories (including nested/multi-parent relationships) and items, **When** the user runs `taxomesh graph`, **Then** the terminal displays the full taxonomy with categories visually differentiated from items using color and/or formatting, and the hierarchical structure is apparent.
2. **Given** an empty taxonomy, **When** the user runs `taxomesh graph`, **Then** the CLI displays a clear message indicating no categories or items exist (not an error or blank output).
3. **Given** a taxonomy with deeply nested categories, **When** the user runs `taxomesh graph`, **Then** the nesting depth is visible through indentation or tree-style connectors, and remains readable.
4. **Given** a taxonomy with categories that have no items, **When** the user runs `taxomesh graph`, **Then** those categories are shown without any items listed beneath them.

---

### Edge Cases

- Empty taxonomy: service returns a valid empty graph; CLI shows a user-friendly "nothing to display" message.
- Category with no items: appears in graph with no items listed.
- Item assigned to multiple categories: appears under each applicable category (repeated), ordered by `sort_index` within each.
- Deeply nested category tree (DAG with many levels): hierarchy remains readable in terminal.
- Very large taxonomy (many categories and items): output remains complete (no truncation) unless display constraints require pagination.
- Categories with multiple parents (DAG, not strict tree): each such category is displayed repeated under every parent, consistent with item display strategy.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `TaxomeshService` MUST expose a method that returns a `TaxomeshGraph` instance representing the full taxonomy at the time of the call.
- **FR-002**: `TaxomeshGraph` MUST contain all categories present in the taxonomy, including their parent-child relationships. In the CLI display, a category with multiple parents MUST appear repeated under each parent (same strategy as items).
- **FR-003**: `TaxomeshGraph` MUST contain all items assigned to each category, grouped or associated by their category membership.
- **FR-004**: `TaxomeshGraph` MUST NOT include any tag data (tags are explicitly out of scope for this feature).
- **FR-005**: Items assigned to multiple categories MUST appear under each category they belong to (repeated per category, not deduplicated).
- **FR-005a**: Within each category, items MUST be ordered by their `sort_index` value in ascending order.
- **FR-006**: The CLI MUST provide a `graph` command that retrieves and displays the `TaxomeshGraph`.
- **FR-007**: The `graph` CLI command MUST render the taxonomy with visual differentiation between categories and items using terminal color and/or text formatting.
- **FR-007a**: Each item leaf in the `graph` CLI display MUST show all three of the item's identity/status fields: `external_id`, `item_id`, and `enabled`. All three MUST always be visible regardless of enabled state (e.g., `lion  3f2a…  enabled=True` or `lion  3f2a…  enabled=False`).
- **FR-007b**: The `graph` CLI command MUST display each category using its `name` only; `description` MUST NOT appear in the tree.
- **FR-008**: The `graph` CLI command MUST convey the hierarchical (parent-child) structure of categories through indentation or tree-style visual connectors.
- **FR-009**: The `graph` CLI command MUST display a descriptive message when the taxonomy is empty rather than producing blank or error output.
- **FR-010**: The `graph` CLI command MUST exclude tag data from its display.
- **FR-011**: `TaxomeshService` MUST guarantee a single immutable root category (name `"__root__"`) exists at all times, created eagerly at service initialisation if absent.
- **FR-012**: `create_category()` MUST auto-link every new category to the root as a parent (`sort_index=0`). Attempting to create a category named `"__root__"` MUST raise `TaxomeshRootCategoryError`.
- **FR-013**: `list_categories()` (no `parent_id`) MUST return only direct children of the root category, not all categories.
- **FR-014**: `delete_category()`, `update_category()`, and `add_category_parent()` MUST raise `TaxomeshRootCategoryError` when called with the root category's UUID.

### Key Entities

- **TaxomeshGraph**: A snapshot of the full taxonomy structure. Contains all categories with their parent-child relationships, and all items associated with each category. Does not include tag data.
- **Category (in graph)**: A node representing a category, aware of its parent categories, child categories, and the items assigned to it.
- **Item (in graph)**: A leaf element representing an item assigned to one or more categories. Appears in the graph in the context of its category memberships.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can obtain a complete graph of the taxonomy with a single service call, covering 100% of categories and their items in the current taxonomy state.
- **SC-002**: The returned `TaxomeshGraph` contains zero tag data entries, regardless of how many tags exist in the taxonomy.
- **SC-003**: The `graph` CLI command output visually distinguishes categories from items (verifiable by automated test checking color codes or formatting markers in output).
- **SC-004**: The `graph` CLI command renders the full hierarchy of a taxonomy with up to 50 categories and 200 items without omitting any entries.
- **SC-005**: The `graph` CLI command completes and renders output within 3 seconds for a taxonomy of up to 50 categories and 200 items.
- **SC-006**: First-time users can identify which entries are categories and which are items from the terminal display without reading documentation.

## Clarifications

### Session 2026-02-23

- Q: For a category with multiple parents, how is it shown in the CLI? → A: Repeated under every parent it belongs to (same strategy as items).
- Q: How is category ordering within a parent determined? → A: Via `CategoryParentLink.sort_index`; every category gets a root link with `sort_index=0` at creation.

### Session 2026-02-24

- Q: What Item information should the `graph` CLI command display for each item leaf? → A: All three identity/status fields always: `external_id`, `item_id`, and `enabled` (e.g., `lion  3f2a…  enabled=True`).
- Q: Should the `graph` CLI command show `Category.description` alongside the category name? → A: Name only; description is not shown in the tree display.

## Assumptions

- The `graph` command always shows the full taxonomy — filtering by category subtree is out of scope for this feature.
- The visual display targets standard terminals that support ANSI color codes (most modern terminals). Non-color fallback behavior is not in scope.
- `TaxomeshGraph` is a read-only snapshot; it does not support mutations or live updates.
- The service builds the graph from whatever storage backend is configured; performance depends on the size of the taxonomy and is subject to SC-005.
- Items in multiple categories appear under each relevant category in the display (confirmed, same strategy as multi-parent categories).

## Out of Scope

- Tag data in any form (listing, filtering, displaying).
- Filtering or searching within the graph (e.g., by category name or item name).
- Exporting the graph to a file or external format.
- Interactive navigation of the graph in the terminal.
- Non-ANSI fallback rendering for terminals without color support.
