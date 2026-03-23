# Feature Specification: Related Items Resilience — Warning Logging and Skip-on-Error

**Feature Branch**: `050-related-items-resilience`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: "en service.list_related_items_for_sources(): agregar logging de warning (indicando todos los datos posibles para encontrar los registros involucrados en la db) y agregar un arg skip_if_error (buscar el nombre más común en libs) que por default sea True."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Broken Link Logged and Skipped (Priority: P1)

A caller invokes `list_related_items_for_sources()` against a repository that contains
dangling item-relation links (i.e. a `target_item_id` referenced by a link no longer
exists as an `Item` in the repository).  With the default behaviour (`skip_on_error=True`)
the method logs a `WARNING` message that includes every identifier needed to locate the
affected records in the database, skips that link, and returns the successfully resolved
entries.  The caller never receives an exception.

**Why this priority**: This is the primary deliverable.  Dangling links are a real
operational hazard (e.g. items deleted without cascade), and swallowing the error
silently (the current behaviour is to raise) is the most common production need.
Observability via structured warning messages lets operators find and fix the
underlying data inconsistency without service disruption.

**Independent Test**: Can be fully tested by creating a source item, adding a relation
link that points to a non-existent target, calling
`list_related_items_for_sources([source.item_id])` with the default `skip_on_error=True`,
and asserting that (a) no exception is raised, (b) a `WARNING` log entry was emitted
containing the relevant IDs, and (c) the missing target is absent from the result.

**Acceptance Scenarios**:

1. **Given** a repository with a source item `S` and a relation link `S → T` where item `T`
   does not exist, **When** `list_related_items_for_sources([S.item_id])` is called with
   the default settings, **Then** the method returns `{}` (empty result, no entry for `S`),
   emits exactly one `WARNING`-level log message, and does **not** raise an exception.

2. **Given** a repository with source `S`, a valid link `S → A`, and a dangling link
   `S → T` (target missing), **When** `list_related_items_for_sources([S.item_id])` is
   called with the default settings, **Then** item `A` is present in the result under
   `S`, item `T` is absent, and one `WARNING` is logged for the dangling link.

3. **Given** the warning log message is emitted, **Then** it MUST contain all of the
   following identifiers: `source_item_id`, `target_item_id`, and `relation_type`;
   the message must be at `WARNING` level using the standard Python `logging` module.

---

### User Story 2 — Strict Mode Preserved (Priority: P2)

A caller that explicitly passes `skip_on_error=False` retains the existing strict
behaviour: if a dangling link is encountered, `TaxomeshItemNotFoundError` is raised
immediately, exactly as today.

**Why this priority**: Existing callers that rely on the exception signal (e.g. admin
integrity checks, migration scripts) must not be silently broken by the new default.

**Independent Test**: Can be fully tested by calling
`list_related_items_for_sources([source.item_id], skip_on_error=False)` with a dangling
link present, and asserting that `TaxomeshItemNotFoundError` is raised with a message
that identifies the missing target.

**Acceptance Scenarios**:

1. **Given** a dangling link exists, **When** `list_related_items_for_sources(..., skip_on_error=False)`
   is called, **Then** `TaxomeshItemNotFoundError` is raised and no partial result is
   returned.

---

### Edge Cases

- What happens when **all** links for a source are dangling?  The source ID is absent
  from the result dict (consistent with existing "absent means no matching links" contract).
- What happens when `source_item_ids` is empty?  Same as today — returns `{}` immediately,
  no logging.
- What happens when the same dangling target is referenced by multiple links?  A separate
  `WARNING` is emitted for each broken link encountered.
- What if `relation_types` filter excludes all dangling links?  No warning is emitted
  because those links are never evaluated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `list_related_items_for_sources()` MUST accept a new keyword-only parameter
  `skip_on_error` of type `bool`, defaulting to `True`.
- **FR-002**: When `skip_on_error=True` and a `target_item_id` referenced by a link is
  not found in the repository, the method MUST emit a `WARNING`-level log message via
  Python's standard `logging` module (using the module-level logger of
  `taxomesh.application.service`).
- **FR-003**: The warning message MUST include at minimum: `source_item_id`,
  `target_item_id`, and `relation_type`, so that an operator can locate the broken
  records in the database.
- **FR-004**: When `skip_on_error=True` and a dangling link is encountered, the method
  MUST skip that link and continue processing the remaining links without raising.
- **FR-005**: When `skip_on_error=False` and a dangling link is encountered, the method
  MUST raise `TaxomeshItemNotFoundError` (existing behaviour, unchanged).
- **FR-006**: The public signature and return type of `list_related_items_for_sources()`
  MUST remain backwards-compatible: the new parameter is keyword-only with a default,
  so existing call sites require no changes.
- **FR-007**: The docstring of `list_related_items_for_sources()` MUST be updated to
  document `skip_on_error`, the new warning behaviour, and the updated `Raises` section
  (raise only when `skip_on_error=False`).

### Key Entities

- **ItemRelationLink**: The link record connecting a `source_item_id` to a
  `target_item_id` with a `relation_type`.  Its fields are used as diagnostic
  identifiers in the warning log message.
- **TaxomeshItemNotFoundError**: The existing domain exception raised when a referenced
  item does not exist; still used in strict mode (`skip_on_error=False`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Calling `list_related_items_for_sources()` with one or more dangling links
  and the default settings completes without raising an exception, 100% of the time.
- **SC-002**: Each dangling link encountered produces exactly one `WARNING` log entry
  containing all required identifiers (`source_item_id`, `target_item_id`, `relation_type`).
- **SC-003**: All existing callers that do not pass `skip_on_error` continue to work
  without modification (zero breaking changes to the call site).
- **SC-004**: Callers passing `skip_on_error=False` continue to receive
  `TaxomeshItemNotFoundError` on dangling links (strict mode fully preserved, 100%).
- **SC-005**: All existing tests for `list_related_items_for_sources()` pass without
  modification after this change.

## Clarifications

### Session 2026-03-23

- Q: What is the canonical parameter name — `skip_on_error` or an alternative? → A: `skip_on_error` (stdlib-idiomatic boolean flag)
- Q: Should the warning log include all five `ItemRelationLink` fields or only the three natural-key fields? → A: Three fields only — `source_item_id`, `target_item_id`, `relation_type`

## Assumptions

- The standard Python `logging` module is already in use (or will be introduced) in
  `taxomesh/application/service.py`.  No third-party logging library is introduced.
- The `ItemRelationLink` domain model exposes `source_item_id`, `target_item_id`, and
  `relation_type` as the natural composite key.  `sort_index` and `metadata` are
  intentionally excluded from the warning message as they do not aid DB record lookup.
