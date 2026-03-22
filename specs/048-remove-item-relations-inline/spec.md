# Feature Specification: Remove Redundant Item Relation Link Models Inline

**Feature Branch**: `048-remove-item-relations-inline`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "quitar el inline 'Item relation link models' porque funcionalmente es lo mismo que 'Items related with' en por ej /admin/taxomesh_contrib_django/itemmodel/.../change/"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clean Item Change Page (Priority: P1)

An admin navigating to an item's change page currently sees two sections relating to item relations: "Items related with" (outgoing relations, editable) and "Item relation link models" (incoming relations, read-only). The read-only incoming section adds visual noise without providing actionable value — an admin who wants to manage relations uses the "Items related with" section, and incoming relations are discoverable from the related item's own change page. Removing the "Item relation link models" inline simplifies the page.

**Why this priority**: Reduces visual clutter on the item change page; no data is lost since relations are bidirectionally accessible from either item's change page.

**Independent Test**: Navigate to any item change page — "Item relation link models" section must not appear, and "Items related with" must still be present and fully functional.

**Acceptance Scenarios**:

1. **Given** an item with outgoing and incoming relations, **When** an admin opens the item's change page, **Then** no section for incoming item relations is visible.
2. **Given** an item with outgoing and incoming relations, **When** an admin opens the item's change page, **Then** the "Items related with" section is still present and shows outgoing relations correctly.
3. **Given** an item with no relations, **When** an admin opens the item's change page, **Then** the "Items related with" section is still present (empty, with option to add) and no incoming-relation section appears.

---

### Edge Cases

- Items that have only incoming relations (no outgoing): the change page shows an empty "Items related with" section — this is acceptable.
- Items with no relations at all: the page must still function normally after the inline is removed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The item change page MUST NOT display an inline section for incoming item relations ("Item relation link models").
- **FR-002**: The item change page MUST continue to display the "Items related with" inline section for outgoing relations, with full create/edit/delete capability.
- **FR-003**: Removing the inline MUST NOT affect the underlying data — no item relations must be deleted or modified as a result of this change.
- **FR-004**: All other inlines on the item change page (parent links, tag links) MUST remain unaffected.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The item change page displays zero inline sections for incoming item relations.
- **SC-002**: The "Items related with" inline section remains fully functional — admins can add, edit, and remove outgoing relations without errors.
- **SC-003**: No existing item relation data is altered as a result of this change (verifiable by checking relation counts before and after in the test database).
- **SC-004**: All existing admin tests pass without modification.

## Assumptions

- The section labeled "Item relation link models" corresponds to the `IncomingRelationInline` — a read-only inline registered on the item change page that shows relations where the current item is the target.
- Removing this inline is a pure display/configuration change — no data migration, no model change, and no service-layer change is required.
- Outgoing relations ("Items related with") remain the canonical interface for managing item relations from an item's change page; incoming relations remain visible from the related item's own page.
