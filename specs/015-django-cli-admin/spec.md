# Feature Specification: Django CLI Compatibility and Admin Graph View

**Feature Branch**: `015-django-cli-admin`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: Fix CLI when taxomesh.toml uses type=django (ImproperlyConfigured error); add a Graph view in Django admin under the taxomesh section that displays the taxonomy graph in a visually styled way.

## Clarifications

### Session 2026-03-01

- Q: Should `--show-config` be updated to correctly handle `type = "django"` as part of this feature? → A: Yes — update `--show-config` to display the django type correctly (shows active `using` alias instead of a file path; lists `"django"` as an accepted value in the comment). Additionally, the bare `"django"` string literal must be replaced by a named constant `DJANGO_REPO_TYPE` in `django_repository.py` (matching the existing `YAML_REPO_TYPE` / `JSON_REPO_TYPE` pattern), and a single aggregate constant `SUPPORTED_REPO_TYPES` must be introduced as the canonical list of all valid type values.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CLI: Clear Error When Django Is Not Configured (Priority: P1)

A developer has a `taxomesh.toml` with `type = "django"` in a project that uses Django as the
storage backend. When they run any taxomesh CLI command from a shell where `DJANGO_SETTINGS_MODULE`
is not set, they currently receive Django's cryptic internal error
(`ImproperlyConfigured: Requested setting INSTALLED_APPS, but settings are not configured`).
They need a clear, actionable message that tells them exactly what to do.

**Why this priority**: The CLI is broken for all Django-backed projects — every taxomesh CLI
command fails immediately. This is a usability regression that blocks productive use of the tool.

**Independent Test**: Can be fully tested by pointing a taxomesh.toml at `type = "django"`,
running `taxomesh category list` without `DJANGO_SETTINGS_MODULE` set, and verifying the
error output is a clear taxomesh message with instructions — not Django's internal error.

**Acceptance Scenarios**:

1. **Given** `taxomesh.toml` has `[repository] type = "django"` and `DJANGO_SETTINGS_MODULE`
   is not set in the environment, **When** the user runs any taxomesh CLI command (e.g.,
   `taxomesh category list`), **Then** the CLI exits with code 1 and prints a clear error
   to stderr: the message must identify the problem (Django settings not configured) and
   include an explicit instruction on how to fix it (set `DJANGO_SETTINGS_MODULE`).

2. **Given** `taxomesh.toml` has `[repository] type = "django"` and `DJANGO_SETTINGS_MODULE`
   is set to a valid Django settings module, **When** the user runs any taxomesh CLI command,
   **Then** the command executes normally using the Django ORM backend — no error is shown
   and the operation completes as expected.

3. **Given** `taxomesh.toml` has `[repository] type = "yaml"` (non-Django type), **When**
   the user runs any taxomesh CLI command, **Then** no change in existing behaviour —
   commands execute as before.

4. **Given** `taxomesh.toml` has `[repository] type = "django"`, **When** the user runs
   `taxomesh --show-config`, **Then** the output shows `type = "django"` and the active
   `using` alias (e.g., `using = "default"`), and the accepted-values comment lists all
   three valid type values: `"yaml"`, `"json"`, and `"django"`.

---

### User Story 2 - Django Admin: Taxonomy Graph View (Priority: P2)

A Django site administrator uses the Django admin to manage taxomesh categories and items.
They want a dedicated "Graph" page under the taxomesh section that shows the full taxonomy
hierarchy in a visual, easy-to-read format — comparable to the `taxomesh graph` CLI command
but rendered as an HTML page in the browser.

**Why this priority**: The admin graph view is a new feature that requires Django admin to
be functioning first, but does not depend on the CLI fix.

**Independent Test**: Can be fully tested by registering a custom admin view in the taxomesh
contrib app, navigating to it in a running Django development server, and verifying the
taxonomy tree is displayed with visual structure matching the stored categories and items.

**Acceptance Scenarios**:

1. **Given** a Django site with `taxomesh.contrib.django` in `INSTALLED_APPS`, **When**
   an admin user navigates to the **main Django admin index** (`/admin/`), **Then** a "Graph"
   link is visible in the Taxomesh section alongside the existing Category, Item, and Tag
   model links — no extra clicks required. Clicking "Graph" redirects to the graph page.

2. **Given** the admin user clicks the "Graph" link, **When** the page loads, **Then** the
   taxonomy tree is displayed as a styled, indented HTML structure showing all categories and
   their items; root categories are at the top level; child categories are indented under their
   parents; items appear under their category; enabled and disabled entries are visually
   distinguished (e.g., different colour or icon).

3. **Given** the taxonomy has no categories yet, **When** the admin user navigates to the
   Graph page, **Then** a meaningful empty-state message is shown (e.g., "No categories
   found. Add one to get started.") instead of a blank page.

4. **Given** the graph page is loaded, **When** the page renders, **Then** the page uses
   Django admin's standard base template (header, sidebar, breadcrumbs) so it appears
   consistent with the rest of the admin site. No external CSS or JS libraries are required.

---

### Edge Cases

- What happens when `DJANGO_SETTINGS_MODULE` is set but points to an invalid/missing module?
  The existing Django import error propagates; taxomesh wraps it as a `TaxomeshRepositoryError`
  with a message that includes the original cause.
- What happens when the Django database is unreachable at graph render time? The admin view
  catches repository errors and displays an error message on the page rather than a 500 error.
- What happens when a category appears under multiple parents (DAG, not a tree)? Each
  occurrence of the category is rendered at each parent position — same behaviour as the
  CLI `graph` command.
- What happens if `taxomesh.contrib.django` is not in `INSTALLED_APPS`? The admin view
  does not exist; no change to existing behaviour.
- What happens when `taxomesh --show-config` is run with `type = "django"` but no `using`
  key in the TOML? The output shows the default alias (`"default"`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the taxomesh CLI detects `type = "django"` in the effective configuration
  and the Django settings are not configured (i.e., `DJANGO_SETTINGS_MODULE` is not set or
  Django raises `ImproperlyConfigured`), the CLI MUST exit with code 1 and print a
  human-readable error message to stderr that: (a) identifies the repository type as `django`,
  (b) states that Django settings are not configured, and (c) instructs the user to set
  `DJANGO_SETTINGS_MODULE`.

- **FR-002**: When the taxomesh CLI detects `type = "django"` and Django is properly
  configured (valid `DJANGO_SETTINGS_MODULE` in environment), all existing CLI commands
  MUST operate normally against the Django ORM backend without any change in command
  interface or output format.

- **FR-003**: The existing behaviour of the CLI for `yaml` and `json` repository types MUST
  remain unchanged.

- **FR-004**: The `--show-config` flag MUST correctly handle `type = "django"`: it MUST
  output `type = "django"` and the active `using` alias (defaulting to `"default"` when
  not set in TOML) instead of a file path. The accepted-values comment in the output MUST
  list all valid type values, derived from the `SUPPORTED_REPO_TYPES` constant.

- **FR-005**: A named constant `DJANGO_REPO_TYPE: Final[str] = "django"` MUST be defined
  in `django_repository.py`, matching the existing `YAML_REPO_TYPE` / `JSON_REPO_TYPE`
  pattern. All bare `"django"` string literals used as a repository type identifier MUST be
  replaced with this constant.

- **FR-006**: A single aggregate constant `SUPPORTED_REPO_TYPES: Final[tuple[str, ...]]`
  MUST be introduced as the canonical, exhaustive list of all valid `repository.type` values.
  It MUST reference `YAML_REPO_TYPE`, `JSON_REPO_TYPE`, and `DJANGO_REPO_TYPE`. All code
  that currently enumerates valid types (error messages, config comments, etc.) MUST derive
  from this constant rather than inline literals.

- **FR-007**: The `taxomesh.contrib.django` admin MUST expose a "Graph" page accessible from
  the taxomesh section of the Django admin site. The page MUST be reachable by any staff
  user with access to the taxomesh section.

- **FR-008**: The Graph admin page MUST call `TaxomeshService.get_graph()` using a
  `DjangoRepository` initialised with the default database alias and render the result as
  an indented HTML tree structure.

- **FR-009**: The Graph admin page MUST render using Django admin's standard base template
  so it inherits the admin header, navigation, and branding without any external CSS or JS
  dependencies.

- **FR-010**: Categories in the Graph page MUST display their name, UUID, and enabled status.
  Items under a category MUST display their external identifier and enabled status.

- **FR-011**: The Graph admin page MUST display a non-empty message when no categories exist.

- **FR-012**: The Graph admin page MUST handle repository errors gracefully: if `get_graph()`
  raises a `TaxomeshError`, the page MUST display the error message to the admin user rather
  than rendering a server error page.

### Key Entities

- **TaxomeshGraph / CategoryNode**: The domain objects returned by `get_graph()`. The graph
  view renders from this structure. No new data entities are introduced.
- **Graph admin view**: A Django admin view registered on the taxomesh app's `AdminSite`
  entry, linked from the taxomesh app index. Not a `ModelAdmin` — it is a custom view.
- **`DJANGO_REPO_TYPE`**: Named constant in `django_repository.py` holding the string
  identifier `"django"` for the Django-backed repository type.
- **`SUPPORTED_REPO_TYPES`**: Aggregate constant (single source of truth) listing all valid
  `repository.type` values. Consumed by config dump output, error messages, and any
  validation logic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer using a Django-backed taxomesh.toml who runs any CLI command
  without `DJANGO_SETTINGS_MODULE` set receives an error message that includes the word
  "DJANGO_SETTINGS_MODULE" within 1 second — eliminating the need to interpret Django's
  internal configuration traceback.

- **SC-002**: A developer who sets `DJANGO_SETTINGS_MODULE` correctly can run all taxomesh
  CLI commands against a Django-backed project without any additional configuration steps.

- **SC-003**: Running `taxomesh --show-config` with `type = "django"` in the TOML produces
  output that contains `type = "django"` and a `using` key showing the active alias —
  no file-path key is emitted.

- **SC-004**: An admin user can navigate from the taxomesh admin section to the Graph view
  in at most 2 clicks (section index → Graph link).

- **SC-005**: The Graph admin page renders the complete taxonomy (all categories and items)
  in a single page load without pagination; the page is self-contained and requires no
  browser-side JavaScript to display the tree.

- **SC-006**: No bare `"django"` string literal used as a repository type identifier
  remains anywhere in the codebase — confirmed by a grep check during review.

- **SC-007**: All quality gates pass: linting, formatting, strict type checking, and test
  coverage ≥ 80%.

## Assumptions

- The CLI fix applies at the point where the Django-type repository is instantiated. The
  error interception catches `django.core.exceptions.ImproperlyConfigured` and re-raises
  it as a user-friendly message; the existing `TaxomeshRepositoryError` wrapper mechanism
  is used.
- The admin graph view does not introduce new URL patterns outside the Django admin site.
  It is registered as a custom URL on the existing `AdminSite` via the taxomesh contrib
  app's `AppConfig`.
- The graph page renders as a server-side HTML tree using Django's template engine;
  no client-side JavaScript or charting libraries are needed. Visual distinction between
  enabled/disabled entries is achieved with CSS (colour or text styling) scoped to the
  admin template.
- The `DjangoRepository` used by the Graph admin view is instantiated with the default
  database alias (`"default"`). No configuration option for the alias is exposed in the
  admin view at this stage.
- The Graph admin view is only accessible to staff users (Django admin access control).
  No taxomesh-specific permission model is added.
- `SUPPORTED_REPO_TYPES` is placed where it can be imported without creating circular
  dependencies — most likely in a shared constants module or in `cli/config.py` where it
  is already consumed, assembling from the three per-adapter constants.
