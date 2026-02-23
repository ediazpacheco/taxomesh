# Research: Command-Line Interface (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Status**: Complete — all design decisions resolved.

---

## Decision 1 — CLI library: Typer over Click or argparse

**Decision**: Use **Typer** as the CLI framework.

**Rationale**:
- Typer uses Python type annotations to define arguments and options — consistent with the
  project's mypy-strict, Pydantic-based style.
- `--help` is generated automatically from type annotations and docstrings.
- Typer's `CliRunner` provides an idiomatic test harness that invokes commands in-process.
- Integrates with `rich` for coloured output (opt-in).

**Alternatives considered**:
- **Click** — rejected: explicit decorator boilerplate; no type-annotation-driven ergonomics.
- **argparse (stdlib)** — rejected: sub-command trees are verbose; no integrated test runner.

---

## Decision 2 — Configuration file format: TOML via stdlib `tomllib`

**Decision**: Configuration file is named `taxomesh.toml`, parsed with Python 3.11's
stdlib `tomllib` (read-only). No additional dependency needed.

**Rationale**:
- Python 3.11 ships `tomllib` (PEP 680). `requires-python = ">=3.11"` covers this.
- TOML has native types — no manual type-coercion of config values.
- Same format as `pyproject.toml`; familiar to the target audience.

**Alternatives considered**:
- **JSON** — rejected: no comments; less human-friendly.
- **INI / configparser** — rejected: all values are strings; requires coercion.
- **YAML** — rejected: optional dependency; TOML is simpler and stdlib.

---

## Decision 3 — Config file lookup strategy

**Decision**: CLI looks for `taxomesh.toml` in the **current working directory** only.
A `--config <path>` root option allows overriding this. Absence of the file is not an error.

**Rationale**:
- CWD-based lookup matches the convention of `pyproject.toml`, `ruff.toml`, etc.
- Single lookup point is simpler than a cascade.
- `--config` flag covers edge cases needing a different path.

**Alternatives considered**:
- User-home fallback — rejected: complexity and lookup ambiguity.
- `--config` required (no auto-lookup) — rejected: forces verbosity for the common case.

---

## Decision 4 — CLI adapter placement in the hexagonal architecture

**Decision**: CLI lives in `taxomesh/adapters/cli/`. It is an adapter (outermost layer)
that depends on `TaxomeshService` only. No direct repository access.

**Rationale**:
- Constitution Principle I: `adapters → application → ports → domain`.
- `main.py` — Typer app and all commands.
- `config.py` — Config loading; builds `TaxomeshService` from config.

**Alternatives considered**:
- `taxomesh/cli.py` (flat) — rejected: mixes adapter code into the package root.
- `taxomesh/application/cli.py` — rejected: CLI is an adapter, not application layer.

---

## Decision 5 — `--external-id` type parsing for `taxomesh item add`

**Decision**: `--external-id` is received as a raw string. The CLI parses it in order:
UUID → int → str. First successful parse wins. No error is raised for ambiguous input.

**Rationale**:
- `ExternalId` is `UUID | str | int`. A heuristic parse is the most ergonomic approach.
- UUID first (most specific), int second, string last.

**Alternatives considered**:
- Separate flags per type — rejected: verbose for one concept.
- Always string — rejected: loses type fidelity.

---

## Decision 6 — `update_*` as partial-update methods on `TaxomeshService`

**Decision**: `update_category`, `update_item`, and `update_tag` accept optional keyword
arguments. Only non-`None` fields are applied. Pydantic's `validate_assignment=True`
handles validation. Saves via existing `save_*` (upsert) — no new repository methods needed
for updates.

**Rationale**:
- Partial updates preserve unchanged fields — least surprising CLI behaviour.
- `validate_assignment=True` means direct attribute assignment triggers validators.
- Reusing `save_*` avoids adding `update_*` counterparts to the Protocol.

**Alternatives considered**:
- Full-replacement update — rejected: forces re-supply of all fields.
- Dedicated `update_*` repository methods — rejected: `save_*` already does upsert.

---

## Decision 7 — `delete_tag` added to `TaxomeshRepositoryBase` (16th method)

**Decision**: `delete_tag(tag_id: UUID) -> bool` is the 16th Protocol method. Tag entity
deletion was out of scope for spec 003 but is required by `taxomesh tag delete`.

**Rationale**:
- Full lifecycle management of tags (including deletion) is required for the CLI to be useful.
- Mirrors the existing `delete_category` / `delete_item` pattern exactly.

---

## Decision 8 — Typer as a mandatory runtime dependency

**Decision**: `typer` is added to `[project.dependencies]` as a mandatory runtime dependency.

**Rationale**:
- The CLI is a first-class feature; an optional extra would force an extra install step.
- `typer` is lightweight (pulls in `click`; `rich` is opt-in within Typer).

---

## Decision 9 — CLI output format: human-readable text, not JSON

**Decision**: All CLI output is human-readable text (labelled key: value lines). No JSON
output mode in this spec.

**Rationale**:
- Primary audience is a developer exploring or managing a taxonomy manually.
- `--output json` flag is a valid future extension.

---

## Decision 10 — Composition-root pattern for CLI → service construction

**Decision**: `config.py` reads TOML config, instantiates the repository adapter, and
returns a fully configured `TaxomeshService`. Every CLI command calls `build_service()`.

**Rationale**:
- Keeps repository construction logic out of `main.py` and makes it independently testable.
- CLI adapter is allowed to import from `adapters/repositories/` (both are adapter-layer).

---

## Decision 11 — `Item` carries no `name` or `description` fields

**Decision**: `Item` has NO `name` or `description` fields. Items are registered solely by
`external_id` (UUID | int | str). Name, description, and other presentation data live in
the external system referenced by `external_id`.

**Rationale**:
- taxomesh is a taxonomy/classification layer, not a content management system.
  Items represent references to external entities; their human-readable data should not
  be duplicated into taxomesh.
- Adding `name` and `description` would make `Item` resemble a CMS record, creating
  synchronisation burden (external system changes → stale taxomesh data).
- The `metadata: dict[str, Any]` field already exists for caller-specific key-value data
  should any lightweight annotation be needed without a full schema change.

**Alternatives considered**:
- `name: str = ""` with CLI `--name` required — rejected (rev 3): creates data duplication
  and maintenance burden; the authoritative name lives in the external system.
- `name: str | None = None` — rejected: same duplication concern; also inconsistent with
  the principle that None means "no value provided" in partial-update methods.

---

## Decision 12 — `item add` inline assignment vs. dedicated sub-commands

**Decision**: Both are supported. `taxomesh item add` and `taxomesh item update` accept
optional `--category-id [--sort-index]` and `--tag-id` flags for inline assignment.
`taxomesh item add-to-category` and `taxomesh item add-to-tag` are dedicated sub-commands
that operate on an already-existing item.

**Rationale**:
- Inline assignment is ergonomic when creating an item and immediately placing it — avoids
  a two-command sequence for the common case.
- Dedicated sub-commands are necessary for assigning existing items without re-creating them.
- Both paths call the same service methods (`place_item_in_category`, `assign_tag`), so no
  extra logic is duplicated.

**Alternatives considered**:
- Inline only (no dedicated sub-commands) — rejected: cannot assign an existing item
  without invoking `update` with a dummy field change.
- Dedicated sub-commands only — rejected: forces a two-command sequence for every new item
  that needs immediate placement.

---

## Decision 13 — `place_item_in_category` idempotency via upsert on `(item_id, category_id)`

**Decision**: `save_item_parent_link` MUST be an upsert: if a link with the same
`(item_id, category_id)` pair already exists, the existing record's `sort_index` is updated
in-place. No duplicate link is created.

**Rationale**:
- Idempotency makes CLI commands safe to retry — running `item add-to-category` twice with
  the same IDs should not accumulate duplicate records.
- Updating `sort_index` on a re-assignment is the most useful upsert behaviour: it lets the
  user reposition an item without a separate remove-then-add sequence.
- Mirrors the idempotency pattern of `assign_tag` (spec 003, Decision 6).

**Alternatives considered**:
- Always append (allow duplicates) — rejected: creates corrupt state; listing would return
  the same placement multiple times.
- Error on duplicate — rejected: breaks CLI idempotency; complicates retry logic.

---

## Decision 14 — `Category.description` changes from `Optional[str]` to `str = ""`

**Decision**: `Category.description` changes from `Annotated[str, Field(max_length=100_000)] | None = None`
to `Annotated[str, Field(max_length=100_000)] = ""`. A Pydantic `BeforeValidator` coerces
`None` → `""` on load to handle existing JSON files that stored `"description": null`.

**Rationale**:
- Consistency: all textual string fields on domain models should default to `""` (same as
  `Tag.name` is required; categories always have some notion of a description, even if empty).
- Eliminates `Optional` / `None` checks throughout the service and CLI layers.
- No migration needed: the `BeforeValidator` handles legacy `null` values transparently.

**Alternatives considered**:
- Keep `Optional[str] = None` — rejected: introduces `None` checks; inconsistent with the
  design goal of "required fields always have a value, even if empty".
- True migration script — rejected: over-engineered; the `BeforeValidator` covers this cleanly.

---

## Decision 15 — `list_items` / `list_categories` expose filtered, ordered views

**Decision**: `TaxomeshService.list_items(*, category_id: UUID | None = None)` and
`TaxomeshService.list_categories(*, parent_id: UUID | None = None)` accept an optional
filter. When the filter is provided, only records linked to that parent/category are
returned, ordered ascending by `sort_index`. The repository Protocol's
`list_item_parent_links()` and `list_category_parent_links()` are used internally.

**Rationale**:
- Callers should never need to know about `ItemParentLink` or `CategoryParentLink` objects.
  The service is the only consumer of these internal structures.
- Extending the existing `list_items` / `list_categories` signatures with keyword-only
  arguments is backward-compatible (existing callers that pass no arguments continue to work).
- Sort order by `sort_index` is the primary ordering consumers expect when viewing content
  within a category.

**Alternatives considered**:
- Separate `list_items_in_category(category_id)` method — rejected: duplicates the `list_items`
  concept; results in two methods with similar purpose.
- Returning `ItemParentLink` / `CategoryParentLink` objects — rejected: leaks internal
  implementation details to callers.

---

## Decision 16 — `category add --parent-id` partial failure behaviour

**Decision**: When `taxomesh category add --name X --parent-id Y` is run and the category
is created successfully but the subsequent `add_category_parent` call fails (e.g., `Y` does
not exist, or would create a cycle), the CLI prints the error and exits 1. The created
category is NOT rolled back; it persists in the repository.

**Rationale**:
- `TaxomeshService` has no transaction support. Rolling back the creation would require
  a second service call (`delete_category`) which could itself fail.
- The failure mode is transparent: the user sees the error and the created category is
  visible on the next `category list`. They can add the parent link manually via
  `category update <id> --parent-id Y` once the issue is resolved.
- Attempting a rollback on error would add significant complexity for an edge case.

**Alternatives considered**:
- Auto-rollback on failure — rejected: no transaction support; rollback could itself fail;
  adds complexity not justified by the frequency of this edge case.
- Atomic create+link in the service — rejected: out of scope for this spec; would require
  a new service method and a more complex CLI command signature.
