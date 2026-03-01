# Research: Item & Category Slug Field

**Branch**: `018-item-category-slug` | **Date**: 2026-03-01

## Decisions

### Decision 1: Partial Unique Constraint for Empty-String Sentinel

**Decision**: Use a DB-level `UniqueConstraint` with `condition=~Q(slug="")` (Django ORM) rather than a nullable column with `null=True`.

**Rationale**: The spec defines `slug=""` as the canonical "no slug" sentinel (FR-002). Using an empty string keeps the field non-nullable and avoids `None` / `null` semantics in Python code. The partial unique constraint enforces uniqueness only for non-empty slugs at the DB level, giving a second layer of protection behind the service-layer check. This is a standard Django pattern for optional-but-unique fields.

**Alternatives considered**:
- `null=True, blank=True` with `UniqueConstraint(condition=Q(slug__isnull=False))` — rejected because mixing `None` and `""` as sentinels adds ambiguity and forces `None`-handling throughout the codebase.
- Application-only uniqueness (no DB constraint) — rejected because concurrent writes could violate uniqueness silently.

---

### Decision 2: Service-Layer Uniqueness Check Pattern

**Decision**: Check `repo.get_*_by_slug(slug)` before every create/update and raise `TaxomeshDuplicateSlugError` if the slug is taken by a *different* entity (different ID). Skip the check when `slug == ""`.

**Rationale**: Keeping the business rule in the service layer (not the repository) is consistent with the hexagonal architecture (Principle I). The DB constraint provides a safety net; the service check provides a user-friendly error before hitting the DB.

**Same-entity self-assign**: On `update_*`, the check compares `existing.entity_id != current_entity_id`. This correctly allows an entity to be saved with its own current slug without raising an error.

**Alternatives considered**:
- Enforcing uniqueness only at DB level — rejected because DB errors (IntegrityError) would leak through the abstraction boundary and require per-adapter exception mapping.

---

### Decision 3: O(n) Linear Scan for File-Based Repositories

**Decision**: `JsonRepository.get_item_by_slug` and `get_category_by_slug` use `next((x for x in self._items.values() if x.slug == slug), None)` — linear scan.

**Rationale**: The spec explicitly acknowledges this (Assumptions section): file-based repositories serve a local taxonomy tool where data volumes are small. Adding an in-memory slug→id index would add complexity for negligible gain. Per SC-007, test coverage ≥ 80% is the key gate; performance is not.

**Alternatives considered**:
- Maintaining a `dict[str, UUID]` slug-to-id index — rejected as YAGNI (not needed at current scale per spec Assumptions).

---

### Decision 4: In-Place Migration Edit

**Decision**: Add slug fields and constraints directly into `0001_initial.py` rather than creating `0002_add_slug.py`.

**Rationale**: The spec explicitly states (Assumptions): "The project has not shipped to production, so the DB migration is edited in-place (`0001_initial`) rather than adding a new migration." This keeps the schema history clean and treats the initial migration as the authoritative schema definition.

**Alternatives considered**:
- New migration `0002` — rejected per spec's explicit instruction.

---

### Decision 5: No Slug Format Validation

**Decision**: Accept any non-empty string up to 256 chars as a valid slug. No URL-safety enforcement, no charset restrictions.

**Rationale**: Explicitly out of scope (spec section "Out of Scope"). Max-length enforcement is handled by Pydantic's `Field(max_length=256)` and the Django model field `max_length=256`.

---

### Decision 6: `TaxomeshDuplicateSlugError` Placement in Exception Hierarchy

**Decision**: `TaxomeshDuplicateSlugError(TaxomeshValidationError)` — a direct subclass of `TaxomeshValidationError`.

**Rationale**: FR-004 mandates this. A duplicate slug is a domain constraint violation, not a "not found" or repository I/O error. Callers can catch at `TaxomeshValidationError` or more specifically at `TaxomeshDuplicateSlugError`.

---

### Decision 7: `__str__` Format — No Name in Category or Item

**Decision**: `Category.__str__` returns `"{slug} ({category_id}) -> {external_id}"` (slug + UUID + optional external_id). The category `name` field is intentionally **not** included in `__str__`.

**Rationale**: The spec defines the exact canonical format (FR-005, FR-006, User Story 3). This format prioritises the stable identifiers (slug and UUID) over the mutable human-readable name. Tests were updated accordingly.

---

## No Unresolved NEEDS CLARIFICATION Items

All items in the spec were clear. The clarify step confirmed zero open questions.
