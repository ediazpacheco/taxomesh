# Feature Specification: Core Domain Models

**Feature Branch**: `002-domain-models`
**Created**: 2026-02-22
**Status**: Implemented
**Input**: User description: "Core domain model layer — 7 classes (ModelBase, Item, Category, Tag, CategoryParentLink, ItemParentLink, ItemTagLink) with field-level constraints, UUID-based identifiers, and junction records for the DAG relationships."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reference external items (Priority: P1)

A developer wants to register references to their own entities (products, songs, documents, Etc) inside taxomesh without duplicating the entity data. They create an `Item` with an `external_id` that identifies the entity in their own system. taxomesh auto-assigns a unique internal identifier to each item. The developer can enable or disable an item without deleting it, and attach arbitrary key-value metadata for consumer-specific extensions.

**Why this priority**: This is the fundamental atom of the system — every other concept (categories, tags, orderings) is built on top of items. The library cannot do anything useful without a way to reference external entities.

**Independent Test**: Can be fully tested by constructing `Item` objects in isolation. Delivers a stable, validated reference type for external entities with auto-generated identity.

**Acceptance Scenarios**:

1. **Given** a developer provides only an `external_id` (UUID, integer, or string ≤ 256 chars), **When** an `Item` is constructed, **Then** it gains a unique internal UUID that was not provided by the caller, and `enabled` defaults to `True`.
2. **Given** a string `external_id` longer than 256 characters, **When** construction is attempted, **Then** it is rejected with a validation error before any object is created.
3. **Given** two separately constructed items with identical `external_id` values, **When** their internal identifiers are compared, **Then** they are distinct.
4. **Given** two constructed `Item` instances, **When** metadata keys are added to one, **Then** the other instance's metadata is unaffected.

---

### User Story 2 - Create and name taxonomy categories (Priority: P2)

A developer wants to create named categories to organize their items. Each category has a required name with a length limit and an optional description. Categories also carry arbitrary metadata for consumer-specific extensions.

**Why this priority**: Categories are the primary organizing structure of the taxonomy. Items and tags are associated to categories; the multi-parent DAG is built entirely from category nodes.

**Independent Test**: Can be fully tested by constructing `Category` objects in isolation. Delivers a validated category entity ready to participate in a hierarchy.

**Acceptance Scenarios**:

1. **Given** a valid `category_id` and a name of at most 256 characters, **When** a `Category` is constructed, **Then** `description` defaults to `None` and `metadata` defaults to an empty dictionary.
2. **Given** a name longer than 256 characters, **When** construction is attempted, **Then** it is rejected with a validation error.
3. **Given** a description longer than 100 000 characters, **When** construction is attempted, **Then** it is rejected with a validation error.

---

### User Story 3 - Create short free-form tags (Priority: P3)

A developer wants to attach concise labels to items. Tags are short (at most 25 characters), identified by a UUID, and also carry arbitrary metadata.

**Why this priority**: Tags are a secondary classification mechanism layered on top of categories. The core system is functional without them, but they complete the full feature set.

**Independent Test**: Can be fully tested by constructing `Tag` objects in isolation. Delivers a validated tag entity with a strict name-length constraint.

**Acceptance Scenarios**:

1. **Given** a valid `tag_id` and a name of at most 25 characters, **When** a `Tag` is constructed, **Then** it succeeds with an empty metadata dictionary.
2. **Given** a name longer than 25 characters, **When** construction is attempted, **Then** it is rejected with a validation error.
3. **Given** a constructed tag with a valid name, **When** the name field is mutated to a value exceeding 25 characters, **Then** the mutation is rejected with a validation error.

---

### User Story 4 - Build a multi-parent category hierarchy (Priority: P2)

A developer wants to organize categories into a directed acyclic graph where each category can appear under multiple parent categories simultaneously. Each parent relationship carries an independent sort index that controls where the child appears within that particular parent's listing.

**Why this priority**: Multi-parent hierarchy with per-parent ordering is a core differentiator of taxomesh over single-parent tree taxonomies. This capability is what the library exists to provide.

**Independent Test**: Can be fully tested by constructing `CategoryParentLink` junction records in isolation. Delivers the relationship record needed to build and query a DAG.

**Acceptance Scenarios**:

1. **Given** a `category_id` and a `parent_category_id`, **When** a `CategoryParentLink` is constructed, **Then** `sort_index` defaults to `0`.
2. **Given** a `CategoryParentLink` with an explicit `sort_index`, **When** the record is retrieved, **Then** the sort index matches the provided value and is of integer type.

---

### User Story 5 - Assign items to categories (Priority: P2)

A developer wants to place items under one or more categories. Each item-category placement carries its own sort index, allowing the same item to appear at different positions depending on which category context is being browsed.

**Why this priority**: Placing items into categories is the primary use of the library. Without this junction, the taxonomy graph is disconnected from the data it organizes.

**Independent Test**: Can be fully tested by constructing `ItemParentLink` records in isolation. Delivers the relationship record needed to answer "which items belong to category X".

**Acceptance Scenarios**:

1. **Given** an `item_id` and a `category_id`, **When** an `ItemParentLink` is constructed, **Then** `sort_index` defaults to `0`.
2. **Given** an `ItemParentLink` with a specific `sort_index`, **When** retrieved, **Then** the sort index is preserved as an integer.

---

### User Story 6 - Link tags to items (Priority: P3)

A developer wants to record that a specific tag applies to a specific item. The association is captured as a junction record containing the tag's UUID and the item's internal UUID.

**Why this priority**: Tag-item associations complete the secondary classification layer. The library is usable without tags, so this story has lower priority than the category stories.

**Independent Test**: Can be fully tested by constructing `ItemTagLink` records in isolation. Delivers the relationship record needed to answer "which tags does item X have".

**Acceptance Scenarios**:

1. **Given** a `tag_id` and an `item_id`, **When** an `ItemTagLink` is constructed, **Then** both identifiers are preserved as UUIDs.

---

### Edge Cases

- What happens when a string `external_id` is exactly 256 characters? → Accepted (boundary is inclusive).
- What happens when `Category.description` is exactly 100 000 characters? → Accepted (boundary is inclusive).
- What happens when `Tag.name` is exactly 25 characters? → Accepted (boundary is inclusive).
- What happens when a field is mutated to an invalid value after construction? → The mutation is rejected with a validation error; the same constraints apply at write time as at construction time.
- What happens when two items are constructed with the same `external_id`? → Both are accepted; the library does not enforce `external_id` uniqueness at the model level — that is a repository-layer concern.
- What happens when `metadata` dicts are shared across instances by reference? → Each instance receives an independent `metadata` dict at construction time; mutations to one instance's metadata do not propagate to any other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST provide a base model type that all domain entities inherit from, configured with name-based field population and validation enforced at assignment time as well as at construction time.
- **FR-002**: The library MUST provide an `Item` type that auto-generates a unique internal identifier at construction time without requiring the caller to supply one.
- **FR-003**: `Item.external_id` MUST accept any one of the following: a UUID, an integer, or a string of at most 256 characters.
- **FR-004**: The library MUST reject construction of an `Item` whose `external_id` is a string longer than 256 characters.
- **FR-005**: The library MUST provide a `Category` type with a required name of at most 256 characters and an optional description of at most 100 000 characters.
- **FR-006**: The library MUST provide a `Tag` type with a name constrained to at most 25 characters.
- **FR-007**: The library MUST provide junction types (`CategoryParentLink`, `ItemParentLink`, `ItemTagLink`) that encode relationships via UUID references and carry no business logic.
- **FR-008**: Junction types representing ordered relationships (`CategoryParentLink`, `ItemParentLink`) MUST include a `sort_index` integer field that defaults to `0`.
- **FR-009**: The library MUST reject any field assignment that violates a declared constraint, both at initial construction and when a field value is mutated after construction.
- **FR-010**: Metadata fields on `Item`, `Category`, and `Tag` MUST default to independent empty dictionaries; mutations to one instance's metadata MUST NOT affect any other instance.

### Key Entities

- **Item**: A reference to any external entity managed by the consumer. Carries an auto-generated internal UUID (`item_id`), a consumer-supplied external identifier (`external_id`), an enabled flag for soft activation/deactivation, and open-ended metadata.
- **Category**: A named node in the taxonomy graph. Identified by a UUID, requires a short name (≤ 256 chars), optionally has a long description (≤ 100 000 chars), and carries metadata.
- **Tag**: A short free-form label. Identified by a UUID, requires a name (≤ 25 chars), and carries metadata.
- **CategoryParentLink**: A junction record encoding a single directed edge in the category DAG — from a child category to one of its parents — with a per-edge sort index.
- **ItemParentLink**: A junction record placing one item under one category, with a sort index controlling position within that category's listing.
- **ItemTagLink**: A junction record associating one tag with one item. Carries no sort index.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All seven model types can be constructed with valid inputs, in any order, with no shared mutable state between instances.
- **SC-002**: Every constraint violation (field too long, type mismatch) is detected and reported at the exact point of construction or field assignment — never silently ignored or deferred.
- **SC-003**: The domain model layer is usable with zero imports from any storage, network, framework, or I/O layer — the domain package has no external runtime dependencies beyond the validation library already used project-wide.
- **SC-004**: The model layer achieves ≥ 80% test coverage, with tests that cover every field's default value, every constraint boundary (inclusive), and every accepted type for polymorphic fields.

## Assumptions

- `external_id` uniqueness across items is NOT enforced at the model level. That is a repository-layer concern.
- `category_id`, `tag_id`, and `item_id` values in junction records are assumed to reference valid existing entities; referential integrity is a repository-layer concern.
- `Item.enabled` serves as a soft-delete / activation flag. The model layer defines the field but imposes no behavior on its value.
- `metadata` is intentionally typed as an open key-value dictionary to support consumer-defined extensions. The use of an untyped value in metadata fields is intentional and must be documented inline wherever it appears.
- All string length limits are inclusive upper bounds: 256 for `Item.external_id` (str branch) and `Category.name`; 100 000 for `Category.description`; 25 for `Tag.name`.
