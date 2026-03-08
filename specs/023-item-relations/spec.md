# Feature Specification: Item-to-Item Relations (ItemRelationLink)

**Feature Branch**: `023-item-relations`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "Add first-class generic item-to-item relations to taxomesh via a new ItemRelationLink feature. Keep taxomesh domain-agnostic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Relate Two Items Programmatically (Priority: P1)

A library user calls the service API to record that one item is related to another via a named, generic relation type. The relation is directed (source → target) and is identified by the triple `(source_item_id, target_item_id, relation_type)`. Calling the same API again with the same triple updates the existing relation (upsert).

**Why this priority**: The service API is the foundation. All other surfaces (CLI, admin) depend on it. Without this, no relation can exist.

**Independent Test**: Create two items and call `relate_items(source_id, target_id, "covers")`. Verify the relation is returned by `list_item_relations(source_id)`.

**Acceptance Scenarios**:

1. **Given** two distinct items exist, **When** `relate_items(source_id, target_id, "covers")` is called, **Then** a relation with `relation_type="covers"` is stored and returned by `list_item_relations`.
2. **Given** a relation already exists for `(source, target, "covers")`, **When** `relate_items` is called again with updated `sort_index` or `metadata`, **Then** the existing relation is updated (upsert) rather than duplicated.
3. **Given** any two items, **When** `relate_items(id, id, "any")` is called with `source_item_id == target_item_id`, **Then** an error is raised and no relation is stored.
4. **Given** any two items, **When** `relate_items` is called with an empty string `relation_type`, **Then** an error is raised and no relation is stored.

---

### User Story 2 — Query Relations for an Item (Priority: P1)

A library user queries all outgoing or incoming relations for a given item, optionally filtering by `relation_type`. The results are returned as a list of `ItemRelationLink` objects.

**Why this priority**: Reading relations is as fundamental as writing them; both are needed for the feature to deliver any value.

**Independent Test**: After creating several relations, call `list_item_relations(item_id)` and `list_related_items(item_id)`. Verify correct links are returned and filtering by `relation_type` works.

**Acceptance Scenarios**:

1. **Given** item A has relations to B ("covers") and C ("samples"), **When** `list_item_relations(A)` is called, **Then** both relations are returned.
2. **Given** item A has relations to B ("covers") and C ("samples"), **When** `list_item_relations(A, relation_type="covers")` is called, **Then** only the relation to B is returned.
3. **Given** item B is a target of relations from A and C, **When** `list_related_items(B, direction="incoming")` is called, **Then** both A and C are returned.
4. **Given** an item has no relations, **When** `list_item_relations(item_id)` is called, **Then** an empty list is returned.

---

### User Story 3 — Remove a Relation (Priority: P2)

A library user removes a specific directed relation by its unique triple `(source_item_id, target_item_id, relation_type)`.

**Why this priority**: Mutation support (create + delete) is required for a complete CRUD API. Depends on P1 stories.

**Independent Test**: Create a relation, call `remove_item_relation(source, target, relation_type)`, then verify `list_item_relations` no longer includes it.

**Acceptance Scenarios**:

1. **Given** a relation exists, **When** `remove_item_relation(source, target, "covers")` is called, **Then** the relation is deleted and no longer returned by queries.
2. **Given** no relation exists for that triple, **When** `remove_item_relation` is called, **Then** `TaxomeshRelationError` is raised.

---

### User Story 4 — Relations Cascade on Item Deletion (Priority: P2)

When an item is deleted via the service layer, all relations where that item is either source or target are automatically removed.

**Why this priority**: Referential integrity. Without cascade, stale relations accumulate and break query results.

**Independent Test**: Create item A with relations to B and C. Delete A. Verify `list_item_relations(A)` returns empty, and querying B or C for incoming relations from A returns empty.

**Acceptance Scenarios**:

1. **Given** item A has outgoing relations to B and C, **When** item A is deleted, **Then** all those relations are removed.
2. **Given** item B is a target of relations from A and C, **When** item B is deleted, **Then** all incoming relations to B are removed.

---

### User Story 5 — Persist Relations in All Backends (Priority: P2)

Relations are durably persisted in the JSON, YAML, and Django backends. Relations survive a full load/save cycle in each backend.

**Why this priority**: Persistence is required for the feature to be useful in real applications; all maintained backends must be consistent.

**Independent Test**: Create relations, save to disk (JSON or YAML) or commit via Django ORM. Reload from storage. Verify all relations are present with correct field values.

**Acceptance Scenarios**:

1. **Given** relations are created via the JSON backend, **When** the repository is reloaded from disk, **Then** all relations are present with correct fields.
2. **Given** relations are created via the YAML backend, **When** the repository is reloaded, **Then** all relations are present.
3. **Given** relations are created via the Django backend, **When** queried via the ORM, **Then** all relations are stored in the database with correct fields and constraints.

---

### User Story 6 — Manage Relations via CLI (Priority: P3)

A user manages item relations from the command line using a `taxomesh item relation` command group.

**Why this priority**: CLI is a secondary surface over the service layer. Useful for scripts and quick inspection, but not blocking for library adopters.

**Independent Test**: Run `taxomesh item relation add`, `taxomesh item relation list`, `taxomesh item relation related`, and `taxomesh item relation delete` in sequence. Verify each command produces correct output and modifies state as expected.

**Acceptance Scenarios**:

1. **Given** two items exist, **When** `taxomesh item relation add <source> <target> <type>` is run, **Then** the relation is created and a success message is displayed.
2. **Given** relations exist, **When** `taxomesh item relation list <item_id>` is run, **Then** outgoing relations are displayed in a readable table.
3. **Given** relations exist, **When** `taxomesh item relation related <item_id>` is run, **Then** related items (with relation type) are displayed.
4. **Given** a relation exists, **When** `taxomesh item relation delete <source> <target> <type>` is run, **Then** the relation is removed and confirmed in the output.

---

### User Story 7 — Manage Relations in Django Admin (Priority: P3)

A Django admin user views and edits item relations through the admin interface. Outgoing relations are editable inline on the source item. Incoming relations are visible read-only on the target item. Self-relations are blocked with a clear validation error.

**Why this priority**: Admin is a convenience surface for Django adopters. Depends on the service layer being complete.

**Independent Test**: Open an item in Django admin, add an outgoing relation inline, save. Verify the relation appears. Attempt to add a self-relation; verify the admin rejects it with a readable error.

**Acceptance Scenarios**:

1. **Given** an item in Django admin, **When** an outgoing relation is added via inline and saved, **Then** the relation is persisted via the service layer.
2. **Given** an item is a target of relations, **When** the item is opened in admin, **Then** incoming relations are listed read-only.
3. **Given** a user sets source == target in the inline, **When** the form is submitted, **Then** Django admin shows a validation error blocking the save.

---

### Edge Cases

- What happens when `relate_items` is called with a non-existent `source_item_id` or `target_item_id`? → An error must be raised; no orphan relation is created.
- What happens when `sort_index` is not provided? → Defaults to `0`; relations without explicit ordering are still valid.
- What happens when `metadata` is not provided? → Defaults to an empty dict; the field is always present on the returned object.
- What happens when the same relation triple is added via two concurrent callers? → Upsert semantics ensure at most one record exists; no duplicate is created.
- What happens when an item with many relations is deleted? → All relations (both outgoing and incoming) are removed atomically.
- What happens when `list_related_items` is called with an unknown `direction` value? → An error is raised with a clear message.

## Requirements *(mandatory)*

### Functional Requirements

**Domain Model**

- **FR-001**: The library MUST expose a new `ItemRelationLink` entity with fields: `source_item_id` (UUID), `target_item_id` (UUID), `relation_type` (non-empty string), `sort_index` (integer, default 0), and `metadata` (key-value store, default empty).
- **FR-002**: `ItemRelationLink` MUST be immutably identified by the triple `(source_item_id, target_item_id, relation_type)`.
- **FR-003**: The library MUST reject any `ItemRelationLink` where `source_item_id == target_item_id` with a descriptive error.
- **FR-004**: The library MUST reject any `ItemRelationLink` where `relation_type` is an empty string or whitespace-only, with a descriptive error.
- **FR-004b**: `relation_type` MUST be normalised to lowercase at write time (before validation and before storage). Callers receive the normalised value on reads. `"covers"` and `"COVERS"` are therefore the same relation.

**Service API**

- **FR-005**: `relate_items(source_item_id, target_item_id, relation_type, *, sort_index=0, metadata=None)` MUST create or update the relation identified by the triple (upsert semantics).
- **FR-006**: `list_item_relations(item_id, *, relation_type=None, direction="outgoing")` MUST return all matching `ItemRelationLink` objects for the item; optional `relation_type` filter narrows results; `direction` accepts `"outgoing"` or `"incoming"`.
- **FR-007**: `list_related_items(item_id, *, relation_type=None, direction="outgoing")` MUST return the list of `Item` objects reachable from the given item via matching relations.
- **FR-008**: `remove_item_relation(source_item_id, target_item_id, relation_type)` MUST delete the specific relation or raise an error if it does not exist.
- **FR-009**: Deleting an item via the service layer MUST cascade-delete all relations where that item appears as source or target.

**Repository Protocol**

- **FR-010**: The `TaxomeshRepositoryBase` protocol MUST be extended with methods covering: add/update a relation, list relations (by item + optional type + direction), and delete a relation.
- **FR-011**: All three maintained backends (JSON file, YAML file, Django ORM) MUST implement the extended repository protocol.

**Persistence — JSON & YAML Backends**

- **FR-012**: The JSON backend MUST persist relations in the existing JSON file structure without breaking backward compatibility with existing taxonomy data.
- **FR-013**: The YAML backend MUST persist relations in the existing YAML file structure without breaking backward compatibility.

**Persistence — Django Backend**

- **FR-014**: A `ItemRelationLinkModel` Django ORM model MUST be defined with: `source_item` (FK to `ItemModel`), `target_item` (FK to `ItemModel`), `relation_type` (CharField), `sort_index` (IntegerField, default 0), `metadata` (JSONField, default dict).
- **FR-015**: A unique constraint MUST be enforced on `(source_item, target_item, relation_type)` at the database level.
- **FR-016**: Deleting an `ItemModel` MUST cascade-delete all associated `ItemRelationLinkModel` rows (both source and target FKs).
- **FR-017**: A Django migration MUST be provided for the new model.

**CLI**

- **FR-018**: A `taxomesh item relation` command group MUST be added as a sub-group of the `item` command, reflecting that relations exist exclusively between items.
- **FR-019**: `taxomesh item relation add <source_item_id> <target_item_id> <relation_type>` MUST create a relation, with optional `--sort-index INT` and repeatable `--metadata KEY=VALUE` flags (e.g. `--metadata source=discogs --metadata confidence=high`). Multiple `--metadata` flags are merged into a single dict.
- **FR-020**: `taxomesh item relation list <item_id>` MUST display outgoing relations in a readable table, with an optional `--type` filter and `--direction` flag.
- **FR-021**: `taxomesh item relation related <item_id>` MUST display items related to the given item, with optional `--type` and `--direction` flags.
- **FR-022**: `taxomesh item relation delete <source_item_id> <target_item_id> <relation_type>` MUST remove the relation and confirm success.

**Django Admin**

- **FR-023**: An `ItemRelationLinkModelAdmin` MUST be registered for `ItemRelationLinkModel` with list display showing source, target, relation type, and sort index.
- **FR-024**: `ItemModelAdmin` MUST include an inline for outgoing relations (editable) and a read-only section for incoming relations.
- **FR-025**: Admin writes to relations MUST go through the taxomesh service layer, not direct ORM saves.
- **FR-026**: Admin MUST reject self-relations with a user-readable validation error on form submission.

**Documentation**

- **FR-027**: `README.md` MUST document `ItemRelationLink` with Python API examples, CLI examples, and a Django admin note.
- **FR-028**: `README.md` MUST include a section explaining when to use categories vs item placement vs tags vs item relations.

### Key Entities

- **ItemRelationLink**: Represents a directed, typed relation between two items. Identified by the triple `(source_item_id, target_item_id, relation_type)`. Carries `sort_index` for ordering and `metadata` for arbitrary key-value data. Has no independent UUID — the triple is the primary key.
- **Item** (existing): The domain entity being linked. Items are identified by UUID. Relations reference items by their ID; items are otherwise unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four service API methods (`relate_items`, `list_item_relations`, `list_related_items`, `remove_item_relation`) pass their test suites with no failures.
- **SC-002**: Relations created in the JSON backend survive a full serialize → deserialize round-trip with all field values intact.
- **SC-003**: Relations created in the YAML backend survive a full serialize → deserialize round-trip with all field values intact.
- **SC-004**: Relations created in the Django backend are retrievable from the database with all field values and constraints enforced.
- **SC-005**: All four CLI subcommands (`add`, `list`, `related`, `delete`) complete successfully and produce human-readable output in their acceptance scenarios.
- **SC-006**: Attempting to create a self-relation is rejected at every layer (service, CLI, Django admin) without storing any data.
- **SC-007**: Attempting to create a relation with an empty `relation_type` is rejected at the domain model level before any persistence occurs.
- **SC-008**: Deleting an item results in zero orphaned relations in any backend.
- **SC-009**: The test suite maintains at least 80% coverage across all new and modified modules.
- **SC-010**: All existing tests continue to pass after this feature is merged (no regressions in category, item, or taxonomy graph behavior).

## Assumptions

- `relation_type` is a free-form string with no predefined enumeration; the library enforces non-emptiness and normalises to lowercase on write.
- `direction="outgoing"` is the default for all list operations; callers must explicitly pass `direction="incoming"` for reverse lookups.
- The `TaxomeshGraph` type remains category-centric and is not extended to include relations.
- Upsert behavior on the triple key means the last write wins for `sort_index` and `metadata`.
- `metadata` values must be JSON-serializable (strings, numbers, booleans, lists, dicts, null); the library validates this at write time.
- The CLI reads configuration from the existing TOML config mechanism to determine which backend and file path to use.
- `list_related_items` returns `Item` objects, not `ItemRelationLink` objects; callers who need the relation metadata should use `list_item_relations`.
- Non-existent item IDs passed to `relate_items` raise a lookup error; the service does not create items implicitly.

## Clarifications

### Session 2026-03-08

- Q: When `remove_item_relation` is called for a triple that does not exist, should it raise or return silently? → A: Raise `TaxomeshRelationError` (Option A). Consistent with FR-008 and the no-silent-failures principle.
- Q: Should `relation_type` matching be case-sensitive or case-insensitive? → A: Case-insensitive; normalise to lowercase on write (Option B). `"covers"` and `"COVERS"` are the same relation.
- Q: What format should the CLI `--metadata` flag use for `taxomesh item relation add`? → A: Repeatable `KEY=VALUE` pairs (Option A), e.g. `--metadata source=discogs --metadata confidence=high`; merged into a single dict.
