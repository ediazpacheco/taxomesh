# Research: Unique External ID (1:1 Constraint)

**Feature**: 041-unique-external-id
**Date**: 2026-03-20
**Status**: Complete — no NEEDS CLARIFICATION items

---

## Decision 1: Exception Hierarchy Placement

**Decision**: `TaxomeshExternalIdConflictError` subclasses `TaxomeshValidationError`, not `TaxomeshError` directly.

**Rationale**: The spec requires subclassing `TaxomeshError` (FR-021). `TaxomeshValidationError` is already a subclass of `TaxomeshError`, so this satisfies the requirement. Semantically, a duplicate `external_id` is a domain constraint violation — the same category as `TaxomeshDuplicateSlugError`. Placing it under `TaxomeshValidationError` preserves the exception hierarchy symmetry and lets callers catch all validation errors with a single `except TaxomeshValidationError`.

**Alternatives considered**:
- Direct subclass of `TaxomeshError` — valid per spec but loses semantic grouping.
- Subclass of `TaxomeshRepositoryError` — rejected: the conflict is a domain rule, not a storage failure.

---

## Decision 2: Django Unique Constraint Strategy

**Decision**: Use `unique=True` directly on the `CharField(null=True)` field — NOT a partial `UniqueConstraint`.

**Rationale**: The spec (FR-013, FR-014, FR-016) explicitly specifies `CharField(null=True, blank=True, unique=True, default=None)` and states "no partial index is required". Both SQLite and PostgreSQL allow multiple NULL values under a standard UNIQUE constraint, which is exactly the required behaviour. Using a partial `UniqueConstraint` (the slug pattern) would be inconsistent with the spec and would add unnecessary complexity.

**Note**: Django raises a system check warning (`fields.W340`) when `null=True` is combined with `unique=True` on a CharField, because Django's convention discourages NULL on string fields. This warning can be suppressed with `suppress_warnings = ["fields.W340"]` in the field declaration if needed, or acknowledged in code comments. The warning does not affect correctness.

**Alternatives considered**:
- `UniqueConstraint(fields=["external_id"], condition=Q(external_id__isnull=False))` — valid but deviates from spec wording and adds a partial index when one isn't required.

---

## Decision 3: `DEFAULT_*_EXTERNAL_ID` Constants

**Decision**: Retain both constants, change type from `Final[str]` to `Final[str | None]` and value from `""` to `None`.

**Rationale**: Both constants are imported in domain models and Django ORM models. Keeping them avoids breaking imports. The constitution (Principle X) mandates named constants — `None` as a default is self-evident but the constant provides a single source of truth for the default value.

**Alternatives considered**:
- Remove constants, inline `None` directly — violates Principle X when used in multiple places.
- Keep as `Final[str] = ""` and add a new `DEFAULT_EXTERNAL_ID_NONE` — creates redundancy.

---

## Decision 4: Service Method Caching

**Decision**: Retain `@memoize(DEFAULT_CACHE_TTL)` on both new service methods unchanged.

**Rationale**: The return type changes from `list[Item]` to `Item | None`, but the memoize decorator works correctly with any return type including `None`. Caching `None` for "not found" lookups is a valid negative cache pattern that prevents redundant repository calls.

**Note**: The existing TTL-based invalidation (5-second window) remains unchanged.

---

## Decision 5: `DjangoRepository.save_item` / `save_category` — IntegrityError Handling

**Decision**: Wrap `update_or_create` in `transaction.atomic()` (already done), catch `IntegrityError` specifically (not just `DatabaseError`), and raise `TaxomeshExternalIdConflictError`. Non-IntegrityError `DatabaseError` continues to raise `TaxomeshRepositoryError`.

**Rationale**: `IntegrityError` is the specific Django ORM exception for unique constraint violations. Catching it separately from generic `DatabaseError` allows precise error mapping. `transaction.atomic()` ensures the failed write is rolled back automatically before the exception is re-raised.

**Alternatives considered**:
- Pre-check uniqueness with a SELECT before the write — rejected: introduces a race condition (TOCTOU).
- Catch all `DatabaseError` and map all to conflict — rejected: hides real database errors.

---

## Decision 6: JSON / YAML Repository Uniqueness Check

**Decision**: In `save_item` and `save_category`, before writing, scan `self._items` / `self._categories` for any record (other than the one being saved, matched by primary key) with the same non-None `external_id`. Raise `TaxomeshExternalIdConflictError` if found.

**Rationale**: File-based repositories have no database-level constraints. An in-process scan is the only available mechanism. The scan must exclude the record being saved to allow re-saves (clarification Q1).

**Performance note**: O(n) scan on save. Acceptable for file-based backends (small-to-medium datasets).

---

## Decision 7: CLI Empty String → None Conversion

**Decision**: In `_parse_external_id(raw: str) -> str | None`, return `None` when `raw` is an empty string. The function signature changes to return `str | None`.

**Rationale**: FR-023 requires empty string CLI input → `None`. The existing `_parse_external_id` utility is the natural place for this conversion, keeping the change contained.

---

## Decision 8: Django Admin `_resolve_linked_url` and `GraphEntry`

**Decision**:
- `GraphEntry.external_id` type changes from `str` to `str | None`.
- `_resolve_linked_url(external_id: str | None, ...)` returns `None` immediately when `external_id is None`.
- Existing guard `if not external_id` already handles empty string — extend to also pass for `None`.

**Rationale**: With `external_id = None` now possible, the admin must not pass `None` to URL resolution logic that expects a string. The existing empty-string guard can be extended to cover `None` with minimal change.
