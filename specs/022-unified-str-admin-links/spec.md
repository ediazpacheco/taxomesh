# Feature Specification: Unified __str__ Representation + Django Admin Graph Links

**Feature Branch**: `022-unified-str-admin-links`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Unified __str__ representation for Category and Item domain models, plus Django admin graph links."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent human-readable labels across CLI and admin (Priority: P1)

A developer or admin user sees the same human-readable label for a Category or Item regardless
of the surface (CLI graph output, Django admin graph view, Python repr). The label includes the
name, slug (when present), internal ID, and external ID (when present), clearly prefixed so
each field is unambiguous.

**Why this priority**: Eliminates divergence between the CLI and the admin view. Both surfaces
derive their label from `__str__`, so a single change keeps them in sync forever.

**Independent Test**: Instantiate a `Category` with various combinations of slug/external_id
and assert `str(cat)` returns the expected string. No CLI or admin needed.

**Acceptance Scenarios**:

1. **Given** a Category with no slug and no external_id, **When** `str()` is called, **Then** the result is `📂 <name> (id: <uuid>)`.
2. **Given** a Category with a slug but no external_id, **When** `str()` is called, **Then** the result is `📂 <name> (slug: <slug> - id: <uuid>)`.
3. **Given** a Category with both slug and external_id, **When** `str()` is called, **Then** the result is `📂 <name> (slug: <slug> - id: <uuid> - ext_id: <external_id>)`.
4. **Given** a Category with no slug but with external_id, **When** `str()` is called, **Then** the result is `📂 <name> (id: <uuid> - ext_id: <external_id>)`.
5. **Given** an Item with no slug and no external_id, **When** `str()` is called, **Then** the result is `🏷️ <name> (id: <uuid>)`.
6. **Given** an Item with a slug and external_id, **When** `str()` is called, **Then** the result is `🏷️ <name> (slug: <slug> - id: <uuid> - ext_id: <external_id>)`.

---

### User Story 2 - Django admin graph links to change pages (Priority: P2)

An admin user browsing the taxonomy graph view in the Django admin can click on any category
or item label and be taken directly to its change page, without having to navigate there manually.

**Why this priority**: Improves admin usability. The graph is a read-only overview; linking to
change pages makes it actionable.

**Independent Test**: Load the graph view with at least one category and one item. Verify each
label renders as an anchor tag with the correct change-page URL.

**Acceptance Scenarios**:

1. **Given** the taxonomy graph view is rendered with categories, **When** the page loads, **Then** each category label is a clickable link to that category's change page.
2. **Given** the taxonomy graph view is rendered with items, **When** the page loads, **Then** each item label is a clickable link to that item's change page.
3. **Given** a category with no external_id, **When** the graph is rendered, **Then** the label shows only slug (if present) and id — no empty ext_id segment.

---

### User Story 3 - Simplified admin graph rendering (Priority: P3)

The Django admin graph view calls `str()` on each domain object instead of extracting
individual fields. Removing the per-field extraction eliminates the risk of the admin
view drifting from the domain model's own representation logic.

**Why this priority**: Internal quality improvement. Users don't see it directly, but it
prevents future divergence bugs.

**Independent Test**: Call `_flatten_graph` with a populated graph and assert that the
returned dicts contain `name` equal to `str(cat)` / `str(item)`, and do not contain
`slug`, `external_id`, or `indent_em` keys.

**Acceptance Scenarios**:

1. **Given** a `TaxomeshGraph` with categories and items, **When** `_flatten_graph` is called, **Then** each entry's `name` equals `str(category)` or `str(item)`.
2. **Given** `_flatten_graph` output, **When** inspecting entry keys, **Then** no `slug`, `external_id`, or `indent_em` keys are present.

---

### Edge Cases

- Category or Item with empty string slug (`""`): slug segment must be omitted entirely.
- Category or Item with empty string external_id (`""`): ext_id segment must be omitted entirely.
- Category with external_id that coerces from non-string (e.g., integer): must still appear as string in ext_id segment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `Category.__str__` MUST return a string containing the emoji prefix `📂`, the category name, and an `id: <uuid>` segment.
- **FR-002**: `Category.__str__` MUST include a `slug: <value>` segment only when the slug field is non-empty.
- **FR-003**: `Category.__str__` MUST include an `ext_id: <value>` segment only when the external_id field is non-empty.
- **FR-004**: `Item.__str__` MUST return a string containing the emoji prefix `🏷️`, the item name, and an `id: <uuid>` segment.
- **FR-005**: `Item.__str__` MUST include a `slug: <value>` segment only when the slug field is non-empty.
- **FR-006**: `Item.__str__` MUST include an `ext_id: <value>` segment only when the external_id field is non-empty.
- **FR-007**: The Django admin `_flatten_graph` function MUST derive each entry's `name` field by calling `str()` on the domain object.
- **FR-008**: The Django admin graph template MUST render each category and item label as an anchor tag linking to the corresponding admin change page.
- **FR-009**: The CLI graph output MUST automatically reflect the new `__str__` format without any changes to CLI code.

### Key Entities

- **Category**: Domain model with `name`, `slug`, `category_id` (UUID), `external_id`. Human-readable form controlled by `__str__`.
- **Item**: Domain model with `name`, `slug`, `item_id` (UUID), `external_id`. Human-readable form controlled by `__str__`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing and new unit tests for `Category.__str__` and `Item.__str__` pass without modification to production code after the change.
- **SC-002**: The Django admin graph view renders every entry label as a clickable link (zero non-linked labels).
- **SC-003**: The `_flatten_graph` function returns entries with no `slug`, `external_id`, or `indent_em` keys — verified by unit test.
- **SC-004**: The overall test suite maintains ≥ 80% coverage and zero regressions.
- **SC-005**: The CLI graph output includes the external_id segment for items/categories that have a non-empty external_id.

## Assumptions

- `external_id` defaults to `""` on both `Category` and `Item`; emptiness is the falsy check used to decide whether to include the `ext_id:` segment.
- The Django admin change-page URL names follow the standard pattern `admin:<app_label>_<model_name>_change`.
- No changes to the CLI adapter source code are required — it already calls `str()` internally.
- This feature is implemented as a retroactive spec (the code was written first); the spec describes behaviour already verified by the test suite.
