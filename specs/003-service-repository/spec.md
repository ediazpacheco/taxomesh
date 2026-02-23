# Feature Specification: Service Layer and Pluggable Storage

**Feature Branch**: `003-service-repository`
**Created**: 2026-02-22
**Status**: Draft
**Input**: User description: "TaxomeshService, RepositoryBase and a JsonRepository (inheriting from RepositoryBase). TaxomeshService is the single public facade for taxomesh. It must support: Managing categories (create, get, list, delete), Managing items (create, get, list, delete), Managing tags (create, assign, remove). Pluggable storage backend using RepositoryBase interface. JsonRepository is the default storage adapter. It persists data to a JSON file on disk. Non-goals: Async interface, Query/search capabilities (future spec), SQLite adapter (future spec)"
*Note: the original description says "RepositoryBase" and "inheriting from RepositoryBase"; the design adopts `TaxomeshRepositoryBase` (see FR-014) with structural typing — no inheritance required (see Decision 1 in research.md).*

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Manage categories through the service (Priority: P1)

A developer wants to organise their items into categories using the taxomesh library. They interact exclusively with the `TaxomeshService` — they never touch storage directly. They create named categories, retrieve them by identity, list all categories at once, and delete ones that are no longer needed. The service ensures that operations on non-existent categories are reported as errors rather than silently failing.

**Why this priority**: Category management is the core purpose of the library. Every other organisational feature (item placement, tag assignment) depends on categories existing. A service that can manage categories is a functional, demonstrable MVP.

**Independent Test**: Can be fully tested by constructing a `TaxomeshService` backed by any conforming storage, executing create → get → list → delete operations, and verifying outcomes without inspecting storage internals.

**Acceptance Scenarios**:

1. **Given** a service is constructed, **When** a developer creates a category with a valid name, **Then** the service returns the newly created category with a unique identifier assigned by the library.
2. **Given** a category exists, **When** a developer retrieves it by its identifier, **Then** the service returns the category with all its fields intact.
3. **Given** a category does not exist, **When** a developer attempts to retrieve it by identifier, **Then** the service raises a typed not-found error (no `None` return).
4. **Given** several categories have been created, **When** a developer lists all categories, **Then** all previously created categories are returned in the result.
5. **Given** a category exists, **When** a developer deletes it by identifier, **Then** the operation succeeds and a subsequent retrieval of the same identifier raises a not-found error.
6. **Given** a category does not exist, **When** a developer attempts to delete it, **Then** the service raises a typed not-found error.

---

### User Story 2 — Manage items through the service (Priority: P1)

A developer wants to register references to their own entities (products, documents, songs, etc.) inside taxomesh. They supply an external identifier that belongs to their own system; the library assigns an internal identifier. They can retrieve, list, and delete items. All operations go through `TaxomeshService`.

**Why this priority**: Items are the atomic units that categories and tags are applied to. The service is not useful without item management. This story ranks equal with category management.

**Independent Test**: Can be fully tested by constructing a `TaxomeshService`, creating items with various external identifier types, and verifying retrieval, listing, and deletion outcomes.

**Acceptance Scenarios**:

1. **Given** a developer provides an external identifier, **When** an item is created via the service, **Then** the service returns the item with a library-assigned internal identifier distinct from the external one.
2. **Given** an item exists, **When** a developer retrieves it by its internal identifier, **Then** the service returns the item with all its fields intact.
3. **Given** an item does not exist, **When** a developer retrieves it by internal identifier, **Then** the service raises a typed not-found error.
4. **Given** several items have been created, **When** a developer lists all items, **Then** all previously created items are returned.
5. **Given** an item exists, **When** a developer deletes it by internal identifier, **Then** the operation succeeds and a subsequent retrieval raises a not-found error.
6. **Given** an item does not exist, **When** a developer attempts to delete it, **Then** the service raises a typed not-found error.

---

### User Story 3 — Manage tags through the service (Priority: P2)

A developer wants to attach short labels (tags) to items and later remove those labels. They first create a tag entity, then assign it to one or more items, and can remove the assignment when no longer needed. All operations are synchronous and go through `TaxomeshService`.

**Why this priority**: Tags are an optional secondary classification layer. The library is fully functional for category-based organisation without tags; this story adds labelling capability on top.

**Independent Test**: Can be fully tested by creating a service, creating a tag and an item, assigning the tag to the item, verifying the assignment, and then removing it.

**Acceptance Scenarios**:

1. **Given** a developer provides a valid tag name, **When** a tag is created via the service, **Then** the service returns the new tag with a unique identifier.
2. **Given** a tag and an item both exist, **When** the tag is assigned to the item, **Then** the operation succeeds with no error.
3. **Given** a tag is already assigned to an item, **When** the same assignment is requested again, **Then** the operation is idempotent — it succeeds without error and produces no duplicate.
4. **Given** a tag and an item both exist with an active assignment, **When** the tag is removed from the item, **Then** the assignment no longer exists.
5. **Given** a tag or item that does not exist, **When** an assign or remove operation references it, **Then** the service raises a typed not-found error.

---

### User Story 4 — Use a custom storage backend (Priority: P2)

A developer building on taxomesh wants to plug in their own storage backend — for example, a test double, an in-memory store, or a future database adapter. They provide any object that satisfies the storage interface at service construction time, and `TaxomeshService` delegates all reads and writes to it without requiring them to inherit from any class.

**Why this priority**: The pluggable backend is a fundamental architectural promise of the library. Without it, consumers are locked into the bundled file-based adapter. This story must be verified before the service layer can be considered complete.

**Independent Test**: Can be fully tested by implementing a minimal in-memory object that matches the storage contract and confirming that `TaxomeshService` uses it correctly for all CRUD operations.

**Acceptance Scenarios**:

1. **Given** a developer provides a custom object satisfying the storage contract, **When** `TaxomeshService` is constructed with that object, **Then** all service operations delegate to the custom backend without error.
2. **Given** `TaxomeshService` is constructed without specifying a storage backend, **When** any operation is performed, **Then** the service uses the built-in file-based backend automatically.
3. **Given** a custom backend that tracks which methods are called, **When** a service operation is performed, **Then** only the expected storage methods are invoked — no hidden direct I/O occurs inside the service.

---

### User Story 5 — Persist data across process restarts with JsonRepository (Priority: P2)

A developer wants their taxomesh data (categories, items, tags, assignments) to survive application restarts. They configure `JsonRepository` with a file path; the library reads existing data from that file at start-up and writes updated data back after each mutating operation. When they restart their process and create a new service pointing at the same file, all previously stored data is available.

**Why this priority**: Without durable storage, taxomesh is only useful for in-process experiments. This story delivers the practical, production-ready default storage experience.

**Independent Test**: Can be fully tested by creating and populating a service backed by `JsonRepository`, destroying the service, creating a new service reading the same file, and confirming all previously written records are present.

**Acceptance Scenarios**:

1. **Given** a `JsonRepository` is configured with a file path and the file does not yet exist, **When** the repository is created, **Then** the file (and any missing parent directories) is initialised and the service can operate immediately.
2. **Given** data has been written through a service backed by `JsonRepository`, **When** a new service is created pointing at the same file, **Then** all previously written categories, items, tags, and assignments are available through the new service.
3. **Given** a write operation (create, delete, assign, remove) completes, **When** the file is inspected, **Then** its contents reflect the current state — no data is buffered exclusively in memory between writes.
4. **Given** a `JsonRepository` is given a path to a file that contains invalid or unrecognisable content, **When** the repository is constructed, **Then** a descriptive error is raised before any operation is attempted.

---

### User Story 6 — Manage category parent relationships with DAG integrity (Priority: P1)

A developer building a taxonomy wants to express parent–child relationships between categories (e.g., "Animals" is a parent of "Mammals", and "Mammals" is a parent of "Dogs"). Because categories form a Directed Acyclic Graph (DAG) rather than a simple tree, each category may have multiple parents. The service prevents the developer from accidentally introducing a cycle (e.g., making "Animals" a child of "Dogs", which would close a loop).

**Why this priority**: The DAG structure is the raison d'être of taxomesh. Without the ability to record category parent links — and without cycle detection to keep the graph valid — the library cannot fulfil its core architectural promise (Constitution Principle VI).

**Independent Test**: Can be fully tested by constructing a `TaxomeshService` backed by any conforming storage, adding parent links, and verifying both happy-path link creation and cycle-detection errors.

**Acceptance Scenarios**:

1. **Given** two categories exist, **When** a developer adds one as a parent of the other, **Then** the service returns a link record containing both category identifiers.
2. **Given** category A is already a parent of category B, **When** a developer attempts to add B as a parent of A (creating a 2-node cycle), **Then** the service raises `TaxomeshCyclicDependencyError`.
3. **Given** a chain A → B → C exists (A is a parent of B, B is a parent of C), **When** a developer attempts to add A as a parent of C (closing a 3-node cycle), **Then** the service raises `TaxomeshCyclicDependencyError`.
4. **Given** a category exists, **When** a developer attempts to add that category as its own parent (self-loop), **Then** the service raises `TaxomeshCyclicDependencyError`.
5. **Given** the proposed parent category does not exist, **When** a developer calls add category parent, **Then** the service raises `TaxomeshCategoryNotFoundError`.

---

### Edge Cases

- What happens when getting a category, item, or tag by an identifier that has never existed? → A typed not-found error is raised (no `None` return, no silent no-op).
- What happens when deleting a category that has items placed under it or parent-links referencing it? → The category record is deleted; orphaned placement and parent-link records are not automatically cleaned up at this layer. Referential cleanup is a future concern.
- What happens when assigning a tag to an item and both exist, but the storage write fails? → The error propagates as a typed repository error; no partial state is silently committed.
- What happens when two categories are created with identical names? → Both are accepted; the service does not enforce name uniqueness. That is an application-layer concern.
- What happens when the JSON file path is a directory, not a file? → A descriptive error is raised at repository construction time.
- What happens when `JsonRepository` is given no file path argument? → A sensible default file name is used in the current working directory.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST expose `TaxomeshService` as the sole entry point for all category, item, and tag operations. No other service class is part of the public interface.
- **FR-002**: `TaxomeshService` MUST accept an optional storage backend at construction. When none is provided, it MUST automatically use `JsonRepository` with a default file path.
- **FR-003**: `TaxomeshService` MUST provide a **create category** operation that accepts a name (and optional description and metadata) and returns the created category with a library-assigned identifier.
- **FR-004**: `TaxomeshService` MUST provide a **get category** operation that returns the category for a given identifier, or raises `TaxomeshCategoryNotFoundError` if it does not exist.
- **FR-005**: `TaxomeshService` MUST provide a **list categories** operation that returns all stored categories.
- **FR-006**: `TaxomeshService` MUST provide a **delete category** operation that removes the category for a given identifier, or raises `TaxomeshCategoryNotFoundError` if it does not exist.
- **FR-007**: `TaxomeshService` MUST provide a **create item** operation that accepts an external identifier (and optional metadata) and returns the created item with a library-assigned internal identifier.
- **FR-008**: `TaxomeshService` MUST provide a **get item** operation that returns the item for a given internal identifier, or raises `TaxomeshItemNotFoundError` if it does not exist.
- **FR-009**: `TaxomeshService` MUST provide a **list items** operation that returns all stored items.
- **FR-010**: `TaxomeshService` MUST provide a **delete item** operation that removes the item for a given internal identifier, or raises `TaxomeshItemNotFoundError` if it does not exist.
- **FR-011**: `TaxomeshService` MUST provide a **create tag** operation that accepts a name (and optional metadata) and returns the created tag with a library-assigned identifier.
- **FR-012**: `TaxomeshService` MUST provide an **assign tag** operation that associates an existing tag with an existing item. If the tag or item does not exist, it MUST raise the appropriate not-found error. If the association already exists, the operation MUST be idempotent.
- **FR-013**: `TaxomeshService` MUST provide a **remove tag** operation that removes the association between a tag and an item. If the tag or item does not exist, it MUST raise the appropriate not-found error.
- **FR-014**: The library MUST define a `TaxomeshRepositoryBase` storage interface. Any object that implements all required storage methods is a valid backend — explicit inheritance MUST NOT be required.
- **FR-015**: `JsonRepository` MUST read all stored data from a configured file path at initialisation and write the full current state back to that file after every mutating operation.
- **FR-016**: `JsonRepository` MUST create the storage file (and any missing parent directories) if it does not exist at construction time.
- **FR-017**: `JsonRepository` MUST raise a descriptive typed error at construction time if the storage file exists but cannot be parsed as valid storage content.
- **FR-018**: All error conditions MUST be reported as typed errors drawn from the existing `TaxomeshError` hierarchy. The service MUST NEVER return `None` for a requested entity, nor swallow errors silently.
- **FR-019**: `TaxomeshService` MUST provide an **add category parent** operation that records a parent–child relationship between two existing categories and returns the created link record.
- **FR-020**: If adding a parent relationship would create a cycle in the category graph (including a self-loop), the operation MUST raise `TaxomeshCyclicDependencyError` before persisting any change.
- **FR-021**: `TaxomeshRepositoryBase` MUST include `save_category_parent_link(link: CategoryParentLink) -> None` and `list_category_parent_links() -> list[CategoryParentLink]` methods, making the full Protocol 15 methods.

### Key Entities

- **TaxomeshService**: The single entry point for all library operations. Accepts an optional storage backend at construction. Delegates all reads and writes to the backend; contains no storage logic itself.
- **TaxomeshRepositoryBase**: A structural storage interface. Defines the contract that any storage backend must satisfy. Does not require inheritance — structural compatibility is sufficient. Consists of 15 methods covering categories, items, tags, tag-item associations, and category parent links.
- **JsonRepository**: The default storage backend. Reads and writes all data to a single JSON file on disk. The file path is configurable; a sensible default is used when not specified.
- **CategoryParentLink**: A link record that records one parent–child category relationship. Belongs to the domain layer (`taxomesh/domain/models.py`). Carries `category_id`, `parent_category_id`, and `sort_index`.
- **DAG cycle-detection utility** (`taxomesh/domain/dag.py`): A pure domain function (`check_no_cycle`) that performs a depth-first search over existing parent links to detect cycles before a new link is persisted. Invoked by `TaxomeshService.add_category_parent`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can complete the full category lifecycle (create → get → list → delete) using only `TaxomeshService`, with no knowledge of or dependency on the storage layer, in a single process run.
- **SC-002**: A developer can complete the full item lifecycle (create → get → list → delete) using only `TaxomeshService`.
- **SC-003**: A developer can complete the full tag lifecycle (create → assign to item → remove from item) using only `TaxomeshService`.
- **SC-004**: A developer can substitute the default storage backend with any custom object that satisfies `TaxomeshRepositoryBase`, without modifying `TaxomeshService` or any other library file.
- **SC-005**: Data written in one process run through `JsonRepository` is fully readable in a subsequent process run using the same file — zero records are lost between restarts.
- **SC-006**: Every operation that targets a non-existent entity raises a specific, catchable typed error. No operation returns `None` for a missing entity or raises a bare Python exception.
- **SC-007**: The service and repository layers achieve ≥ 80% test coverage; all CRUD operations and error paths are covered by tests.
- **SC-008**: Adding any parent relationship that would create a cycle (including a self-loop or an indirect cycle of any length) raises `TaxomeshCyclicDependencyError` before any data is persisted.

---

## Assumptions

- "Remove tag" means removing the tag-item association (i.e., unassigning the tag from the item), not deleting the tag entity. Tag deletion is not part of this feature.
- Category deletion does not cascade-delete item placement links (`ItemParentLink`) or category parent links (`CategoryParentLink`) that reference the deleted category. Orphaned link cleanup is a future concern.
- `TaxomeshRepositoryBase` satisfies the constitution's Protocol requirement — structural typing, no inheritance needed.
- `JsonRepository` stores all data in a single flat JSON file. No database, no separate files per entity type.
- When no file path is supplied to `JsonRepository`, a default file named `taxomesh.json` in the current working directory is used.
- All operations are synchronous. An async interface is explicitly out of scope for this feature.
- Query and search operations (e.g., find items in a category, find categories by tag) are out of scope; only full-collection listing is included.
- The service does not enforce business constraints such as name uniqueness or referential integrity between entities — those remain repository and application-layer concerns.
- DAG cycle detection is performed in the domain layer (`domain/dag.py`) using a depth-first search over all existing `CategoryParentLink` records. It is invoked by the service before persisting any new parent link.
- `add_category_parent` does not check for duplicate links (the same pair already having a link). Idempotency of parent links is a future concern.
