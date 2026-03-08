# Feature Specification: Graph & Admin UX Improvements

**Feature Branch**: `025-graph-admin-ux`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: 8 UX improvements to the graph view (CLI + Django admin), admin list/detail views, admin home, README, and version bump.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Graph Depth Control (Priority: P1)

A CLI user runs `taxomesh graph` on a large taxonomy. By default only the top 3 levels of the
hierarchy are shown, keeping output readable. They can pass `--max-depth 5` to see more levels,
or `--max-depth 0` to see the entire tree. The Django admin graph view respects the same default
depth limit (3).

**Why this priority**: Affects both CLI and admin graph; foundational for US2 (depth also gates
item relation display).

**Independent Test**: Run `taxomesh graph` on a taxonomy deeper than 3 levels — nodes beyond
depth 3 are absent. Run with `--max-depth 0` — all nodes appear.

**Acceptance Scenarios**:

1. **Given** a taxonomy with categories nested 5 levels deep, **When** `taxomesh graph` is run without `--max-depth`, **Then** only the first 3 levels are rendered; deeper nodes are omitted.
2. **Given** the same taxonomy, **When** `taxomesh graph --max-depth 5` is run, **Then** all 5 levels are rendered.
3. **Given** `--max-depth 0`, **When** `taxomesh graph` is run, **Then** the complete taxonomy is rendered regardless of depth.
4. **Given** the Django admin graph page is loaded, **When** the taxonomy has more than 3 levels, **Then** only the first 3 levels are shown by default.

---

### User Story 2 — Item Relations: Always Shown, Collapsed by Default (Priority: P2)

An admin user viewing the graph no longer needs a global "Show item relations" toggle. Instead,
item relations are always present in the graph but start collapsed — each item that has outgoing
relations shows a `[+]` control. Clicking it expands the relations inline. Relations for items
at a depth greater than the current `--max-depth` setting are not shown.

**Why this priority**: Simplifies the graph UX; depends on depth infrastructure from US1.

**Independent Test**: Load the admin graph page — no "Show item relations" checkbox is present;
items with relations show a `[+]` control; clicking it reveals the relations.

**Acceptance Scenarios**:

1. **Given** the admin graph page is loaded, **When** the user inspects the page, **Then** no "Show item relations" checkbox is present.
2. **Given** an item at depth ≤ max-depth has outgoing relations, **When** the graph page loads, **Then** that item shows a `[+]` control and its relations are hidden initially.
3. **Given** the `[+]` control is clicked, **When** the user interacts, **Then** the item's relations become visible.
4. **Given** an item is at a depth greater than max-depth, **When** the graph page loads, **Then** neither the item nor its relations appear.
5. **Given** an item at depth ≤ max-depth has no outgoing relations, **When** the graph page loads, **Then** no `[+]` control is shown for that item.

---

### User Story 3 — External-ID Link in Item/Category Admin List & Detail (Priority: P3)

An admin user browsing the Item or Category list sees a `↗` icon next to any entry that has
an `external_id`. Clicking the icon opens the admin change page for the corresponding instance
of the configured linked model (e.g. `Content`). The same icon appears on the detail page.
Entries without an `external_id` show no icon.

**Why this priority**: High operational value; lets admins jump directly from a taxomesh item
to its linked domain object. Independent of US1/US2.

**Independent Test**: With `TAXOMESH_LINKED_MODEL` configured and some items having `external_id`,
load the Item list — the `↗` column is present; entries with `external_id` show a link; entries
without do not.

**Acceptance Scenarios**:

1. **Given** `TAXOMESH_LINKED_MODEL` is configured and an item has a non-empty `external_id`, **When** the Item list is loaded, **Then** a `↗` icon-link is shown for that item pointing to the configured model's admin change page.
2. **Given** an item has no `external_id`, **When** the Item list is loaded, **Then** no icon appears for that item.
3. **Given** `TAXOMESH_LINKED_MODEL` is not configured, **When** the Item or Category list is loaded, **Then** no icon column appears.
4. **Given** `TAXOMESH_LINKED_MODEL` is configured, **When** the Category detail page for a category with `external_id` is loaded, **Then** a `↗` icon-link to the linked model instance appears in the detail view.
5. **Given** a configured linked model instance does not exist for a given `external_id`, **When** the list or detail is loaded, **Then** no icon is shown (graceful degradation).

---

### User Story 4 — Admin Home: Taxomesh Version & Config Info (Priority: P4)

An admin user visiting the Taxomesh section of the Django admin home sees a small informational
widget showing the installed taxomesh version and the storage backend or config file in use.
This helps quickly diagnose which version and configuration is active.

**Why this priority**: Operational convenience; fully independent of other stories.

**Independent Test**: Load the Django admin home — the Taxomesh app section shows the version
string (e.g. "taxomesh 0.1.0a12") and the active backend or config path.

**Acceptance Scenarios**:

1. **Given** taxomesh is installed, **When** the Django admin home is loaded, **Then** the Taxomesh section displays the installed version (e.g. "v0.1.0a12").
2. **Given** a `taxomesh.toml` config file exists in the project, **When** the admin home is loaded, **Then** the config file path is shown.
3. **Given** no `taxomesh.toml` exists (Django ORM backend in use), **When** the admin home is loaded, **Then** "Django ORM backend" (or similar) is displayed instead of a config path.

---

### User Story 5 — Remove "Item Relation Links" from Admin Home (Priority: P5)

The standalone "Item relation links" entry currently visible on the Django admin home is removed.
Relation management is fully covered by the inline editors on the Item change page.

**Why this priority**: Housekeeping; quickest change; fully independent.

**Independent Test**: Load the Django admin home — "Item relation links" does not appear as a
top-level section.

**Acceptance Scenarios**:

1. **Given** the Django admin home is loaded, **When** the user views the Taxomesh section, **Then** "Item relation links" does not appear as a standalone navigable entry.
2. **Given** the Item change page is loaded, **When** a user manages relations, **Then** outgoing and incoming relation inlines are still fully functional.

---

### User Story 6 — README & Version Update (Priority: P6)

The README is updated to document: `--max-depth` option, item relations behaviour (always shown,
collapsed), `TAXOMESH_LINKED_MODEL` in list/detail views, and the admin home version widget.
The package version is bumped to reflect these changes.

**Why this priority**: Documentation and versioning; depends on all other stories being complete.

**Independent Test**: README contains accurate documentation for all features above; `pip show taxomesh` returns the new version.

**Acceptance Scenarios**:

1. **Given** the README is read, **When** a user looks for graph depth control, **Then** `--max-depth` is documented with its default value and `--max-depth 0` for unlimited.
2. **Given** the README is read, **When** a user looks for the linked model feature, **Then** both the graph icon-link and the list/detail icon-link are documented.
3. **Given** the package is installed, **When** the version is queried, **Then** the new version string is returned.

---

### Edge Cases

- `--max-depth 0` must show all nodes (unlimited). `--max-depth 1` shows only root categories (no items).
- When `TAXOMESH_LINKED_MODEL` is set but the app is not installed or the model string is malformed, icon-links must be silently suppressed everywhere (list, detail, graph).
- If a linked model instance does not exist for a given `external_id`, no icon is shown — no error page, no broken link.
- The admin home version widget must not crash if `importlib.metadata` cannot find the taxomesh package (show "unknown" gracefully).
- Removing `ItemRelationLinkModelAdmin` must not break the existing inline editors on the Item change page.

## Requirements *(mandatory)*

### Functional Requirements

**Graph depth control (US1)**

- **FR-001**: The `taxomesh graph` CLI command MUST accept a `--max-depth INTEGER` option (default: `3`).
- **FR-002**: A value of `0` for `--max-depth` MUST mean "no limit" (render the full taxonomy).
- **FR-003**: The admin graph view MUST apply a depth limit of `3` by default; categories and items at depth > max-depth MUST be omitted from the rendered output.
- **FR-004**: The depth of an entry is defined as its level in the category hierarchy: root categories are at depth 0, their direct items and child categories are at depth 1, and so on.

**Item relations: always shown, collapsed (US2)**

- **FR-005**: The "Show item relations" checkbox MUST be removed from the admin graph page.
- **FR-006**: Items at depth ≤ max-depth that have outgoing relations MUST show a `[+]` control on the graph page; their relations MUST be hidden by default and revealed on click.
- **FR-007**: Items at depth > max-depth MUST NOT appear in the graph and their relations MUST NOT appear.
- **FR-008**: The CLI `--show-relations` flag behaviour is unchanged; relation leaves are rendered inline when the flag is set, subject to `--max-depth`.

**External-ID links in list/detail (US3)**

- **FR-009**: When `TAXOMESH_LINKED_MODEL` is configured, `ItemModelAdmin` list MUST include a column that renders a `↗` icon-link for items with a non-empty `external_id`.
- **FR-010**: When `TAXOMESH_LINKED_MODEL` is configured, `CategoryModelAdmin` list MUST include the same `↗` icon-link column for categories with `external_id`.
- **FR-011**: The same icon-link MUST appear on the Item and Category detail (change) pages as a read-only field.
- **FR-012**: When `TAXOMESH_LINKED_MODEL` is not configured or the instance is not found, no icon or error MUST be shown (graceful suppression).

**Admin home version widget (US4)**

- **FR-013**: The Taxomesh section in the Django admin home MUST display the installed taxomesh version.
- **FR-014**: The same section MUST display either the path to the active `taxomesh.toml` config file, or a label indicating the Django ORM backend is in use when no config file is present.

**Remove Item relation links (US5)**

- **FR-015**: `ItemRelationLinkModel` MUST NOT be registered as a standalone admin entry.
- **FR-016**: Outgoing and incoming relation inlines on the Item change page MUST remain fully functional.

**README & version (US6)**

- **FR-017**: README MUST document `--max-depth` with its default and the `0`-means-unlimited behaviour.
- **FR-018**: README MUST document that item relations in the admin graph are always shown collapsed.
- **FR-019**: README MUST document the `↗` icon-link in Item/Category list and detail views.
- **FR-020**: The package version MUST be incremented.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `taxomesh graph` on a 5-level taxonomy with default settings renders nodes at depths 0–2 only (depth 3 = max, items at depth 3 excluded per FR-004 definition).
- **SC-002**: `taxomesh graph --max-depth 0` on the same taxonomy renders all nodes.
- **SC-003**: The admin graph page contains no "Show item relations" checkbox and zero visible relation rows on first load.
- **SC-004**: Clicking `[+]` on an item in the admin graph reveals that item's relation rows without a page reload.
- **SC-005**: With `TAXOMESH_LINKED_MODEL` set and M items having `external_id`, exactly M `↗` links appear in the Item list.
- **SC-006**: The Django admin home Taxomesh section shows a non-empty version string and a non-empty backend/path string.
- **SC-007**: "Item relation links" does not appear as a top-level entry on the Django admin home.
- **SC-008**: All quality gates pass: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov=taxomesh --cov-fail-under=80`.

## Assumptions

- `--max-depth` applies uniformly to categories, items, and item relations in both CLI and admin.
- Depth 0 = root categories. Items directly under a root category are at depth 1. This matches the existing `_flatten_graph` depth convention.
- The admin graph does not expose a UI control for max-depth — it is fixed at 3 on the server side (hardcoded default, configurable only via a future setting if needed).
- For the admin home version widget, the version is read via `importlib.metadata`; the config path is found by checking for `taxomesh.toml` in the Django project's `BASE_DIR` (falling back to "Django ORM backend").
- The `↗` icon-link in list/detail uses the same `TAXOMESH_LINKED_MODEL` + `pk` lookup as the graph view.
- Version bump: `0.1.0a11` → `0.1.0a12`.
- `ItemRelationLinkModelAdmin` was partially removed in a prior cycle but may have been reverted; this spec treats full removal as in scope.
