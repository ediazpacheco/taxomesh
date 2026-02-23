# Research: Core Domain Models (002-domain-models)

**Date**: 2026-02-22
**Status**: Complete — no NEEDS CLARIFICATION markers were present in the spec.

All design decisions were fully specified in the feature input. This document records
the confirmed rationale for each decision so that future contributors understand *why*
each choice was made, not just *what* was chosen.

---

## Decision 1 — Pydantic v2 `BaseModel` as the model base

**Decision**: All domain entities inherit from `pydantic.BaseModel` via a shared `ModelBase`
base class.

**Rationale**:
- Pydantic v2 is already a mandatory transitive runtime dependency (pulled in by `fastapi ≥ 0.110`).
  Using it for domain models incurs zero additional dependency cost.
- Pydantic provides construction-time validation, typed field declarations, and `Annotated`
  constraints (`max_length`, `default_factory`) out of the box. Implementing equivalent
  behaviour with `@dataclass` would require custom `__post_init__` validators and a separate
  validation library.
- `validate_assignment=True` extends validation to post-construction field mutations at no cost.
- Pydantic v2 is compatible with `mypy --strict` when fields are fully annotated.

**Alternatives considered**:
- `@dataclass` — rejected: no constraint support, no mutation-time validation, requires a
  separate validation layer.
- `attrs` — rejected: not a project dependency; adds a dependency without benefit over Pydantic
  already in the runtime.
- `TypedDict` — rejected: no validation, no defaults, not instantiable as objects.

---

## Decision 2 — `ModelBase` with `populate_by_name=True` and `validate_assignment=True`

**Decision**: A shared `ModelBase(BaseModel)` carries `ConfigDict(populate_by_name=True,
validate_assignment=True)` and all domain models inherit from it.

**Rationale**:
- Centralising config in one base avoids repeating `model_config` in every class.
- `populate_by_name=True` ensures field names always work as keyword arguments even if aliases
  are added later; it is a forward-compatibility precaution with no runtime cost.
- `validate_assignment=True` means the same Pydantic validators that run at construction also
  run on any subsequent field mutation, satisfying FR-009 without any additional code.

**Alternatives considered**:
- `frozen=True` — rejected: the spec does not require immutability, and immutable models would
  break update patterns in application services.
- Duplicating `model_config` per class — rejected: violates DRY and makes future config changes
  fragile.

---

## Decision 3 — `UUID` for all primary and foreign identifiers

**Decision**: `item_id`, `category_id`, `tag_id`, `parent_category_id` are all typed as `UUID`
(from `uuid` stdlib). `Item.item_id` uses `Field(default_factory=uuid4)` for auto-generation.

**Rationale**:
- UUIDs are collision-resistant across distributed systems without requiring a central counter.
  When taxomesh is used by multiple processes or in multi-tenant scenarios, UUID-based IDs
  never conflict.
- `UUID` is a stdlib type — no extra dependency. Pydantic v2 natively validates `UUID` values.
- Auto-generation via `default_factory=uuid4` means callers never need to supply `item_id`,
  satisfying FR-002 with a single field declaration.

**Alternatives considered**:
- `int` auto-increment — rejected: requires a central sequence counter, which is a repository
  concern; the domain model layer must remain storage-agnostic.
- `str` UUIDs — rejected: loses type safety; `UUID` objects are comparable, hashable, and
  validated by Pydantic automatically.

---

## Decision 4 — `external_id` as a polymorphic union `UUID | Annotated[str, Field(max_length=256)] | int`

**Decision**: `Item.external_id` accepts three disjoint types. The `str` branch carries a
`max_length=256` constraint via `Annotated`. The `UUID` and `int` branches have no additional
constraint.

**Rationale**:
- taxomesh is explicitly designed for generic items. Consumer systems may identify their
  entities by UUID (common in modern systems), integer PK (legacy RDBMS), or string slug
  (content management systems). A union type at the model layer avoids forcing consumers
  into a type conversion layer.
- Pydantic v2 evaluates union branches left-to-right; `UUID` is tried first, then `str`
  (with max_length enforced), then `int`. This ordering prevents numeric strings from
  being misidentified.
- `max_length=256` on the `str` branch satisfies FR-004 and the constitution's string length
  rule for direct model fields.

**Alternatives considered**:
- Separate `Item` subclasses per ID type — rejected: over-engineered; consumers would need
  to pick the right subclass.
- `str` only — rejected: forces consumers with UUID/int IDs to stringify, losing type fidelity
  and making the API less ergonomic.

---

## Decision 5 — `metadata: dict[str, Any]` with `Field(default_factory=dict)`

**Decision**: `Item`, `Category`, and `Tag` each carry `metadata: dict[str, Any] = Field(default_factory=dict)`.

**Rationale**:
- `default_factory=dict` guarantees each instance gets an independent empty dict (satisfying
  FR-010). Using `= {}` as a default would share the same dict object across all instances
  that don't override it — a classic Python mutable-default bug.
- `dict[str, Any]` is the minimal open-typed container that lets consumers store arbitrary
  extension data without taxomesh needing to know the schema. `Any` is the only correct value
  type when the schema is genuinely unknown at the library level.
- mypy strict permits `dict[str, Any]` — it is fully parameterised. The `Any` in the value
  position must be accompanied by a justification comment per constitution Principle IV.

**Alternatives considered**:
- `dict[str, str]` — rejected: too restrictive; consumers may need to store nested dicts, lists,
  or numeric values.
- `dict[str, object]` — rejected: would require `isinstance` guards everywhere callers use
  metadata values; `Any` is more honest about the intent.
- No `metadata` field — rejected: without an extension mechanism, consumers must subclass or
  wrap every model to add context-specific data.

---

## Decision 6 — String length constraints via `Annotated[str, Field(max_length=N)]`

**Decision**: All direct `str` fields declare constraints through `Annotated`, not via
`Field(max_length=N)` alone at the field definition site.

**Rationale**:
- Constitution Principle IV mandates that every direct `str` field have an explicit `max_length`.
- `Annotated[str, Field(max_length=N)]` is Pydantic v2's canonical way to attach constraints
  to a type so they compose cleanly in unions (e.g., the `str` branch of `external_id`'s union
  carries its own constraint without affecting the `UUID` or `int` branches).
- Limits chosen:
  - `Category.name` → 256: standard name-field length, matches common DB column conventions.
  - `Category.description` → 100 000: generous limit for rich text without being unbounded.
  - `Tag.name` → 25: tags are meant to be concise labels; 25 chars enforces that intent.
  - `Item.external_id` (str branch) → 256: matches `Category.name` for consistency; sufficient
    for UUIDs-as-strings, slugs, and most URL-safe identifiers.

**Alternatives considered**:
- No length limits — rejected: violates constitution Principle IV's string length rule.
- Shorter `Category.description` limit — rejected: descriptions may contain markdown content;
  100 000 chars is still a hard upper bound that prevents unbounded writes to storage.

---

## Decision 8 — `ExternalId` TypeAlias in `taxomesh/domain/types.py`

**Decision**: The union `UUID | Annotated[str, Field(max_length=256)] | int` is extracted into
a named `TypeAlias` called `ExternalId` in a dedicated `taxomesh/domain/types.py` module.
`Item.external_id` is annotated as `ExternalId` instead of the inline union.

**Rationale**:
- The same union type will be referenced by future layers (application services, repository
  adapters, FastAPI view functions). Repeating the 50-character inline union verbatim in each
  layer creates an implicit copy that drifts silently if the union is ever extended.
- A named alias at `taxomesh.domain.types.ExternalId` gives future layers a stable import
  contract: `from taxomesh.domain.types import ExternalId`.
- Python 3.11's `typing.TypeAlias` is the correct annotation form. PEP 695 soft-keyword syntax
  (`type ExternalId = ...`) requires Python 3.12+ and is therefore forbidden by the project's
  `requires-python = ">=3.11"` constraint.
- Placing the alias in `domain/types.py` (not `domain/models.py`) keeps the models module
  focused on class definitions and avoids circular imports when future domain modules need
  `ExternalId` without importing the full model graph.

**Alternatives considered**:
- Keep the inline union in `models.py` only — rejected: will be duplicated in future layers.
- Define `ExternalId` inside `models.py` and export it — rejected: mixes type-alias declarations
  with class definitions; harder to discover and import without pulling in all model classes.
- Use PEP 695 `type ExternalId = ...` — rejected: requires Python 3.12+, incompatible with
  the project's minimum Python version.

---

## Decision 7 — Junction models carry no business logic

**Decision**: `CategoryParentLink`, `ItemParentLink`, `ItemTagLink` are pure DTO classes with
only fields — no methods, no validators beyond field types, no computed properties.

**Rationale**:
- Junction models represent storage rows. Business logic that operates on junctions (e.g.,
  cycle detection when adding a `CategoryParentLink`) belongs in the domain service layer
  (`domain/dag.py` per constitution Principle VI), not in the junction model itself.
- Keeping junction models as thin DTOs means they can be serialised/deserialised freely by
  any repository adapter without side effects.

**Alternatives considered**:
- Adding `validate_no_self_reference` to `CategoryParentLink` — rejected: a model validator
  could only check that `category_id != parent_category_id` for a single record; it cannot
  detect multi-hop cycles. Cycle detection requires graph traversal over all existing records,
  which is a repository+domain concern, not a single-model concern.
