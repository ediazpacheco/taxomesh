# Feature Specification: Admin & Service Improvements — Category External ID, Debug, and UX

**Feature Branch**: `026-admin-service-debug`
**Created**: 2026-03-08
**Status**: Draft
**Input**: User description: Category external_id full support in admin, better item/category-content filters, partial UUID search, show-relations default true, TaxomeshService create/update/list with external_id, TaxomeshService.get_debug(), debug data in TAXOMESH submenu.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Category Linked-Object Resolution in Admin (Priority: P1)

An administrator manages categories that are linked to external domain objects (e.g., a "Genre" record in a publishing platform) via a category's `external_id`. Currently the admin resolves `external_id` only for Item-linked models; Category uses the same setting and the link icon is broken or absent. The administrator needs the category list and detail pages to correctly display and navigate to the linked external object — independently of the Item-linked-model configuration.

**Why this priority**: Broken admin links reduce trust in the tool. This is the most visible gap: the external_id field is shown but the link resolution silently does nothing useful for Category records.

**Independent Test**: Configure a category with a non-empty `external_id` pointing to a valid external object, and a category-specific linked-model setting. Verify the category list shows a working navigation icon, and the category detail page shows the resolved linked object.

**Acceptance Scenarios**:

1. **Given** `TAXOMESH_CATEGORY_LINKED_MODEL` is set, **When** a category with a non-empty `external_id` is viewed in the admin list, **Then** a linked-object icon is shown that navigates to the correct admin change page for that external object.
2. **Given** `TAXOMESH_CATEGORY_LINKED_MODEL` is not set, **When** a category is viewed in the admin list, **Then** no broken icon is shown; the `external_id` value is still displayed as text.
3. **Given** `TAXOMESH_CATEGORY_LINKED_MODEL` is set but no object with the given `external_id` exists, **When** the admin list is rendered, **Then** no link icon is shown (graceful fallback, no error).

---

### User Story 2 — Partial UUID Search in Admin List Views (Priority: P2)

An administrator copies part of a UUID (e.g. `2b0bf7ef6646`) from a log or URL and pastes it into the admin search box to locate a specific category or item. Currently the search only matches slug or name fields; UUID substrings return no results.

**Why this priority**: UUIDs are the primary identifiers used in integrations and logs. Inability to search by partial UUID forces administrators to manually browse paginated lists, which is impractical.

**Independent Test**: Create a category whose `category_id` contains the substring `2b0bf7ef6646`. Search for that substring in the admin list. The category appears in results.

**Acceptance Scenarios**:

1. **Given** a category with UUID `2b0bf7ef6646…`, **When** the admin search box receives `2b0bf7ef6646`, **Then** that category appears in the results list.
2. **Given** an item with UUID `abc123…`, **When** the admin search box receives `abc123`, **Then** that item appears in the results list.
3. **Given** a search string that matches no UUID, name, slug, or external_id, **When** the query is submitted, **Then** an empty list is returned with no error.

---

### User Story 3 — Better Item/Category–Content Integration Filters in Generic Admin (Priority: P2)

A developer integrating an external domain model (e.g. `Content`) with taxomesh uses the library's generic admin mixin to add taxomesh category awareness to their model's admin. Currently filters are coarse and do not allow filtering the external model's list by taxomesh category, nor filtering taxomesh category records by whether they have a linked external object. The developer needs list-level filters that make the relationship navigable in both directions.

**Why this priority**: The extensibility admin is a core advertised capability. Poor filters reduce its practical usefulness to integrators.

**Independent Test**: Register an external `Content` model admin using the taxomesh mixin. The Content list must show a filter sidebar that lets the user narrow results by taxomesh category. The Category list must allow filtering to "has linked object" or "no linked object".

**Acceptance Scenarios**:

1. **Given** a `Content` model admin using the taxomesh mixin with no `list_filter` customisation, **When** the Content list is viewed, **Then** a taxomesh category filter is automatically available in the sidebar (no extra config required).
2. **Given** categories with and without linked external objects, **When** the Category admin list filter "has linked object" is selected, **Then** only categories with a non-empty `external_id` are shown (field-level check; no external DB verification).
3. **Given** a filter is applied, **When** the filter is cleared, **Then** the full unfiltered list is restored.

---

### User Story 4 — show-relations Defaults to True (Priority: P3)

A developer or administrator runs the CLI `graph` command or opens the admin graph view. Currently item relations are hidden by default (`show-relations` defaults to `False`). Since relations are part of the core value of the graph, the default should be reversed to `True`. The admin graph should follow the same convention.

**Why this priority**: Reversing a default is a non-breaking UX improvement. Hiding relations by default causes confusion about the graph's capabilities.

**Independent Test**: Run the CLI graph command with no flags. Item relations appear in the output. Open the admin graph view with no customisation. Relations are visible.

**Acceptance Scenarios**:

1. **Given** a taxonomy with item relations, **When** the graph command is run with no arguments, **Then** relations are displayed in the output.
2. **Given** the admin graph is opened with no URL parameters, **When** the page renders, **Then** relations are visible in the graph.
3. **Given** a user explicitly requests no relations, **When** the graph command runs with the opt-out flag, **Then** relations are hidden.

---

### User Story 5 — TaxomeshService Category Methods Support external_id (Priority: P2)

A developer using `TaxomeshService` programmatically needs to create categories with an `external_id`, update a category's `external_id`, and list categories filtered by `external_id`. Currently none of these three methods expose `external_id` as a parameter, making programmatic management of the Category–external object relationship impossible without bypassing the service.

**Why this priority**: The service is the single public facade. If a field is manageable in the admin but not via the service, the API surface is incomplete and forces callers into internal APIs.

**Independent Test**: Call `service.create_category(name="X", external_id="abc")`. Retrieve the category and verify `external_id == "abc"`. Call `service.update_category(id, external_id="xyz")` and verify the update. Call `service.list_categories(external_id="xyz")` and verify only that category is returned.

**Acceptance Scenarios**:

1. **Given** a call to `create_category(name="Genres", external_id="genre-42")`, **When** the method returns, **Then** the returned category has `external_id == "genre-42"`.
2. **Given** an existing category with `external_id="old"`, **When** `update_category(id, external_id="new")` is called, **Then** the stored category reflects `external_id == "new"`.
3. **Given** multiple categories, some with `external_id="abc"` and some without, **When** `list_categories(external_id="abc")` is called, **Then** only categories with `external_id == "abc"` are returned.
4. **Given** `update_category(id, external_id=None)` is called, **Then** the `external_id` field is left unchanged (`None` means "do not update").
5. **Given** `update_category(id, external_id="")` is called, **Then** the `external_id` is explicitly cleared to empty string (explicit clear, distinct from no-update).

---

### User Story 6 — TaxomeshService.get_debug() Diagnostic Method (Priority: P3)

A developer or operator needs to quickly inspect the runtime state of a taxomesh installation: which version is installed, where the service is operating, which config file is active, and which repository backend is in use. Currently there is no programmatic way to retrieve this information.

**Why this priority**: Diagnostic methods reduce support overhead and help developers verify integrations are configured correctly.

**Independent Test**: Call `service.get_debug()`. Verify the returned dict contains keys for version, working path, config name, and repository type.

**Acceptance Scenarios**:

1. **Given** a `TaxomeshService` instance, **When** `get_debug()` is called, **Then** a dict is returned containing at minimum: `version`, `config_name`, `repository_type`, and `working_path`.
2. **Given** a service backed by a JSON file at `data/taxomesh.json`, **When** `get_debug()` is called, **Then** `repository_type` identifies the repository class name and `working_path` reflects the relevant file path.
3. **Given** a service built from `taxomesh.toml`, **When** `get_debug()` is called, **Then** `config_name` reflects the name of the active config.
4. **Given** a service constructed with no config (defaults), **When** `get_debug()` is called, **Then** `config_name` is `None` and `working_path` is still populated.

---

### User Story 7 — Debug Info in TAXOMESH Admin Submenu (Priority: P3)

An administrator opens the Django admin and wants to see taxomesh diagnostic information (version, config, repository) in one place under the TAXOMESH section. This view must appear under "TAXOMESH", not under "Visualization" or any other group.

**Why this priority**: Discoverability — diagnostics must be near the other TAXOMESH admin entries. Placing them elsewhere creates confusion.

**Independent Test**: Open the Django admin home. Under the TAXOMESH heading, a diagnostic entry is visible. Clicking it opens a read-only page showing version, config name, repository type, and working path.

**Acceptance Scenarios**:

1. **Given** the Django admin is open, **When** the home page is viewed, **Then** a diagnostic entry appears under the TAXOMESH app group (not under Visualization or any other group).
2. **Given** the diagnostic entry is clicked, **When** the page loads, **Then** all four values (version, config name, repository type, working path) are visible as read-only fields.
3. **Given** the taxomesh version is updated, **When** the debug page is reloaded, **Then** the displayed version reflects the currently installed package version without any manual configuration change.

---

### Edge Cases

- `list_categories(external_id="")` returns all categories whose `external_id` is empty string (treats empty string as a valid exact-match filter, not as "no filter").
- `TAXOMESH_CATEGORY_LINKED_MODEL` pointing to a model not installed or not found: the icon is silently omitted; no 500 error is raised.
- A partial UUID search string that matches both a UUID substring and a slug or name: both matching records are returned in the same query result.
- `update_category` called with `external_id=None`: the field is unchanged. Called with `external_id=""`: the field is explicitly set to empty string.
- `get_debug()` called before any repository operation has been performed: all four keys are still populated (no lazy initialisation side effects required).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The admin Category list view MUST display a linked-object icon that resolves using a category-specific linked-model configuration key (`TAXOMESH_CATEGORY_LINKED_MODEL`), independent of the Item-linked-model configuration.
- **FR-002**: The admin Category detail view MUST display the resolved linked external object (read-only) when `TAXOMESH_CATEGORY_LINKED_MODEL` is configured and `external_id` is non-empty.
- **FR-003**: When `TAXOMESH_CATEGORY_LINKED_MODEL` is not set or the external object is not found, the admin MUST display `external_id` as plain text without raising any error.
- **FR-004**: The admin Category and Item list views MUST include UUID fields (`category_id`, `item_id`) in the searchable fields so that partial UUID strings match records.
- **FR-005**: The generic admin mixin (`ItemCategoryAssignmentMixin`) MUST automatically include `TaxomeshCategoryListFilter` in its `list_filter` so that external model admins get a taxomesh-category sidebar filter with no extra configuration.
- **FR-006**: The Category admin list MUST support a filter for "has linked object" (categories with non-empty `external_id`; no external DB verification required — non-empty field value is the sufficient proxy condition).
- **FR-007**: The CLI `graph` command's relation display MUST default to showing relations (opt-out available via explicit flag).
- **FR-008**: The admin graph view MUST display item relations by default, with no opt-in required.
- **FR-009**: `TaxomeshService.create_category()` MUST accept an optional `external_id: str = ""` parameter and persist it on the created category.
- **FR-010**: `TaxomeshService.update_category()` MUST accept an optional `external_id: str | None = None` parameter; a non-None value MUST be persisted; a None value MUST leave the existing `external_id` unchanged.
- **FR-011**: `TaxomeshService.list_categories()` MUST accept an optional `external_id: str | None = None` keyword parameter; when supplied, only categories matching that exact `external_id` value MUST be returned.
- **FR-012**: `TaxomeshService.get_debug()` MUST return a `dict` containing at minimum the keys: `version` (installed taxomesh version string), `config_name` (config name or `None`), `repository_type` (class name of the active repository), and `working_path` (relevant path string or `None`).
- **FR-013**: The Django admin MUST expose a read-only diagnostic page whose admin home entry appears under the TAXOMESH app group; the page MUST instantiate `TaxomeshService()` with no arguments (auto-discovery) to obtain its data, with no new Django setting required.
- **FR-014**: The diagnostic admin page MUST display all four values returned by `TaxomeshService.get_debug()` as read-only fields.
- **FR-015**: All repository backends (JSON, YAML, Django ORM) MUST be supported by `get_debug()` without raising errors.

### Key Entities

- **Category**: Domain entity with an existing `external_id: str` field. The service layer gains full CRUD exposure for this field.
- **TaxomeshService**: Application facade — gains `external_id` parameters on `create_category`, `update_category`, and `list_categories`, plus a new `get_debug()` method.
- **TAXOMESH_CATEGORY_LINKED_MODEL**: A new Django settings key (analogous to the existing Item-linked-model key) that scopes external object resolution to Category records only.
- **Diagnostic admin page**: A new read-only admin view (using a proxy model pattern to avoid a new database table) registered under the TAXOMESH app group.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can navigate from a Category admin list row to the linked external object in 2 clicks or fewer, when `TAXOMESH_CATEGORY_LINKED_MODEL` is configured.
- **SC-002**: A partial UUID of 8 or more characters entered in the admin search box returns the matching record without error.
- **SC-003**: A developer can create, update, and list categories with `external_id` values exclusively through `TaxomeshService`, with zero calls to internal repository or domain APIs.
- **SC-004**: `get_debug()` returns accurate values for all four keys across all three supported repository backends (JSON, YAML, Django ORM).
- **SC-005**: The admin diagnostic page is reachable in 1 click from the Django admin home page, under the TAXOMESH section.
- **SC-006**: The CLI graph command run without arguments shows item relations for all items that have outgoing relations, without requiring any additional flags.
- **SC-007**: The full test suite passes with ≥ 80% coverage after all changes are implemented.

## Clarifications

### Session 2026-03-08

- Q: For the "has linked object" admin filter (FR-006), what constitutes "has linked object"? → A: Non-empty `external_id` field only (no external DB query); non-empty `external_id` is the sufficient proxy condition.
- Q: Should `TaxomeshCategoryListFilter` be auto-included in `ItemCategoryAssignmentMixin.list_filter` or opt-in? → A: Auto-included — the mixin appends the filter to `list_filter` automatically.
- Q: How should the admin debug page obtain its `TaxomeshService` instance? → A: Auto-instantiate via `TaxomeshService()` (auto-discovers `taxomesh.toml` from the working directory; no new Django setting required).

## Assumptions

- `TAXOMESH_CATEGORY_LINKED_MODEL` follows the same Django `"app_label.ModelName"` string format as the existing item-linked-model configuration key.
- Partial UUID search is a case-insensitive substring match on the string representation of the UUID field.
- `list_categories(external_id=...)` performs an exact-match filter (not substring), consistent with how the existing `get_categories_by_external_id()` service method works.
- `get_debug()` reads the installed package version from standard package metadata; no hardcoded version string is used.
- The diagnostic admin page uses a proxy model pattern (same approach as `CategoryGraphProxy`) to appear in the admin without requiring a new database table or migration.
- The admin debug page instantiates `TaxomeshService()` with no arguments (auto-discovers `taxomesh.toml`); no new Django setting is introduced for this purpose.
- Changing the `show-relations` default does not affect callers that already pass the flag explicitly; the change is backwards-compatible.
- The `working_path` value in `get_debug()` is the file path for file-backed repositories or the Django settings database name for ORM-backed repositories.
