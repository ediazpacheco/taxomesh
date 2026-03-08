# Research: Item-to-Item Relations (023-item-relations)

**Date**: 2026-03-08
**Status**: Complete — no unresolved unknowns

---

## Decision 1: Composite Key vs Surrogate UUID for ItemRelationLink

**Decision**: Use the triple `(source_item_id, target_item_id, relation_type)` as the
composite natural key. No surrogate UUID is assigned to a relation link.

**Rationale**: Relations are upserted by the triple — callers identify them by the three
fields, not by an opaque ID. Assigning a UUID would add complexity with no benefit (callers
never need to reference a relation by an opaque handle; they always know the triple).
`CategoryParentLink` and `ItemParentLink` follow the same pattern: no surrogate key.

**Alternatives considered**:
- Surrogate UUID as primary key: rejected — over-engineering for a link entity; inconsistent
  with existing link models in the codebase.

---

## Decision 2: New Exception Type for Relation Violations

**Decision**: Add `TaxomeshRelationError(TaxomeshValidationError)` as a new leaf exception
for self-relation and empty-relation-type violations.

**Rationale**: The constitution's hierarchy already has `TaxomeshCyclicDependencyError` as
a specific child of `TaxomeshValidationError` to allow callers to distinguish structural
violations. Self-relation and empty-type are relation-specific structural violations that
deserve the same treatment, enabling callers to `except TaxomeshRelationError` specifically.

**Alternatives considered**:
- Raise bare `TaxomeshValidationError`: rejected — loses granularity; callers cannot
  distinguish relation constraint violations from other validation errors.
- Raise `ValueError`: rejected — violates Principle V (all errors must inherit from
  `TaxomeshError`).

---

## Decision 3: direction Parameter Type — Literal vs Enum vs str

**Decision**: Use `Literal["outgoing", "incoming"]` for the `direction` parameter in
service and repository methods. Named constants `DIRECTION_OUTGOING` and `DIRECTION_INCOMING`
provide single sources of truth (Principle X).

**Rationale**: `Literal` is the lightest-weight option: it is checked by mypy at call sites,
requires no enum import or conversion overhead, and is consistent with the project's Python
3.11+ target. Named constants avoid magic string repetition throughout the codebase.

**Alternatives considered**:
- Python `Enum`: rejected — requires callers to import and use `Direction.OUTGOING` rather
  than a simple string; adds import boilerplate for a two-value parameter.
- Plain `str`: rejected — loses static type safety; violates mypy --strict requirements.

---

## Decision 4: JSON/YAML Persistence Schema for Relations

**Decision**: Store item relation links under a top-level key `"item_relation_links"` in
the JSON and YAML data files, parallel to the existing `"items"`, `"categories"`,
`"item_parent_links"`, etc. keys. Each entry serializes all five fields.

**Rationale**: All existing link types (tag links, parent links, item-category links) are
stored as flat lists under their own top-level key. Reusing this pattern avoids inventing
a new schema shape, and backward compatibility is preserved (old files without
`"item_relation_links"` load as an empty list via `.get()`).

**Alternatives considered**:
- Nesting relations under each item's record: rejected — breaks the flat schema pattern
  and complicates serialization/deserialization that is already uniform across all link types.

---

## Decision 5: Cascade Delete in JSON/YAML Backends

**Decision**: The `delete_item()` method in `JsonRepository` and `YAMLRepository` is
updated to filter `_item_relation_links` to remove any entry where
`source_item_id == item_id OR target_item_id == item_id` before persisting.

**Rationale**: The JSON/YAML backends manage in-memory lists and write atomically. Cascade
must be handled explicitly because there is no FK constraint mechanism. The existing
`delete_item()` already does a similar filter for `_item_parent_links` and `_links`
(tag links), so the pattern is established.

**Alternatives considered**:
- Separate cleanup method called by the service: rejected — the repository is responsible
  for its own referential integrity; leaking this concern to the service violates hexagonal
  layering.

---

## Decision 6: Django Admin — Incoming Relations Inline Strategy

**Decision**: Use two distinct `TabularInline` classes on `ItemModelAdmin`:
- `OutgoingRelationInline` — based on `ItemRelationLinkModel` with `fk_name="source_item"`,
  editable
- `IncomingRelationInline` — based on `ItemRelationLinkModel` with `fk_name="target_item"`,
  all fields `readonly_fields`, `extra=0`, `can_delete=False`

Both inlines route through the service layer via overridden `save_model` / `delete_model`
on the admin or custom `save_formset` hooks.

**Rationale**: Two `TabularInline` classes on the same model with different `fk_name` is
the standard Django pattern for bidirectional inline display. It requires no extra proxy
model or view hacks.

**Alternatives considered**:
- Single inline showing all relations: rejected — conflates editable and read-only concepts;
  confusing UX.
- Custom admin view page for relations: rejected — over-engineering; TabularInline achieves
  the goal with less code.

---

## Decision 7: max_length for relation_type

**Decision**: `RELATION_TYPE_MAX_LENGTH: Final[int] = 256` — consistent with `name`,
`external_id`, and `slug` max lengths on `Category` and `Item` (all 256). Stored in
`domain/constants.py`.

**Rationale**: 256 is the project's established maximum for human-readable identifier
strings. It is generous enough for domain-specific relation type names while providing a
clear upper bound that satisfies Principle IV's "no unbounded strings" rule.

**Alternatives considered**:
- 64 characters: rejected — too restrictive for verbose relation types users might define.
- 512 characters: rejected — no evidence this is needed; YAGNI.

---

## Decision 8: list_related_items Return Type

**Decision**: `list_related_items()` returns `list[Item]` (domain `Item` objects). The
relation metadata (type, sort_index) is not included. Callers who need both call
`list_item_relations()` instead.

**Rationale**: Matches the mental model: "give me the items I'm related to". Pairing both
in one return type would require a new response wrapper type — unnecessary complexity for
the spec's stated requirements.

**Alternatives considered**:
- Return `list[tuple[Item, ItemRelationLink]]`: rejected — tuple return types are weakly
  typed and awkward for callers; adds no value over two separate calls.
- Return a new `RelatedItemResult` dataclass: rejected — YAGNI; no use case stated.

---

## No Unresolved Unknowns

All decisions above are resolved. The implementation can proceed directly to Phase 1.
