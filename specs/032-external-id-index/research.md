# Research: External-ID Database Indexes

**Feature**: 032-external-id-index
**Date**: 2026-03-14

## Research Items

No external research was required. All decisions were resolved by reading the existing codebase.

---

### Decision 1: Index type — `db_index=True` vs `UniqueConstraint`

**Decision**: Use `db_index=True` on the field definition (non-unique B-tree index).

**Rationale**: The spec explicitly prohibits making `external_id` unique. A non-unique index
satisfies the performance requirement for `filter(external_id=...)` without changing duplicate
semantics.

**Alternatives considered**:
- `UniqueConstraint` — rejected; spec forbids uniqueness on `external_id`.
- Composite index (e.g. `external_id` + `enabled`) — rejected; YAGNI; simple single-column
  index is sufficient for the described query pattern.

---

### Decision 2: Migration strategy — `AlterField` vs `AddIndex`

**Decision**: Use `migrations.AlterField` to add `db_index=True` to both fields. Django
generates the index automatically from the field definition rather than a separate
`migrations.AddIndex` operation.

**Rationale**: `AlterField` is the idiomatic Django approach when the index is declared directly
on the field. It keeps the migration in sync with the model field definition. Using a separate
`AddIndex` would work but would create a mismatch between the field definition and the migration
operation that could confuse future developers.

**Alternatives considered**:
- `migrations.AddIndex` — technically equivalent but less idiomatic; rejected for simplicity.
- Manual `RunSQL` — rejected; no advantage over ORM-managed migration.

---

### Decision 3: Repository query logic — no changes needed

**Decision**: `DjangoRepository.list_items_by_external_id` and
`list_categories_by_external_id` already use `filter(external_id=external_id)`. No query
logic changes are needed.

**Rationale**: Reading the implementation confirms the correct filtered ORM query is already
in place. The performance improvement comes entirely from the database index, not from query
rewrites.

**Alternatives considered**: None — the existing implementation is already correct.

---

### Decision 4: Protocol — no changes needed

**Decision**: `TaxomeshRepositoryBase` already declares both lookup methods (added in spec
013). No protocol changes are required.

**Rationale**: The methods were promoted to the protocol in spec 013. This spec only adds the
database-level performance support (index + tests).

---

### Decision 5: Non-Django adapters — no changes needed

**Decision**: `JsonRepository` and `YAMLRepository` implement the protocol methods via
Python-level list comprehension scans. No changes to these implementations.

**Rationale**: The spec explicitly states the performance improvement targets the Django
backend. File-based repositories are not subject to database index optimisation; their
scan-based implementation is appropriate for their storage model.

---

### Decision 6: Testing approach — cardinality assertions, no query-count assertions

**Decision**: Tests assert result cardinality (`len(result)`) and field values. No
`django.test.utils.CaptureQueriesContext` or `assertNumQueries` assertions.

**Rationale**: The spec notes that query-count assertions can be brittle. Cardinality-based
tests cover all specified acceptance scenarios (empty, single, duplicate) without coupling
tests to implementation details of the ORM query planner.
