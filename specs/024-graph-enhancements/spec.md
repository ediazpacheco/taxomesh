# Feature Specification: Graph Enhancements (CLI + Admin)

**Feature Branch**: `024-graph-enhancements`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: "CLI graph command: add --show-relations flag (default off). Django admin graph: remove link underlines, [+]/[-] expand/collapse controls, boolean toggle for item relations, icon-link to configured Django model via external_id."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — CLI: Show Item Relations in Graph (Priority: P1)

A CLI user runs `taxomesh graph` to inspect their taxonomy. By default the output is clean and
focused on the category/item hierarchy. When they also want to inspect how items are related
to each other, they pass `--show-relations` and the tree additionally prints each item's outgoing
relations below it.

**Why this priority**: Foundational — adds the new data layer to the terminal output and is
independent of all admin changes.

**Independent Test**: Run `taxomesh graph` on a taxonomy with item relations. Without the flag
relations are absent; with `--show-relations` each item's outgoing relations appear indented below it.

**Acceptance Scenarios**:

1. **Given** a taxonomy with item relations, **When** `taxomesh graph` is run without `--show-relations`, **Then** no item relations appear anywhere in the output.
2. **Given** a taxonomy with item relations, **When** `taxomesh graph --show-relations` is run, **Then** each item that has outgoing relations shows them indented below it (relation type + target item name).
3. **Given** a taxonomy with no item relations, **When** `taxomesh graph --show-relations` is run, **Then** the output is identical to the output without the flag.

---

### User Story 2 — Admin Graph: Remove Link Underlines (Priority: P2)

An admin user views the graph page. Currently all category/item links have the browser-default
underline decoration which adds visual noise to the tree. After this change links are rendered
without underline in their default state.

**Why this priority**: Purely visual polish; quickest win in the admin changes.

**Independent Test**: Load the graph page and inspect the rendered HTML/CSS — all `<a>` elements
inside the tree must have `text-decoration: none` by default.

**Acceptance Scenarios**:

1. **Given** the graph page is loaded, **When** a user views any category or item link, **Then** the link has no underline decoration in its default state.
2. **Given** the graph page is loaded, **When** a user hovers over a link, **Then** an underline may appear (to preserve discoverability).

---

### User Story 3 — Admin Graph: Expand/Collapse Controls (Priority: P3)

An admin user views a large taxonomy graph. To reduce clutter they can click `[-]` next to a
category to collapse it (hiding all its items and child categories) and click `[+]` to expand it
again. When the relations toggle is ON, items that have outgoing relations also get `[+]`/`[-]`
controls to show/hide those relations.

**Why this priority**: UX improvement that depends on a readable graph (P2).

**Independent Test**: Load the graph page, click `[-]` next to a category — its items and
children disappear. Click `[+]` — they reappear. State is managed client-side only (no page reload).

**Acceptance Scenarios**:

1. **Given** the graph page is loaded, **When** a category has a `[-]` control and the user clicks it, **Then** all items and child categories under that category are hidden.
2. **Given** a category is collapsed (`[+]` shown), **When** the user clicks `[+]`, **Then** the category's items and children become visible again.
3. **Given** the relations toggle is ON and an item has outgoing relations, **When** the user clicks `[-]` next to that item, **Then** its outgoing relations are hidden.
4. **Given** an item with no outgoing relations, or the relations toggle is OFF, **When** the page loads, **Then** no expand/collapse control is shown next to that item.
5. **Given** a category has no items and no children, **When** the page loads, **Then** no expand/collapse control is shown next to that category.

---

### User Story 4 — Admin Graph: Item Relations Toggle (Priority: P4)

An admin user viewing the graph wants to optionally see item-to-item relations inline.
A boolean control (checkbox or toggle) at the top of the graph page lets them switch
item relations on or off without a full page reload. Default state is OFF.

**Why this priority**: Depends on the expand/collapse controls (P3) which render the relations when shown.

**Independent Test**: Load the graph page — relations are hidden. Toggle ON — each item's outgoing
relations appear. Toggle OFF — they disappear again.

**Acceptance Scenarios**:

1. **Given** the graph page is loaded, **When** a user has not interacted with the toggle, **Then** item relations are not visible.
2. **Given** the toggle is switched ON, **When** an item has outgoing relations, **Then** those relations appear below the item (with relation type and target name).
3. **Given** the toggle is switched OFF after being ON, **When** a user views the graph, **Then** all item relations are hidden regardless of individual expand/collapse state.
4. **Given** a taxonomy with no item relations, **When** the toggle is switched ON, **Then** no relation entries appear and the graph looks identical to the OFF state.

---

### User Story 5 — Admin Graph: Icon-Link to Configured Django Model (Priority: P5)

An admin user has configured a Django model (e.g. `myapp.Content`) to be associated with
taxomesh items/categories via `external_id`. On the graph page, next to each item or category
that has a non-empty `external_id`, a small icon appears as a hyperlink to that model instance's
Django admin change page. Items/categories without an `external_id` show no icon.

**Why this priority**: Most complex; requires a configuration mechanism and URL resolution
that depends on a stable graph rendering (P2–P4).

**Independent Test**: Configure the linked model, load the graph — items with `external_id` show
an icon-link; items without do not. Clicking the icon navigates to the correct admin change page.

**Acceptance Scenarios**:

1. **Given** a linked model is configured and an item has a non-empty `external_id`, **When** the graph page is loaded, **Then** an icon-link appears next to that item pointing to the admin change page of the matching linked model instance.
2. **Given** a linked model is configured and an item has no `external_id`, **When** the graph page is loaded, **Then** no icon appears next to that item.
3. **Given** no linked model is configured, **When** the graph page is loaded, **Then** no icon appears next to any item or category.
4. **Given** a linked model is configured but no instance with the given `external_id` exists, **When** the graph page is loaded, **Then** no icon is rendered for that node (graceful degradation, no error).

---

### Edge Cases

- A category with no items and no children must not show `[+]`/`[-]`.
- CLI `--show-relations` on a taxonomy with no relations must produce output identical to the flag-less output.
- When the relations toggle is toggled OFF after being ON, per-item expand/collapse state is reset.
- When `TAXOMESH_LINKED_MODEL` is set but the model cannot be resolved (e.g. app not installed), the graph must still render without crashing — the icon feature is silently disabled.

## Requirements *(mandatory)*

### Functional Requirements

**CLI**

- **FR-001**: The `taxomesh graph` command MUST accept a `--show-relations` / `--no-show-relations` flag (default: `False`).
- **FR-002**: When `--show-relations` is `False`, the graph output MUST be identical to current behaviour (no item relations shown).
- **FR-003**: When `--show-relations` is `True`, each item that has outgoing `ItemRelationLink` records MUST display those relations indented below it, showing at minimum the relation type and the target item's display name.

**Admin graph — visual**

- **FR-004**: All hyperlinks in the graph tree MUST have `text-decoration: none` in their default (non-hover) state.
- **FR-005**: Every category node that has at least one item or child category MUST be preceded by a `[+]` or `[-]` clickable control that toggles the visibility of its descendants.
- **FR-006**: A category with no items and no children MUST NOT display an expand/collapse control.
- **FR-007**: Expand/collapse state MUST be managed client-side (vanilla JavaScript) without page reload.

**Admin graph — item relations toggle**

- **FR-008**: The graph page MUST include a boolean UI control labelled to communicate whether item relations are shown (e.g. "Show item relations").
- **FR-009**: The control MUST default to OFF (relations hidden) on every page load.
- **FR-010**: When the toggle is ON, each item with outgoing relations MUST display a `[+]`/`[-]` control and its relations inline (relation type + target item name/link).
- **FR-011**: When the toggle is switched, the visibility of all relation rows MUST update immediately without a page reload.

**Admin graph — linked Django model**

- **FR-012**: The taxomesh Django integration MUST support an optional Django setting `TAXOMESH_LINKED_MODEL` whose value is a string in the form `"app_label.ModelName"`.
- **FR-013**: When `TAXOMESH_LINKED_MODEL` is set and an item/category has a non-empty `external_id`, the graph MUST render a small inline icon-link next to that node pointing to the Django admin change page for the model instance whose **primary key** matches the `external_id`. The lookup field is always `pk`; no override setting is provided.
- **FR-014**: When `TAXOMESH_LINKED_MODEL` is set but a model instance with the given `external_id` does not exist, the icon MUST NOT be rendered for that node (no broken link, no error page).
- **FR-015**: When `TAXOMESH_LINKED_MODEL` is not set (or the model cannot be resolved), the graph MUST render identically to its current state (no icons, no errors).
- **FR-016**: The icon used MUST be a standard inline text symbol (e.g. ↗) requiring no external assets or additional HTTP requests.

### Key Entities

- **ItemRelationLink**: Directed relation between two `Item` entities, carrying `relation_type` (string) and `sort_index`. Defined in spec 023; already exists in the domain.
- **TAXOMESH_LINKED_MODEL**: Optional Django setting string (`"app_label.ModelName"`) read by the graph view at request time to resolve icon-links via `external_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `taxomesh graph --show-relations` on a taxonomy with N items that have relations produces at least N relation entries in the output.
- **SC-002**: `taxomesh graph` (no flag) on the same taxonomy produces zero relation entries.
- **SC-003**: On the admin graph page, clicking `[-]` on any non-empty category hides its descendants; clicking `[+]` reveals them — with no page reload in either case.
- **SC-004**: With the relations toggle OFF (default), zero relation rows are visible in the admin graph for any item.
- **SC-005**: With the relations toggle ON, every item that has at least one outgoing relation shows at least one relation row.
- **SC-006**: When `TAXOMESH_LINKED_MODEL` is set and M out of N items have a non-empty `external_id`, exactly M icon-links appear in the graph (the remaining N−M show no icon).
- **SC-007**: All quality gates pass: `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov=taxomesh --cov-fail-under=80`.

## Assumptions

- `ItemRelationLink` data is fetchable via `TaxomeshService`; if no service method exists for bulk-fetching relations per item, a minimal addition is in scope.
- Expand/collapse in the admin is implemented with vanilla JavaScript (no new JS libraries).
- The linked-model lookup field is always `pk` (resolved during /speckit.specify; no override setting).
- `TAXOMESH_LINKED_MODEL` is read at request time so changes take effect without restarting the server.
- Toggle state and expand/collapse state are NOT persisted across page loads.
- The icon-link always points to the standard Django admin change URL for the configured model.
