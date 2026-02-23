# Research: Service Layer and Pluggable Storage (003-service-repository)

**Date**: 2026-02-22
**Status**: Complete — no NEEDS CLARIFICATION markers were present in the spec.

All design decisions are resolved below with rationale and alternatives considered.

---

## Decision 1 — `typing.Protocol` without `@runtime_checkable` for `TaxomeshRepositoryBase`

**Decision**: `TaxomeshRepositoryBase` is defined as `typing.Protocol` (Python 3.11 stdlib).
`@runtime_checkable` is NOT applied.

**Rationale**:
- Constitution Principle III mandates a structural interface: "Any class that implements the required
  methods is a valid repository — explicit inheritance is not required."
- `typing.Protocol` is exactly this mechanism in Python 3.11. mypy `--strict` verifies structural
  compliance at type-check time — no `isinstance()` check at runtime is needed.
- `@runtime_checkable` adds overhead to every attribute access and only checks method *names*,
  not signatures; it provides a false sense of safety and is unnecessary when mypy is the
  verification tool.
- The constitution (Principle IV) mandates mypy strict; structural correctness is therefore
  guaranteed statically.

**Alternatives considered**:
- Abstract base class (`ABC`) — rejected: requires explicit inheritance; violates Principle III.
- `@runtime_checkable` Protocol — rejected: runtime overhead, shallow check (names only, not
  signatures), unnecessary when mypy strict is the gate.

---

## Decision 2 — Pydantic v2 JSON round-trip strategy

**Decision**: Serialize models to JSON-safe dicts with `model.model_dump(mode='json')`.
Reconstruct with `ModelClass.model_validate(data)`.

**Rationale**:
- `model_dump(mode='json')` converts all non-JSON-native types to their JSON equivalents:
  `UUID` → `str`, `datetime` → ISO string. This is required for `uuid.UUID` fields since
  `json.dumps` cannot serialise `UUID` objects natively.
- `model_validate(data)` reconstructs typed models from plain dicts, running all Pydantic
  validators including `max_length` constraints and union disambiguation.
- This round-trip preserves all domain constraints and works with `json.dumps` / `json.loads`
  directly, requiring no custom JSON encoder.

**Alternatives considered**:
- `model_dump()` (default mode) — rejected: returns `UUID` objects which are not JSON-serialisable
  without a custom encoder.
- `model_dump_json()` — produces a JSON string, not a dict; requires an extra parse step when
  building a composite document. Not wrong, but less convenient for building a structured JSON file.
- Custom JSON encoder — rejected: adds complexity not justified when Pydantic already handles it.

---

## Decision 3 — Atomic write strategy for `JsonRepository`

**Decision**: Write the full current state to a sibling temporary file, then use `os.replace()`
(POSIX atomic rename) to replace the target file in a single operation.

**Rationale**:
- Writing directly to the target file risks leaving a partially-written, unreadable file if the
  process is killed mid-write. A subsequent startup would then fail to load the repository.
- `os.replace()` is atomic on POSIX systems (Linux, macOS): the filesystem either has the old
  version or the new version — never a partial state. On Windows it is not guaranteed atomic but
  is still safer than an in-place overwrite.
- `os.fsync(fd)` must be called on the temp file descriptor before closing it and before the
  rename. Without `fsync`, the OS may not have flushed write buffers to disk; a kernel crash
  after rename but before flush would produce a zero-length or truncated target file.
- The temp file must be written to the same directory as the target so that `os.replace()` is
  always an in-filesystem rename (guaranteed atomic) rather than a cross-filesystem copy+delete.
- Writing the full state (not appending deltas) keeps the implementation simple: no append log,
  no compaction step, no recovery logic.

**Alternatives considered**:
- In-place write (open + truncate + write) — rejected: partial writes produce a corrupt file on
  crash; not recoverable without a backup.
- Write-ahead log / append-only delta — rejected: over-engineered for the scale and complexity of
  this feature; compaction and recovery logic would dominate the implementation.
- `fcntl` file locking — not needed: taxomesh is a single-process library; concurrent access is
  not a declared requirement.

---

## Decision 4 — Exception module placement

**Decision**: All exceptions live in `taxomesh/exceptions.py` at the package root and are
re-exported from `taxomesh/__init__.py`.

**Rationale**:
- Exceptions are cross-cutting: raised by `application/service.py` (not-found errors) and by
  `adapters/repositories/json_repository.py` (repository errors).
- Placing them in `domain/` would force `application/` and `adapters/` to import from `domain/`,
  which is correct (domain is innermost), but exceptions are not domain *models* — they are
  library-level error signals.
- Placing them at `taxomesh/exceptions.py` lets all layers import them without circular imports,
  and aligns with Principle V (exception hierarchy is part of the public API).
- The import chain `exceptions.py` → nothing ensures it can be imported by any layer freely.

**Alternatives considered**:
- `taxomesh/domain/exceptions.py` — acceptable but semantically odd; exceptions like
  `TaxomeshRepositoryError` are not domain concepts.
- One file per layer — rejected: fragmented; the constitution defines a single hierarchy.

---

## Decision 5 — Repository method signatures: return `T | None` vs raise

**Decision**: Repository methods that look up a single entity by ID return `T | None` (where `T`
is the entity type). The service layer converts `None` into the appropriate typed `NotFoundError`.
Repository delete methods return `bool` (`True` = found and deleted, `False` = not found).

**Rationale**:
- The repository is an internal abstraction. Returning `None` for a missing entity is idiomatic
  Python and keeps the repository free of knowledge about which error class to raise.
- The service layer owns the decision of which typed error to surface (e.g., `TaxomeshCategoryNotFoundError`
  vs `TaxomeshTagNotFoundError`). This is the correct layer for that decision.
- `bool` returns for delete are a clean signal without coupling the repo to the exception hierarchy.

**Alternatives considered**:
- Repository raises `NotFoundError` directly — rejected: requires the repo to import exceptions;
  also makes repositories harder to adapt (a database repo might want to map its own NotFoundException).
- Repository raises `KeyError` — rejected: raw Python exceptions violate Principle V.

---

## Decision 6 — `remove_tag` when the association is absent

**Decision**: If both the tag entity and the item entity exist but no association exists between
them, `remove_tag` is a no-op (succeeds silently). No error is raised.

**Rationale**:
- The spec (FR-013) mandates errors only when "the tag or item does not exist" — i.e., the
  entity-not-found case. A missing association is not an entity-not-found condition.
- Treating a missing association as an error would make `remove_tag` non-idempotent, which
  complicates retry-safe consumer code.
- Symmetric with `assign_tag` which is explicitly idempotent (FR-012).

**Alternatives considered**:
- Raise `TaxomeshNotFoundError` for missing association — rejected: not supported by spec text
  (FR-013 only covers tag/item entity absence); would break idempotency.

---

## Decision 7 — `TaxomeshService` default repository instantiation

**Decision**: When no `repository` argument is passed to `TaxomeshService.__init__`, the service
instantiates `JsonRepository` with a default file path of `Path("taxomesh.json")` (relative to
the process working directory).

**Rationale**:
- Constitution Principle II: "If no repository is provided, it defaults to `JsonRepository`."
- Using the current working directory follows the Unix convention for tool defaults; no hidden
  application-support directory or platform-specific path logic is needed.
- The path is predictable and overridable by the consumer.

**Alternatives considered**:
- `platformdirs` / user home directory — rejected: adds a dependency and platform-specific logic
  not justified for a library default.
- Hardcoded absolute path — rejected: breaks portability.

---

## Decision 10 — Protocol tag association: domain-level `assign_tag` / `remove_tag` instead of `save_item_tag_link` / `delete_item_tag_link`

**Decision**: `TaxomeshRepositoryBase` exposes `assign_tag(tag_id, item_id) -> None` and
`remove_tag(tag_id, item_id) -> bool`. The `ItemTagLink` domain model is an internal
implementation detail of each repository adapter; it does NOT appear in the Protocol contract.

**Rationale**:
- `save_item_tag_link(link: ItemTagLink)` leaks an internal join-record type into the Protocol,
  forcing every repository implementer to construct `ItemTagLink` objects even if their storage
  engine (SQL, Redis) handles associations differently.
- Domain-level verbs (`assign_tag`, `remove_tag`) express the operation semantics directly;
  they are the same names already used in `TaxomeshService`, making the call chain transparent.
- Idempotency and no-op semantics live in the repository, which is the correct layer: the
  service validates entity existence, then delegates the association write to the repo without
  constructing a link object.
- Follows the hexagonal principle: the Protocol is a **port** defined in terms of domain
  concepts, not storage implementation details.

**Alternatives considered**:
- Keep `save_item_tag_link` / `delete_item_tag_link` on the Protocol — rejected: leaks the
  `ItemTagLink` join-record type into the port; forces all adapters to depend on a storage
  artifact.
- Embed tag associations in `save_item` (pass `list[UUID]` tags with the item) — rejected:
  over-couples item writes to tag assignment; makes partial updates harder.

---

## Decision 9 — Exception naming: `Taxomesh` prefix on all exception classes

**Decision**: Every exception in the hierarchy carries the `Taxomesh` prefix:
`TaxomeshCategoryNotFoundError`, `TaxomeshItemNotFoundError`, `TaxomeshTagNotFoundError`,
`TaxomeshCyclicDependencyError`. The intermediate base classes (`TaxomeshNotFoundError`,
`TaxomeshValidationError`) and the root (`TaxomeshError`) already had the prefix; leaf
classes now match.

**Rationale**:
- Consistency: the earlier mixed pattern (prefix on bases and `TaxomeshRepositoryError`, no
  prefix on entity-specific leaves) was an accident of incremental design, not a deliberate rule.
- Library disambiguation: `TaxomeshItemNotFoundError` is unambiguous when a codebase uses
  multiple libraries that each define an `ItemNotFoundError`. `except ItemNotFoundError` catches
  the wrong class; `except TaxomeshItemNotFoundError` does not.
- The naming convention in the constitution (Principle V and Naming Conventions table) is
  updated to `Taxomesh prefix + Descriptive + Error` as the single rule for all exception classes.

**Alternatives considered**:
- No prefix on leaf classes — rejected: `ItemNotFoundError` collides with other libraries;
  inconsistent with `TaxomeshRepositoryError` which was always a leaf with the prefix.
- Prefix only on bases — rejected: same collision problem for leaf exceptions; the main benefit
  of typed exceptions is catching them specifically, so the names must be unambiguous.

---

## Decision 8 — `category_id` and `tag_id` generation responsibility

**Decision**: `TaxomeshService.create_category` and `TaxomeshService.create_tag` generate a fresh
`uuid4()` for `category_id` and `tag_id` respectively before constructing the domain model.
`Item.item_id` already auto-generates via `Field(default_factory=uuid4)` — no service-side
generation needed.

**Rationale**:
- `Category.category_id` and `Tag.tag_id` are declared as required fields with no default.
  The service must supply them since the domain model does not auto-generate them.
- Auto-generation in the service (not the repo) keeps ID generation deterministic and testable.
- `Item.item_id` already has `default_factory=uuid4` — no change needed.

**Alternatives considered**:
- Generate in the repository — rejected: IDs should be known before storage; the service needs
  to return the created entity with its ID immediately.
- Add `default_factory=uuid4` to `Category.category_id` and `Tag.tag_id` — rejected: that is a
  domain model change outside this feature's scope. The service generating IDs is consistent with
  how other frameworks handle this pattern.

---

## Decision 12 — DAG cycle detection: domain-layer DFS in `taxomesh/domain/dag.py`

**Decision**: Cycle detection lives in `taxomesh/domain/dag.py` as a pure function
`check_no_cycle(category_id, parent_id, existing_links)`. It builds a `dict[UUID, list[UUID]]`
parent map from `existing_links` and performs a depth-first search (DFS) starting from
`parent_id`. If `category_id` is reachable, the proposed link would close a cycle.
The service calls `check_no_cycle` before calling `repo.save_category_parent_link`.

**Rationale**:
- Constitution Principle VI mandates: "The service layer MUST call `check_no_cycle` before
  persisting any new parent link."
- Domain layer is the correct location for graph integrity rules: the DAG constraint is a domain
  invariant, not a storage concern. Placing it in `domain/` keeps it isolated from persistence.
- A DFS over the existing links (provided by `list_category_parent_links`) is O(V + E) where V is
  the number of distinct categories and E is the number of existing parent links. For the expected
  scale of taxomesh (human-scale taxonomies), this is always fast.
- A pure function (no class, no state) is the simplest implementation: easy to test, easy to audit.

**Alternatives considered**:
- Cycle detection in the service directly — rejected: mixes graph logic into the application layer;
  harder to test in isolation and violates the domain-layer responsibility rule.
- Cycle detection in the repository — rejected: the repository is a storage abstraction; adding
  graph traversal logic there breaks the single-responsibility principle and forces every adapter
  to re-implement the algorithm.
- Topological sort over the full graph — rejected: more complex than needed; DFS from a single
  source node is sufficient and avoids constructing the full sorted order.

---

## Decision 11 — Lazy `application → adapters` import in `TaxomeshService.__init__`

**Decision**: `TaxomeshService.__init__` contains a lazy `import JsonRepository` inside an
`if repository is None:` guard. This is the only `application → adapters` import in the service
layer and is the designated composition root for the default backend.

**Rationale**:
- Constitution Principle II mandates: "If no repository is provided, it defaults to
  `JsonRepository`." Fulfilling this inside `__init__` is the most ergonomic pattern — the caller
  needs no knowledge of adapters to use the library.
- A strict `adapters → application` dependency graph would require callers to always supply a
  repository, breaking the "zero-config" ergonomic contract of Principle II.
- The lazy import (`if repository is None: from …`) confines the `application → adapters`
  dependency to a single guard, making it easy to audit and remove if the design changes.
- Constitution v1.2.1 explicitly allows this pattern under the "Composition-root exception"
  added to Principle I.

**Alternatives considered**:
- Make `repository` a required argument (no default) — rejected: violates Principle II; forces
  every consumer to import and instantiate `JsonRepository` manually even for the common case.
- Move the default instantiation to `taxomesh/__init__.py` as a module-level expression — rejected:
  creates an eager file-system side-effect on every import of `taxomesh`, which is surprising and
  breaks library etiquette.
- Use a factory function (`make_default_service()`) instead — rejected: adds an extra public API
  surface for no ergonomic gain; the single-constructor pattern is simpler.
