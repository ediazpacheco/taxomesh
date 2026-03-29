# Feature Specification: Pluggable Graph Sort Modes

**Feature Branch**: `053-graph-sort-modes`
**Created**: 2026-03-29
**Status**: Draft
**Input**: User description: "Add pluggable sort modes to the Django admin graph view. The graph currently sorts children by sort_index ascending only. A registry-based system where sort_modes is a list of 3-tuples (key, label, callable) — taxomesh ships two built-ins (sort_index_asc, sort_index_desc) and consumers can extend the list with their own sort functions. The callable receives list[GraphEntry] and returns list[GraphEntry]. A UI selector in the graph template lets users switch between available modes. The selected mode is propagated via query param to both the root graph view and the children AJAX endpoint."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch sort order in the graph view (Priority: P1)

An admin user opens the taxonomy graph and wants to view categories and items in a different order than the default. They use a sort mode selector in the graph toolbar to switch between available sort modes. The graph immediately reloads with the new ordering applied to all visible entries. When they expand a category to load its children, the same sort mode is applied to the children as well.

**Why this priority**: Core of the feature. Without this, no sorting capability exists at all.

**Independent Test**: Can be fully tested by navigating to the graph admin view, changing the sort selector, and verifying that entries reorder correctly — delivers the primary user value independently.

**Acceptance Scenarios**:

1. **Given** the graph is displayed with the default sort mode (`sort_index_asc`), **When** the user selects `sort_index_desc` from the sort selector, **Then** the graph reloads and all visible entries are ordered by descending sort index.
2. **Given** a sort mode is active, **When** the user expands a category to load its children, **Then** the children are rendered in the same active sort mode.
3. **Given** the user selects a sort mode, **When** they navigate away and return to the same URL, **Then** the sort mode is preserved (via query param in the URL).
4. **Given** only the two built-in sort modes are registered, **When** the user opens the sort selector, **Then** exactly two options are shown: "Sort index ↑" and "Sort index ↓".

---

### User Story 2 - Consumer registers a custom sort mode (Priority: P2)

A consumer application (e.g., a project built on top of taxomesh) needs to sort graph entries by a domain-specific criterion — for example, by content relevance score. The consumer extends the sort mode registry by appending a 3-tuple with a unique key, a human-readable label, and a callable. No changes to taxomesh internals are required. The custom sort mode appears in the UI selector alongside the built-in ones.

**Why this priority**: This is the extensibility contract. Without it, the feature is not agnostic and consumers cannot add their own ordering logic.

**Independent Test**: Can be fully tested by defining a custom sort function, registering it on the admin class, navigating to the graph, and verifying the custom mode appears in the selector and produces the expected ordering.

**Acceptance Scenarios**:

1. **Given** a consumer has registered a custom sort mode (`content_relevance`, "Content relevance", `fn`), **When** the user opens the sort selector, **Then** the custom mode appears in the list alongside the built-in modes.
2. **Given** the user selects the custom sort mode, **When** the graph renders, **Then** entries are ordered by the output of the consumer's sort callable.
3. **Given** a consumer registers a custom sort mode, **When** taxomesh executes the sort, **Then** taxomesh passes only the list of graph entries to the callable — no domain-specific data from taxomesh.

---

### User Story 3 - Default behavior is unchanged (Priority: P3)

An existing consumer that does not configure any sort modes continues to see the graph sorted by sort index ascending — the same behavior as before this feature. No migration or configuration change is required.

**Why this priority**: Backward compatibility. Ensures existing consumers are not broken by the change.

**Independent Test**: Can be fully tested by running the graph view without any sort_modes configuration and verifying the default ordering matches pre-feature behavior.

**Acceptance Scenarios**:

1. **Given** a consumer does not override sort modes, **When** they load the graph, **Then** entries are ordered by sort index ascending (same as current behavior).
2. **Given** no `sort_by` query param is present in the URL, **When** the graph loads, **Then** it defaults to `sort_index_asc`.

---

### Edge Cases

- What happens when an unknown `sort_by` value is passed as a query param (e.g., manually crafted URL)? The system falls back to the default (`sort_index_asc`) silently.
- What happens when a consumer registers a sort callable that returns an empty list? The graph renders with no entries (callable output is trusted as-is).
- What happens when two sort modes share the same key? The last registered entry wins (list order).
- What happens when the sort callable raises an exception? The error propagates — it is the consumer's responsibility to provide a correct callable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The graph admin view MUST display a sort mode selector control in the graph UI.
- **FR-002**: The sort mode selector MUST list all registered sort modes by their human-readable label.
- **FR-003**: The selected sort mode MUST be propagated as a query parameter to both the root graph view and the lazy-load children endpoint.
- **FR-004**: The graph admin class MUST define a `sort_modes` class attribute as an ordered list of 3-tuples: `(key: str, label: str, fn: Callable[[list[GraphEntry]], list[GraphEntry]])`.
- **FR-005**: taxomesh MUST ship two built-in sort modes registered by default: `sort_index_asc` (ascending by sort index) and `sort_index_desc` (descending by sort index).
- **FR-006**: The built-in sort callables MUST be importable as standalone functions from taxomesh so consumers can reference them directly.
- **FR-007**: A consumer MUST be able to extend the sort mode list by overriding `sort_modes` on their admin subclass — appending to the parent class's list.
- **FR-008**: When no `sort_by` query param is present, the graph MUST default to `sort_index_asc`.
- **FR-009**: When an unrecognized `sort_by` value is received, the graph MUST silently fall back to `sort_index_asc`.
- **FR-010**: The sort callable MUST receive only `list[GraphEntry]` as its argument — no request context, no domain objects, no taxomesh internals.
- **FR-011**: The sort callable MUST return `list[GraphEntry]` — the graph renders exactly what the callable returns.
- **FR-012**: The currently active sort mode MUST be visually indicated in the selector (selected state).

### Key Entities

- **SortMode**: A 3-tuple of `(key, label, fn)` — `key` uniquely identifies the mode and is used as the query param value; `label` is shown in the UI; `fn` is the callable applied to graph entries.
- **GraphEntry**: The existing typed dictionary representing a single node (category or item) in the admin graph — `sort_modes` callables receive and return lists of these.
- **sort_modes registry**: The ordered list of `SortMode` entries declared on the graph admin class. taxomesh provides the default two entries; consumers extend it by overriding the class attribute.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin user can change the graph sort order without leaving the graph page — mode change takes effect within a single page reload.
- **SC-002**: A consumer can register a custom sort mode by adding a single entry to the `sort_modes` list — zero changes to taxomesh internals required.
- **SC-003**: All existing graph views and tests continue to pass without modification after this feature is introduced — no regressions.
- **SC-004**: The active sort mode is bookmarkable — the same URL always produces the same sort order.
- **SC-005**: taxomesh source code contains no references to any consumer-specific sort concept (e.g., "relevance", "content") — agnosticism is verifiable by grep.

## Assumptions

- The sort callable is applied at the `GraphEntry` list level (after entries are built), not at the repository or service level. The existing sort_index-based ordering from the service layer is the input to the callable.
- The `sort_modes` attribute is a class-level attribute (not an instance method) — consumers override it by subclassing, not by calling a registration function.
- Labels are plain strings; no i18n/translation requirement for this feature.
- The sort selector is rendered as an HTML `<select>` element in the graph toolbar. Exact placement is a planning/implementation decision.
- The `sort_by` query param applies uniformly to both categories and items within the same view.
