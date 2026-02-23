# Feature Specification: Command-Line Interface (CLI)

**Feature Branch**: `004-cli`
**Created**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Status**: Draft
**Input**: Add a CLI using Typer. Commands: `taxomesh [category|item|tag] [list|add|update|delete]`.
Options passed as `--name`, `--description`, etc. Config file (`taxomesh.toml`) selects the
repository backend. README updated to feature CLI as the primary usage path.
Errors exit with non-zero status and verbose output. CLI tests required.

**Amendments in rev 3**:
1. `Item` domain model does NOT gain `name` or `description` fields. Items are registered
   purely by `external_id`; name/description come from the referenced external system.
2. `Category.description` changes from `Optional[str] = None` to `str = ""`.
3. `category list` gains an optional `--parent-id <uuid>` filter to list child categories
   of a given parent, ordered by `sort_index`. `item list` gains an optional
   `--category-id <uuid>` filter to list items in a given category, ordered by `sort_index`.
4. `item_parent_links` and `category_parent_links` are internal repository implementation
   details. The service exposes `list_items(category_id=…)` and
   `list_categories(parent_id=…)` so callers never interact with link objects directly.

**Amendments in rev 2**:
1. `taxomesh category add/update` gains `--parent-id` and `--sort-index` to assign a parent
   relationship atomically with the create/update operation.
2. `taxomesh item add/update` gains optional inline `--category-id [--sort-index]` and
   `--tag-id` options. Dedicated `item add-to-category` and `item add-to-tag` sub-commands
   are also added as standalone alternatives.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Manage categories from the terminal (Priority: P1)

A developer maintains a product catalogue. They want to organise their categories directly
from a shell without writing Python. They install taxomesh, run `taxomesh category add`
to create a category (optionally assigning a parent in the same command), `taxomesh category list`
to inspect what exists (optionally filtered by parent), `taxomesh category update` to correct
a name or add a parent, and `taxomesh category delete` to remove one they no longer need.

**Why this priority**: Category management is the core purpose of the library; the CLI must
cover it completely before any other entity group.

**Independent Test**: Can be fully exercised by invoking the CLI via Typer's `CliRunner`
without a real filesystem or running process.

**Acceptance Scenarios**:

1. **Given** no categories exist, **When** the developer runs `taxomesh category list`,
   **Then** the output is empty (or a friendly "no categories" message) and the exit code is 0.
2. **Given** the developer runs `taxomesh category add --name "Music"`,
   **Then** the new category is printed with its UUID and exit code is 0.
3. **Given** two categories exist, **When** the developer runs
   `taxomesh category add --name "Jazz" --parent-id <music-id>`,
   **Then** the new category is printed and a parent relationship with "Music" is persisted.
4. **Given** a category exists, **When** the developer runs
   `taxomesh category update <id> --name "New Name"`,
   **Then** the updated category is printed and exit code is 0.
5. **Given** a category exists, **When** the developer runs
   `taxomesh category update <id> --parent-id <other-id>`,
   **Then** the parent relationship is added and a confirmation is printed.
6. **Given** a category ID does not exist, **When** the developer runs
   `taxomesh category delete <id>`,
   **Then** a descriptive error is printed to stderr and exit code is non-zero.
7. **Given** the developer runs `taxomesh category --help`,
   **Then** all sub-commands and their options are described in the output.
8. **Given** a parent category and two child categories exist, **When** the developer runs
   `taxomesh category list --parent-id <parent-id>`,
   **Then** only the child categories are printed, ordered by their `sort_index`.

---

### User Story 2 — Manage items from the terminal (Priority: P1)

A developer wants to register item references (by integer ID, string slug, or UUID)
into taxomesh from the shell. Items are identified solely by their `external_id`; name,
description, and other metadata live in the external system referenced by that ID. The
developer can optionally assign the item to a category and/or a tag in the same `add`
command, or use dedicated `add-to-category` / `add-to-tag` sub-commands later. The
developer can list items globally or filtered by category (ordered by sort_index).

**Why this priority**: Items are the atomic units that categories and tags are applied to.

**Independent Test**: Invocable via Typer's `CliRunner` in isolation.

**Acceptance Scenarios**:

1. **Given** the developer runs `taxomesh item add --external-id 42`,
   **Then** a new item is printed with its internal UUID and exit code is 0.
2. **Given** the developer runs
   `taxomesh item add --external-id "slug" --category-id <id> --sort-index 2 --tag-id <tag-id>`,
   **Then** the item is created, placed in the category, and assigned the tag in one step.
3. **Given** an existing item, **When**
   `taxomesh item add-to-category ITEM_ID --category-id <id> --sort-index 1` is run,
   **Then** the placement is persisted and a confirmation is printed.
4. **Given** an existing item and tag, **When**
   `taxomesh item add-to-tag ITEM_ID --tag-id <id>` is run,
   **Then** the assignment is persisted and a confirmation is printed.
5. **Given** an item does not exist, **When** `taxomesh item delete <id>` is run,
   **Then** a descriptive error is printed to stderr and exit code is non-zero.
6. **Given** a category with two items (sort_index 1 and 2), **When**
   `taxomesh item list --category-id <id>` is run,
   **Then** only those two items are printed, ordered by sort_index.

---

### User Story 3 — Manage tags from the terminal (Priority: P1)

A developer maintains a set of free-form labels and wants to manage them from the shell.
They create tags with `taxomesh tag add --name`, list them with `taxomesh tag list`,
rename them with `taxomesh tag update`, and delete them with `taxomesh tag delete`.

**Why this priority**: Tags are the third entity group; completing all three gives
a fully operational CLI.

**Independent Test**: Invocable via Typer's `CliRunner` in isolation.

**Acceptance Scenarios**:

1. **Given** the developer runs `taxomesh tag add --name "live"`,
   **Then** a new tag is printed with its UUID and exit code is 0.
2. **Given** a tag exists, **When** `taxomesh tag update <id> --name "studio"` is run,
   **Then** the updated tag is printed and exit code is 0.
3. **Given** a tag exists, **When** `taxomesh tag delete <id>` is run,
   **Then** a confirmation is printed and exit code is 0.
4. **Given** a tag name exceeds 25 characters, **When** `taxomesh tag add --name <long>` is run,
   **Then** a descriptive validation error is printed to stderr and exit code is non-zero.

---

### User Story 4 — Configure the storage backend via config file (Priority: P1)

A developer wants taxomesh to persist data to a specific JSON file rather than the default
`taxomesh.json`. They create a `taxomesh.toml` in their project directory, set
`[repository] type = "json"` and `path = "/data/my_taxonomy.json"`. When they run any
CLI command, taxomesh reads the config and uses that file.

**Acceptance Scenarios**:

1. **Given** a `taxomesh.toml` exists with `[repository] type = "json" path = "custom.json"`,
   **When** any CLI command is run without `--config`,
   **Then** `custom.json` is used as the storage file.
2. **Given** no `taxomesh.toml` exists in CWD,
   **When** any CLI command is run,
   **Then** the CLI defaults to `JsonRepository` with path `taxomesh.json` and exits with code 0.
3. **Given** the developer passes `--config /path/to/other.toml`,
   **When** any CLI command is run,
   **Then** the config file at that path is used instead of the default.
4. **Given** a `taxomesh.toml` contains invalid TOML syntax,
   **When** any CLI command is run,
   **Then** a descriptive parse error is printed to stderr and exit code is non-zero.

---

### User Story 5 — All errors produce a non-zero exit code and verbose output (Priority: P1)

A developer scripting taxomesh in a shell pipeline needs reliable exit codes so they can
detect failures. Any error — not-found, validation, repository, config parse — must exit
with a non-zero status code and print a clear message to stderr.

**Acceptance Scenarios**:

1. **Given** a command targets a non-existent entity, **When** it is run,
   **Then** exit code is 1 and stderr contains the entity type and ID.
2. **Given** a required option is missing, **When** the command is run,
   **Then** Typer's built-in error handling produces a descriptive message and non-zero exit.
3. **Given** a `JsonRepository` file is corrupted, **When** any command is run,
   **Then** a `TaxomeshRepositoryError` message is printed to stderr and exit code is 1.

---

### Edge Cases

- `taxomesh category update <id>` with no `--name`, `--description`, or `--parent-id`:
  the CLI raises a usage error and exits non-zero.
- `taxomesh item update <id>` with no options at all:
  the CLI raises a usage error and exits non-zero.
- `taxomesh category add --name "Jazz" --parent-id <id>` where `<id>` does not exist:
  the category IS created first; then `add_category_parent` raises `TaxomeshCategoryNotFoundError`
  and the CLI exits 1. *(The created category persists — cleanup is a future concern.)*
- `taxomesh category update <id> --parent-id <same-id>` (self-loop):
  `TaxomeshCyclicDependencyError` is raised; the CLI prints it and exits 1.
- `taxomesh item add --external-id 42 --category-id <id>` where category does not exist:
  the item IS created first; then the placement fails with `TaxomeshCategoryNotFoundError`;
  the CLI exits 1.
- Passing a non-UUID string as `<category-id>` / `<item-id>` / `<tag-id>` argument:
  the CLI catches the parse error and exits non-zero with a descriptive message.
- The `taxomesh.toml` file exists but is missing the `[repository]` section:
  defaults are applied for all missing keys.
- `[repository] type` value other than `"json"`: config error, exit non-zero.
- `taxomesh category list --parent-id <id>` where the category does not exist:
  raises `TaxomeshCategoryNotFoundError`; the CLI prints it and exits 1.
- `taxomesh item list --category-id <id>` where the category does not exist:
  raises `TaxomeshCategoryNotFoundError`; the CLI prints it and exits 1.

---

## Requirements *(mandatory)*

### Functional Requirements

**CLI entry point:**
- **FR-001**: The package MUST register a `taxomesh` entry point in `[project.scripts]` in
  `pyproject.toml`, pointing to the Typer application.
- **FR-002**: The CLI MUST be implemented using **Typer**.
- **FR-003**: The CLI MUST expose three sub-command groups: `category`, `item`, `tag`.
- **FR-004**: Each sub-command group MUST expose at minimum: `list`, `add`, `delete`, `update`.
  The `item` group additionally exposes `add-to-category` and `add-to-tag`.
- **FR-005**: Every command and sub-command group MUST support `--help`.

**Configuration:**
- **FR-006**: The CLI MUST read a `taxomesh.toml` configuration file from the current working
  directory at startup. If the file is absent, defaults are used silently.
- **FR-007**: Default configuration: `[repository] type = "json"`, `path = "taxomesh.json"`.
- **FR-008**: The root CLI command MUST accept a `--config <path>` option to override the
  default config file location.
- **FR-009**: If the config file is found but cannot be parsed as valid TOML, the CLI MUST
  print a descriptive error to stderr and exit with a non-zero status code.

**Category sub-commands:**
- **FR-010**: `taxomesh category add --name <name> [--description <desc>] [--parent-id <uuid> [--sort-index <int>]]`
  MUST create a category and — if `--parent-id` is given — call `add_category_parent` immediately after.
- **FR-011**: `taxomesh category list [--parent-id <uuid>]` MUST print all categories when
  `--parent-id` is absent, or print only the child categories of the given parent ordered by
  `sort_index` when it is present. Exit 0 always (including when the filter yields no results).
- **FR-012**: `taxomesh category delete <category-id>` MUST delete the category and print a confirmation.
- **FR-013**: `taxomesh category update <category-id> [--name <name>] [--description <desc>] [--parent-id <uuid> [--sort-index <int>]]`
  MUST update the specified fields and/or add a parent relationship. At least one option MUST be provided.

**Item sub-commands:**
- **FR-014**: `taxomesh item add --external-id <id> [--category-id <uuid> [--sort-index <int>]] [--tag-id <uuid>]`
  MUST create an item and — if `--category-id` is given — call `place_item_in_category`; if
  `--tag-id` is given — call `assign_tag`. Assignments are performed after item creation.
  `--external-id` is parsed: UUID → int → str.
- **FR-015**: `taxomesh item list [--category-id <uuid>]` MUST print all items when
  `--category-id` is absent, or print only items placed in the given category ordered by
  `sort_index` when it is present. Exit 0 always.
- **FR-016**: `taxomesh item delete <item-id>` MUST delete the item and print a confirmation.
- **FR-017**: `taxomesh item update <item-id> [--enable | --disable] [--category-id <uuid> [--sort-index <int>]] [--tag-id <uuid>]`
  MUST update the enabled flag and/or make assignments. At least one option MUST be provided.
- **FR-018**: `taxomesh item add-to-category ITEM_ID --category-id <uuid> [--sort-index <int>]`
  MUST place the item in the category. Idempotent.
- **FR-019**: `taxomesh item add-to-tag ITEM_ID --tag-id <uuid>`
  MUST assign the tag to the item. Idempotent (delegates to `assign_tag`).

**Tag sub-commands:**
- **FR-020**: `taxomesh tag add --name <name>` MUST create a tag and print it to stdout.
- **FR-021**: `taxomesh tag list` MUST print all tags. Exit 0 always.
- **FR-022**: `taxomesh tag delete <tag-id>` MUST delete the tag and print a confirmation.
- **FR-023**: `taxomesh tag update <tag-id> --name <name>` MUST rename the tag and print the updated entity.

**Error handling:**
- **FR-024**: Any `TaxomeshError` raised during a command MUST be caught by the CLI, its
  message printed to stderr, and the process MUST exit with status code 1.
- **FR-025**: Any unexpected exception MUST be caught, printed to stderr, and exit with status code 1.

**Domain model changes:**
- **FR-026**: `Category.description` MUST change from `Optional[str] = None` to
  `Annotated[str, Field(max_length=100_000)] = ""`. Existing JSON files that have
  `"description": null` MUST load cleanly via a Pydantic `BeforeValidator` that coerces
  `None` → `""`.

**Service layer extensions:**
- **FR-027**: `TaxomeshService` MUST be extended with `update_category(category_id, name, description) -> Category`.
- **FR-028**: `TaxomeshService` MUST be extended with `update_item(item_id, enabled) -> Item`.
  Only the `enabled` flag is updatable; items carry no name or description.
- **FR-029**: `TaxomeshService` MUST be extended with `update_tag(tag_id, name) -> Tag`.
- **FR-030**: `TaxomeshService` MUST be extended with `delete_tag(tag_id) -> None`.
- **FR-031**: `TaxomeshService` MUST be extended with
  `place_item_in_category(item_id, category_id, sort_index=0) -> ItemParentLink`.
  If the placement already exists, `sort_index` MUST be updated (upsert, idempotent).
- **FR-032**: `TaxomeshService.list_items` MUST accept an optional `category_id: UUID | None = None`
  keyword argument. When `None`, all items are returned (existing behaviour). When a UUID is
  provided, only items placed in that category are returned, ordered ascending by `sort_index`.
  `TaxomeshCategoryNotFoundError` MUST be raised if the category does not exist.
- **FR-033**: `TaxomeshService.list_categories` MUST accept an optional `parent_id: UUID | None = None`
  keyword argument. When `None`, all categories are returned (existing behaviour). When a UUID
  is provided, only child categories of that parent are returned, ordered ascending by
  `sort_index`. `TaxomeshCategoryNotFoundError` MUST be raised if the parent does not exist.

**Repository layer extensions:**
- **FR-034**: `TaxomeshRepositoryBase` MUST be extended with `delete_tag(tag_id: UUID) -> bool`
  (16th Protocol method).
- **FR-035**: `TaxomeshRepositoryBase` MUST be extended with
  `save_item_parent_link(link: ItemParentLink) -> None` (17th Protocol method). Implementations
  MUST be idempotent: if a link with the same `(item_id, category_id)` pair already exists,
  the existing record is updated (sort_index replaced); no duplicate is added.
- **FR-036**: `TaxomeshRepositoryBase` MUST be extended with
  `list_item_parent_links() -> list[ItemParentLink]` (18th Protocol method). Used internally
  by the service layer; callers should not interact with link objects directly.
- **FR-037**: `JsonRepository` MUST implement `delete_tag`, `save_item_parent_link`, and
  `list_item_parent_links`.

**README:**
- **FR-038**: `README.md` MUST be updated to show the CLI as the first/primary usage method,
  above the Python API quick start.

**Tests:**
- **FR-039**: A `tests/test_cli.py` module MUST be created covering: all sub-commands (happy
  path), all not-found error paths, config file loading, default-config fallback, inline
  category/tag assignment on `item add`, `item add-to-category`, `item add-to-tag`,
  `category list --parent-id`, and `item list --category-id`.
  Tests MUST use Typer's `CliRunner`.

### Key Entities

- **`taxomesh` CLI entry point**: Typer application registered in `pyproject.toml`.
- **`taxomesh/adapters/cli/`**: New package.
  - `main.py`: Typer app and all command implementations.
  - `config.py`: Config file loading; builds `TaxomeshService`.
- **`taxomesh.toml`**: TOML config file (user-created, not shipped).
- **`Category`** (modified): `description` changes from `Optional[str]` to `str = ""`.
- **`ItemParentLink`**: existing domain model; used internally by the service.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `taxomesh category add --name "Music"` prints a `Category` with UUID, exits 0.
- **SC-002**: `taxomesh category add --name "Jazz" --parent-id <id>` creates category and
  parent link atomically; exits 0.
- **SC-003**: `taxomesh item add --external-id 99` prints an `Item` with `external_id=99`, exits 0.
- **SC-004**: `taxomesh item add --external-id 1 --category-id <id>` places the item in the
  category in one command; exits 0.
- **SC-005**: `taxomesh item add-to-category ITEM_ID --category-id <id>` places existing item.
- **SC-006**: `taxomesh item add-to-tag ITEM_ID --tag-id <id>` assigns tag to existing item.
- **SC-007**: `taxomesh tag add --name "live"` prints tag, exits 0.
- **SC-008**: Any command targeting a non-existent entity exits 1, stderr has typed error message.
- **SC-009**: Valid `taxomesh.toml` causes correct repo path to be used.
- **SC-010**: Absent `taxomesh.toml` → defaults used, no error.
- **SC-011**: All `--help` flags produce readable output.
- **SC-012**: All quality gates pass: `ruff check`, `ruff format --check`, `mypy --strict`,
  `pytest --cov=taxomesh --cov-fail-under=80`.
- **SC-013**: `taxomesh category update <id>` with no options exits non-zero.
- **SC-014**: `taxomesh category list --parent-id <id>` returns child categories ordered by sort_index.
- **SC-015**: `taxomesh item list --category-id <id>` returns items ordered by sort_index.

---

## Assumptions

- The CLI is synchronous.
- `--external-id` parsing order: UUID → int → str. No ambiguity error is raised.
- `metadata` is not exposed via the CLI for add or update commands (future spec).
- `taxomesh tag delete` deletes the tag entity itself, not a tag-item association.
- Tag-item association management via `assign_tag`/`remove_tag` is exposed through
  `item add-to-tag` (and inline on `item add/update`). A dedicated `item remove-from-tag`
  is out of scope for this spec.
- `update_*` service methods are partial updates: only non-`None` arguments are applied.
- Calling an update method with all-`None` arguments is a no-op at the service level; the
  CLI layer guards against it.
- `place_item_in_category` is idempotent: if `(item_id, category_id)` already exists, the
  sort_index is updated (upsert behaviour).
- When `item add --category-id` or `--tag-id` is provided and the assignment fails (e.g.,
  category not found), the item has already been created. Cleanup is a future concern.
- Typer is added as a mandatory runtime dependency.
- `[repository] type` only supports `"json"` in this spec.
- `Category.description` existing JSON files may contain `"description": null`; a Pydantic
  `BeforeValidator` coerces `None` to `""` at load time — no data migration is required.
- Root categories (categories with no parent) are categories that do not appear as a child
  in any `CategoryParentLink`. Listing root categories is out of scope; clients can filter
  client-side from `list_categories()`.
