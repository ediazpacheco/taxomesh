# Feature Specification: Repository-Level Enabled Filtering

**Feature Branch**: `046-repo-enabled-filter`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Que la lógica de filtrar por enabled (en Category/Items) sea manejada en los Repository. Para que por ej el Repository de django pueda aprovechar y filtrarlo directamente en el ORM en vez de tener que traer todos los registros y después filtrarlo con Python ya en el servicio o más arriba."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filter by Enabled State at Retrieval Time (Priority: P1)

A developer consuming the library calls any listing or search method and receives only
enabled categories or items by default — no post-processing required. Passing
`enabled=False` explicitly returns only disabled records. The repository applies the
filter natively for its storage backend.

**Why this priority**: This is the core contract change. Every other story builds on it.

**Independent Test**: Can be tested fully by calling `list_categories()` and `list_items()`
against a repository that contains a mix of enabled and disabled records, then asserting
that only enabled records are returned without any argument being passed.

**Acceptance Scenarios**:

1. **Given** a repository with both enabled and disabled categories, **When** a caller
   calls `list_categories()` with no arguments, **Then** only enabled categories
   are returned.
2. **Given** a repository with both enabled and disabled items, **When** a caller
   calls `list_items()` with no arguments, **Then** only enabled items are returned.
3. **Given** a repository with records in both states, **When** a caller passes
   `enabled=False`, **Then** only disabled records are returned.
4. **Given** a repository with no disabled records, **When** a caller passes
   `enabled=False`, **Then** an empty list is returned without error.

---

### User Story 2 - Service Layer and All Interfaces Are Coherent (Priority: P2)

Every service method, CLI command, contrib API endpoint, and Django admin view that
returns categories or items consistently applies `enabled=True` as the default filter.
No interface silently exposes disabled records by default. The `enabled_only` parameter
name on search methods is unified to `enabled` to match the rest of the API.
Backward compatibility is intentionally broken in favour of coherence.

**Why this priority**: Without coherence, callers get unexpected disabled records through
some interfaces while other interfaces hide them — a source of confusion and bugs.

**Independent Test**: Can be tested by calling each public surface (service, CLI, API)
with no explicit `enabled` argument and asserting that no disabled records appear in
any result.

**Acceptance Scenarios**:

1. **Given** a mix of enabled and disabled categories/items in the store, **When** any
   service method, CLI command, or API endpoint is invoked without an `enabled` argument,
   **Then** disabled records never appear in the output.
2. **Given** a caller that previously passed `enabled_only=True` to `search_items` or
   `search_categories`, **When** the same call is made after this change using the
   unified `enabled=True` parameter name, **Then** results are identical.
3. **Given** a Django admin view listing categories or items, **When** an admin user
   selects "Yes" from the `enabled` list filter in the sidebar, **Then** only enabled
   records appear. The default view (no filter selected) shows all records to give
   admin users visibility over disabled entries.

---

### User Story 3 - Django Backend Filters at Storage Level (Priority: P3)

When the Django backend is active and a listing or search is performed with
`enabled=True` (the default), the storage query excludes disabled records — no disabled
records are fetched and discarded in Python.

**Why this priority**: This is the primary performance motivation for the feature.
Other backends gain correctness; the Django backend additionally gains efficiency.

**Independent Test**: Can be verified by inspecting the storage queries issued during
a standard listing call and confirming that no surplus records are retrieved.

**Acceptance Scenarios**:

1. **Given** a Django-backed store with 10,000 items of which 5,000 are disabled,
   **When** `list_items()` is called (default `enabled=True`), **Then** the backend
   fetches at most 5,000 records from storage.
2. **Given** a Django-backed store, **When** `list_items(enabled=False)` is called,
   **Then** only the disabled items are fetched from storage.

---

### User Story 4 - Consistent Behaviour Across All Backends (Priority: P4)

Every repository implementation (JSON file, YAML file, in-memory, Django ORM) returns
identical result sets for the same `enabled` argument value when given equivalent data.

**Why this priority**: Consistency is a correctness guarantee — callers must not observe
different results when switching backends.

**Independent Test**: Can be tested by running the same `enabled` filter scenario against
each backend in the parity test suite and asserting identical result sets.

**Acceptance Scenarios**:

1. **Given** JSON-backed, YAML-backed, in-memory, and Django-backed repositories each
   holding identical seed data, **When** the same `enabled` value is applied to each,
   **Then** all four return identical result sets.

---

### User Story 5 - Documentation Is Updated (Priority: P5)

All public-facing documentation (docstrings, README, CLI help text, API schema
descriptions) reflects the new default `enabled=True` behaviour and the unified
`enabled` parameter name. Callers can understand the filtering contract without
consulting source code.

**Why this priority**: The documentation change is a delivery obligation, not an
optional improvement.

**Independent Test**: Can be verified by reviewing all updated docstrings and help texts
and confirming that `enabled=True` default and removal of `enabled_only` are accurately
described.

**Acceptance Scenarios**:

1. **Given** the updated codebase, **When** a developer reads the docstring for any
   listing or search method, **Then** the docstring states that only enabled records are
   returned by default and explains how to retrieve disabled records.
2. **Given** the CLI help text, **When** a user runs `--help` on any list command,
   **Then** the output describes the `enabled` filter option and its default.

---

### Edge Cases

- What happens when no records match the filter? → An empty list is returned without
  error.
- What happens when `enabled` is not supplied? → `enabled=True` is assumed; only enabled
  records are returned.
- Does the filter apply to the implicit root category? → The root category must never
  appear in any public listing regardless of its enabled state.
- What about `get_graph`? → Disabled categories are excluded from the graph by default
  (`enabled=True`), consistent with all other listing methods.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository port contract MUST add an `enabled: bool | None = True`
  parameter to `list_categories`; `True` returns only enabled records, `False` returns
  only disabled records, `None` returns all records regardless of state.
- **FR-002**: The repository port contract MUST add an `enabled: bool | None = True`
  parameter to `list_items`; same three-way semantics as FR-001.
- **FR-003**: Every repository adapter (JSON file, YAML file, in-memory, Django ORM)
  MUST implement the `enabled` parameter for both `list_categories` and `list_items`
  with identical semantics.
- **FR-004**: The Django adapter MUST apply the `enabled` filter at the storage query
  level, not by loading all records and filtering in Python.
- **FR-005**: Every service method that returns a list of categories or items MUST pass
  the caller-supplied `enabled` value (defaulting to `True`) through to the repository.
  This includes but is not limited to: `list_categories`, `list_items`,
  `list_categories_by_item`, `search_items`, `search_categories`, and `get_graph`.
- **FR-005a**: `get_graph` MUST exclude disabled categories by default (`enabled=True`)
  and MUST expose an explicit parameter to include disabled categories when needed.
- **FR-006**: The `enabled_only` parameter name on `search_items` and `search_categories`
  MUST be renamed to `enabled` to match the unified naming convention. The default value
  remains `True`. Backward compatibility for the old parameter name is intentionally
  not preserved.
- **FR-007**: All CLI commands that list or search categories or items MUST apply
  `enabled=True` by default and MUST expose an `--include-disabled` boolean flag;
  when the flag is present the command returns all records (both enabled and disabled).
- **FR-008**: All contrib API endpoints that return category or item collections MUST
  apply `enabled=True` by default and MUST accept an `include_disabled` boolean query
  parameter; when `include_disabled=true` the endpoint returns all records (enabled and
  disabled). Endpoints that currently return all records without a filter MUST be updated.
- **FR-009**: The `enabled` filter MUST NOT affect the implicit root category — the root
  category must never appear in public listing results regardless of its enabled state.
- **FR-010**: All docstrings, README sections, CLI help text, and API schema descriptions
  for affected methods and endpoints MUST be updated to reflect the new default behaviour
  and parameter naming.

### Key Entities

- **Category**: Domain entity with an `enabled` boolean field. All public listing and
  search operations now default to returning only enabled categories.
- **Item**: Domain entity with an `enabled` boolean field. All public listing and search
  operations now default to returning only enabled items.
- **Repository port**: The shared interface contract all adapters must satisfy. Gains
  `enabled: bool | None = True` on `list_categories` and `list_items`. The `None` value
  means "all records regardless of state" — used internally by corpus caching and admin views.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Calling any listing or search method without arguments never returns a
  disabled record across all backends and all interfaces.
- **SC-002**: When using the Django backend, a default listing call fetches only matching
  records from storage — no disabled records are transferred to the application layer.
- **SC-003**: The full test suite passes after all call sites, adapters, and interfaces
  are updated (tests that relied on disabled records appearing in default listings must
  be updated to reflect the new contract).
- **SC-004**: All four repository adapters return identical result sets for the same
  `enabled` value when given equivalent data (verified by the parity test suite).
- **SC-005**: Zero occurrences of the old `enabled_only` parameter remain anywhere in
  the codebase after the change.
- **SC-006**: Every public-facing docstring, help text, and API schema description for
  an affected method accurately describes the `enabled=True` default.

## Dependencies

- **036-service-repo-parity**: Parity test infrastructure for cross-backend validation.
- **Repository port** (`taxomesh/ports/repository.py`): Signature change on
  `list_categories` and `list_items`.
- **All adapter implementations**: JSON, YAML, in-memory, and Django repositories.
- **Service layer** (`taxomesh/application/service.py`): All listing and search methods.
- **CLI adapter**: All list and search commands.
- **Contrib API** (`taxomesh/contrib/api/`): Handlers and schemas returning collections.
- **Django admin views** (`taxomesh/contrib/django/`): Category and Item admin views
  gain a list filter on the `enabled` field (All / Yes / No) so admin users can access
  disabled records; the default admin view shows only enabled records.

## Clarifications

### Session 2026-03-21

- Q: Should single-record lookups (`get_category`, `get_item`, slug/external-id lookups) enforce the `enabled` filter? → A: No — they always return the requested record regardless of its enabled state.
- Q: Should `get_graph` exclude disabled categories by default, consistent with `enabled=True` on all other listing methods? → A: Yes — disabled categories are excluded from the graph by default; callers can opt in to include them.
- Q: What form should the CLI flag take to expose disabled records? → A: `--include-disabled` boolean flag; when present, returns all records (enabled + disabled).
- Q: How should contrib API endpoints expose access to disabled records? → A: `?include_disabled=true` query parameter; when present, returns all records (enabled + disabled).
- Q: How should Django admin expose disabled records to admin users? → A: Standard Django admin list filter on the `enabled` field (sidebar: All / Yes / No).

## Assumptions

- Only `list_categories` and `list_items` on the repository port gain the `enabled`
  parameter. Single-record lookups (`get_category`, `get_item`, `get_category_by_slug`,
  `get_item_by_slug`, `get_category_by_external_id`, `get_item_by_external_id`) are
  explicitly out of scope — they are identity operations and MUST return the requested
  record regardless of its enabled state.
- `get_graph` is in scope. Disabled categories are excluded from the graph by default,
  consistent with the `enabled=True` default applied to all other listing methods.
- The search corpus caching (`_get_item_corpus`, `_get_category_corpus`) pre-loads all
  records for the search index. The corpus itself continues to hold all records; the
  `enabled` filter is applied at query time when slicing from the corpus, not at
  corpus-build time — unless the planning phase identifies a performance benefit in
  filtering at corpus-build time.
- Breaking backward compatibility is intentional and accepted. No compatibility shims
  or deprecation warnings are required.
