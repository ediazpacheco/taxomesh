# Feature Specification: Logging Refactor — Public-Library Best Practices

**Feature Branch**: `051-logging-refactor`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: improve dangling-link warning message, adopt public-library logging best practices across taxomesh, add more warnings where warranted, add tests and update documentation.

---

## Context

taxomesh currently has two files that use logging:

- `taxomesh/application/service.py` — one `WARNING` for a dangling item-relation link
- `taxomesh/contrib/django/admin.py` — two `DEBUG` calls for URL-resolution failures

The library does **not** register a `NullHandler` on its root logger, which is a violation of the Python logging cookbook recommendation for public libraries. Additionally, the existing dangling-link warning carries only raw UUIDs and no method name, making it hard to trace without a debugger.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Improved dangling-link warning message (Priority: P1)

A developer integrating taxomesh calls `list_related_items_for_sources()` with `skip_on_error=True`. One of the relation links points to a target item that no longer exists in the repository. A warning is emitted.

Today the warning reads:

```
Dangling item relation link skipped: source_item_id=fea7bd50-... target_item_id=6a273a4c-... relation_type='music_by'
```

After this feature the warning must:
- Identify the calling method by name.
- Represent the **source item** using its human-readable string (which includes name, UUID, slug, and external_id).
- Mark the **target item** as orphaned (because it is absent from the repository, its details cannot be retrieved).
- Include the relation type.
- Carry a full standard log record so consuming applications can attach any formatter they choose (including timestamps).

**Why this priority**: This is the concrete pain-point the user reported and the highest-value, lowest-risk change.

**Independent Test**: Can be tested by configuring a repo with a dangling link and asserting the emitted log record's message fields.

**Acceptance Scenarios**:

1. **Given** a repo where `target_item_id` is absent, **when** `list_related_items_for_sources()` is called with `skip_on_error=True`, **then** a `WARNING` is emitted containing: the method name `list_related_items_for_sources`, the source item's human-readable representation (name, UUID, slug, external_id), the target UUID labelled as orphaned, and the relation type.
2. **Given** the same scenario with `skip_on_error=False`, **when** the method is called, **then** no warning is emitted and `TaxomeshItemNotFoundError` is raised (unchanged behaviour).
3. **Given** a repo with no dangling links, **when** `list_related_items_for_sources()` is called, **then** no warning is emitted.

---

### User Story 2 — NullHandler on the root taxomesh logger (Priority: P1)

A developer installs taxomesh in an application that does **not** configure logging. Without a `NullHandler`, Python will emit "last resort" output to stderr for any library log record.

After this feature, importing taxomesh silently registers a `NullHandler` on the `"taxomesh"` logger, so any unconsumed log records are discarded quietly.

**Why this priority**: This is a non-negotiable best practice for any distributed Python library. It is trivially small to implement and is what makes all other logging improvements "correct" from a library standpoint.

**Independent Test**: Import taxomesh into a fresh Python interpreter with no logging configuration. Verify no output appears on stderr.

**Acceptance Scenarios**:

1. **Given** a fresh Python environment with no logging configuration, **when** `import taxomesh` is executed, **then** `logging.getLogger("taxomesh").handlers` contains at least one `NullHandler`.
2. **Given** the NullHandler is registered, **when** any taxomesh code emits a log record and the consuming application has no handlers set up, **then** the record is silently discarded with no stderr output.

---

### User Story 3 — Upgrade relevant DEBUG calls to WARNING in the Django admin helper (Priority: P2)

A developer using the Django admin integration enables URL-linking for items (e.g., "view in external CMS"). If the required settings key is missing or URL resolution fails, the admin view silently continues. These situations are currently logged at `DEBUG`, invisible unless the developer has enabled debug-level logging.

After this feature:
- A missing settings key emits a `WARNING` (it is a misconfiguration the developer should know about).
- A URL resolution failure emits a `WARNING` with the exception detail (it is an operational failure, not routine).

**Why this priority**: These are low-risk targeted changes in an optional contrib module. They improve visibility for a common misconfiguration without breaking any existing behaviour.

**Independent Test**: Can be tested by calling the URL-resolution helper with a missing or broken settings key and asserting `WARNING` is emitted.

**Acceptance Scenarios**:

1. **Given** a Django admin view where the linked-URL setting key is not in `settings`, **when** the URL-resolution helper is called, **then** a `WARNING` is emitted that names the missing setting key.
2. **Given** a Django admin view where URL resolution raises an exception, **when** the helper is called, **then** a `WARNING` is emitted that includes the external_id, the setting key, and the exception message.
3. **Given** a correctly configured Django admin view, **when** the helper is called successfully, **then** no WARNING is emitted.

---

### User Story 4 — All logger names follow the `taxomesh.*` hierarchy (Priority: P2)

Every logger in taxomesh must be named via the module's own fully-qualified name. This ensures all library log records are filterable and suppressible by configuring a single handler on the `"taxomesh"` root logger.

**Why this priority**: Naming consistency is what makes the NullHandler strategy effective. Without it, a consuming application cannot reliably silence or route taxomesh logs.

**Independent Test**: Inspect all logging initialisation calls in the taxomesh source tree and confirm every one uses the module's own name.

**Acceptance Scenarios**:

1. **Given** the full taxomesh source tree, **when** all logger initialisation calls are inspected, **then** every one uses the module's own fully-qualified name — no hard-coded string names.

---

### User Story 5 — Timestamps available to consuming applications without appearing in message text (Priority: P3)

A developer configuring their application's log formatter wants timestamps on taxomesh records. Since taxomesh is a library, it must **not** embed timestamps in message strings — timestamps are a formatting concern for the consuming application.

**Why this priority**: This is a documentation and convention clarification. The standard log record already carries timestamp data; this story ensures the library never contradicts that convention.

**Independent Test**: Verify that log records emitted by taxomesh contain a valid timestamp attribute, and that no taxomesh log message string itself contains a timestamp.

**Acceptance Scenarios**:

1. **Given** a consuming application that configures a handler with timestamp formatting, **when** taxomesh emits a log record, **then** the consuming application's output includes the timestamp from the standard log record.
2. **Given** any taxomesh log record, **when** the message text is inspected, **then** it contains no embedded timestamp string.

---

### Edge Cases

- What if the source item is unexpectedly absent from the loaded item map at warning time? The warning must still emit without raising, labelling the source as an unknown item with its UUID.
- What if the human-readable representation of an item raises an unexpected exception? The warning must not propagate that exception; use a safe fallback string.
- What if the consuming application has already configured a handler on the `"taxomesh"` logger? The `NullHandler` must not interfere — it should only act as a fallback of last resort.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The library MUST register a `NullHandler` on the `"taxomesh"` logger at import time, before any other code runs.
- **FR-002**: The dangling-link warning in `list_related_items_for_sources` MUST include: the method name, the source item's human-readable representation (name, UUID, slug, external_id), a clearly labelled "orphaned" notice for the target item's UUID, and the relation type.
- **FR-003**: If the source item is unexpectedly absent from the loaded item map, the warning MUST still emit without raising, using a safe placeholder string.
- **FR-004**: The URL-resolution helper in the Django admin module MUST emit `WARNING` (not `DEBUG`) when the required settings key is absent.
- **FR-005**: The URL-resolution helper MUST emit `WARNING` (not `DEBUG`) when URL resolution fails, including the exception detail.
- **FR-006**: Every logger initialisation call throughout the `taxomesh` package MUST use the module's own fully-qualified name — no hard-coded string literals.
- **FR-007**: No taxomesh code MUST configure logging handlers, formatters, levels, or filters. Configuration is the consuming application's responsibility.
- **FR-008**: No taxomesh log message string MUST contain an embedded timestamp.
- **FR-009**: The public documentation MUST describe the taxomesh logging hierarchy (`"taxomesh.*"`), how to capture taxomesh log records, and how to configure timestamp formatting.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer reading a dangling-link warning can identify the originating method, the source item (by name/slug/external-id), and the orphaned target UUID without adding any extra instrumentation.
- **SC-002**: Importing taxomesh into a project with no logging configuration produces zero output on stderr.
- **SC-003**: A consuming application that sets the `"taxomesh"` log level to ERROR successfully suppresses all WARNING-level taxomesh records with no exceptions or side effects.
- **SC-004**: 100% of new and modified logging paths have corresponding test assertions using standard log-capture facilities.
- **SC-005**: All existing quality gates (linting, type checking, test coverage ≥ 80%) pass after the changes.

---

## Assumptions

- `Item.__str__()` returns a human-readable string that includes name, UUID, slug, and external_id — confirmed by reading the current implementation.
- The source item is always present in the item map at the point the dangling-link check fires, because links are fetched by caller-supplied source IDs and all items are loaded in the same batch. The spec covers the edge case defensively but does not expect it in practice.
- The Django contrib module is optional; the WARNING upgrade affects only developers who use it.
- No new log levels, structured-logging libraries, or third-party dependencies are introduced.
