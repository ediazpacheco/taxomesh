# Feature Specification: Graph Category UUID Display

**Feature Branch**: `009-graph-category-uuid`
**Created**: 2026-02-26
**Status**: Draft
**Input**: User description: "In CLI command `taxomesh graph` show the UUID on each category (as is currently showing in the items)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Category UUID in Graph Output (Priority: P1)

A user runs `taxomesh graph` to inspect their taxonomy tree. Currently, each
item line displays its `external_id`, `item_id` (UUID), and `enabled` status.
Categories, however, only display their name — making it impossible to
identify or reference a specific category by its UUID without running a
separate command.

After this change, each category line in the graph output includes the
category's UUID alongside its name, giving users a single-command view of
the full taxonomy with all identifiers visible.

**Why this priority**: This is the sole feature — displaying the category UUID
is the entire scope.

**Independent Test**: Run `taxomesh graph` with at least one category in the
store. Verify that each category line includes its UUID.

**Acceptance Scenarios**:

1. **Given** a taxonomy with one or more categories, **When** the user runs
   `taxomesh graph`, **Then** every category line displays both the category
   name and the category UUID.
2. **Given** a taxonomy with nested categories, **When** the user runs
   `taxomesh graph`, **Then** every category at every nesting level displays
   its UUID.
3. **Given** a taxonomy with categories that have items, **When** the user
   runs `taxomesh graph`, **Then** category UUIDs and item UUIDs are both
   visible in the same tree, each on their respective lines.

---

### Edge Cases

- What happens when a category has an unusually long name? The UUID should
  still appear on the same line, separated from the name — no truncation
  of the UUID.
- What happens with an empty taxonomy (no categories)? The existing
  "No categories were found" message is unchanged; no UUID rendering
  is attempted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `taxomesh graph` command MUST display the `category_id`
  (UUID) on each category line in the tree output.
- **FR-002**: The category UUID MUST appear after the category name on the
  same line, visually separated by whitespace.
- **FR-003**: The category UUID MUST use a muted/dim visual style, consistent
  with how `item_id` is already rendered for items.
- **FR-004**: The existing item rendering (external_id, item_id, enabled
  status) MUST remain unchanged.
- **FR-005**: The existing "No categories were found" empty-state message
  MUST remain unchanged.

## Assumptions

- The category UUID style (`dim`) matches the item UUID style for visual
  consistency. This is a reasonable default following the existing pattern.
- No new CLI flags are needed — the UUID is always shown (matching how
  item UUIDs are always shown).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of categories displayed by `taxomesh graph` include
  their UUID in the output.
- **SC-002**: Users can copy a category UUID directly from the graph output
  to use in other commands (e.g. `taxomesh category remove`).
- **SC-003**: Existing item display format is unchanged — no regressions
  in item rendering.
- **SC-004**: All existing CLI tests continue to pass after the change.
