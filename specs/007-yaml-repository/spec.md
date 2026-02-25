# Feature Specification: YAML Repository

**Feature Branch**: `007-yaml-repository`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "Generate a YAMLRepository and use as the default repository (en vez de JsonRepository). Generate the YAMLRepository following the RepositoryBase protocol. Update README.md accordingly. Let in the repository an yaml file with mocked data to be used an example. The mock should have at least 5 top categories, with 2 or 3 child categories (some with 4 levels of categories) and each of them with 2 or 3 items."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Use YAML as the Default Storage Backend (Priority: P1)

A developer installs taxomesh and runs the CLI without any special configuration. The taxonomy data is now stored in a YAML file (`taxomesh.yaml`) instead of a JSON file (`taxomesh.json`). The developer can open the file with any text editor, read the data, hand-edit it if needed, and commit it to version control alongside their project. Note: this change applies to the CLI only; `TaxomeshService()` called directly from Python continues to default to `JsonRepository` (pass `YAMLRepository` explicitly to use YAML from the Python API).

**Why this priority**: This is the core deliverable — making YAML the default means every new user gets a human-readable file by default without needing any configuration change. All other stories depend on this one being complete.

**Independent Test**: Instantiate `YAMLRepository("taxomesh.yaml")`, call `save_category(...)` and `list_categories()`, verify the data round-trips correctly and a valid YAML file is produced on disk.

**Acceptance Scenarios**:

1. **Given** a fresh directory with no existing storage file, **When** `YAMLRepository` is initialised, **Then** a new `taxomesh.yaml` file is created on disk.
2. **Given** a `YAMLRepository` backed by an existing valid YAML file, **When** any read method is called, **Then** it returns the previously persisted data.
3. **Given** a `YAMLRepository`, **When** a mutating operation (save, delete) completes, **Then** the on-disk file reflects the change and is parseable YAML.
4. **Given** a `YAMLRepository`, **When** a write is interrupted mid-operation, **Then** the existing file is not corrupted (atomic write semantics).
5. **Given** a path pointing to an existing directory, **When** `YAMLRepository` is initialised with that path, **Then** a `TaxomeshRepositoryError` is raised.
6. **Given** a path to an existing file containing invalid YAML, **When** `YAMLRepository` is initialised, **Then** a `TaxomeshRepositoryError` is raised with a descriptive message.
7. **Given** a `YAMLRepository`, **When** `get_config_summary()` is called, **Then** it returns the configured file path as a non-empty string.

---

### User Story 2 — CLI Uses YAML as the Default (Priority: P2)

An end-user runs the `taxomesh` CLI commands (`category add`, `item add`, `graph`, etc.) without any `taxomesh.toml` configuration file. The CLI now persists data to `taxomesh.yaml` in the current directory. When the user provides a `taxomesh.toml` with `type = "yaml"`, the CLI correctly routes to the YAML backend. If the user explicitly configures `type = "json"`, the old JSON behaviour is preserved.

**Why this priority**: Without this story, the default CLI experience still uses JSON. This story makes the end-user-facing change visible.

**Independent Test**: Invoke the CLI via `CliRunner` without a config file; verify `taxomesh.yaml` is the configured path. Invoke with a TOML config specifying `type = "yaml"`; verify `YAMLRepository` is selected. Invoke with `type = "json"`; verify `JsonRepository` is still selected.

**Acceptance Scenarios**:

1. **Given** no `taxomesh.toml` present, **When** any CLI command is invoked, **Then** the storage path reported in verbose output is `taxomesh.yaml`.
2. **Given** a `taxomesh.toml` with `[repository] type = "yaml" path = "data.yaml"`, **When** any CLI command is invoked, **Then** `data.yaml` is used as the storage file.
3. **Given** a `taxomesh.toml` with `[repository] type = "json" path = "legacy.json"`, **When** any CLI command is invoked, **Then** `legacy.json` is used as before (backward-compatible).
4. **Given** a `taxomesh.toml` with `[repository] type = "unsupported"`, **When** any CLI command is invoked, **Then** a descriptive error is printed to stderr and the process exits with a non-zero code.

---

### User Story 3 — Example YAML Data File Ships with the Repository (Priority: P3)

A new developer clones or downloads taxomesh and wants to see what the data format looks like before creating their own taxonomy. An example YAML file is included in the repository demonstrating a rich, realistic taxonomy: at least 5 top-level categories, some with nested sub-categories reaching 4 levels deep, and 2–3 items in each category.

**Why this priority**: Developer-experience improvement. The library is fully functional without it. It also serves as a reference for correct YAML structure and a smoke-test fixture.

**Independent Test**: The example file is present at a documented path, parses without error, and when loaded by `YAMLRepository` produces a non-empty taxonomy (calling `get_graph()` returns a `TaxomeshGraph` with at least 5 roots and at least one 4-level-deep descendant chain).

**Acceptance Scenarios**:

1. **Given** the example YAML file on disk, **When** it is loaded by `YAMLRepository`, **Then** `list_categories()` returns at least 6 categories (root + 5 top-level).
2. **Given** the example YAML file loaded into `TaxomeshService`, **When** `get_graph()` is called, **Then** `TaxomeshGraph.roots` contains at least 5 nodes and at least one node has a 4-level-deep descendant.
3. **Given** the example YAML file, **When** inspected as raw text, **Then** it is valid YAML with human-readable category names and item identifiers.

---

### Edge Cases

- What happens when the YAML file exists but is completely empty? → Treat as an empty taxonomy; no error.
- What happens when only some top-level keys are present in the YAML file? → Missing keys are treated as empty collections; no error.
- What happens when the YAML file path refers to a directory? → `TaxomeshRepositoryError` is raised immediately.
- What happens when the YAML file path parent directory does not exist? → Parent directories are created automatically.
- What happens when a write fails partway through? → Atomic write (temp file + rename) prevents partial state on disk.
- What happens when a user upgrades and already has a `taxomesh.json` from a previous version? → The old `taxomesh.json` is left untouched and ignored. The CLI starts fresh with `taxomesh.yaml`. Users who wish to retain their existing JSON data may add `[repository] type = "json" path = "taxomesh.json"` to `taxomesh.toml`. No automatic migration is performed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `YAMLRepository` class that fully satisfies the `TaxomeshRepositoryBase` protocol — all 17 repository methods MUST be implemented with correct signatures.
- **FR-002**: The system MUST make `YAMLRepository` the default storage backend used by the CLI when no `taxomesh.toml` config file is present.
- **FR-003**: The default YAML storage file name MUST be `taxomesh.yaml` (replacing the previous default `taxomesh.json`).
- **FR-004**: `YAMLRepository` MUST perform atomic writes: data is written to a sibling temporary file and renamed into place so the target file is never in a partial state.
- **FR-005**: The CLI configuration loader MUST accept `type = "yaml"` in the `[repository]` section of `taxomesh.toml` and construct a `YAMLRepository` accordingly.
- **FR-006**: The CLI configuration loader MUST continue to accept `type = "json"` for backward compatibility with existing user configurations.
- **FR-007**: The system MUST raise `TaxomeshRepositoryError` when the YAML file path points to an existing directory.
- **FR-008**: The system MUST raise `TaxomeshRepositoryError` when the YAML file exists but cannot be parsed, including a message identifying the file and the nature of the failure.
- **FR-009**: The system MUST treat a completely empty YAML file as an empty taxonomy with no error.
- **FR-010**: `pyyaml` MUST be promoted from an optional dependency to a required runtime dependency in `pyproject.toml`.
- **FR-011**: An example YAML file with mocked taxonomy data MUST be included in the source repository at `examples/taxomesh_example.yaml`. It MUST NOT be shipped in the installed wheel. The mock MUST contain: at least 5 top-level categories, at least one category chain reaching 4 levels of depth, and 2–3 items per leaf or branch category (intermediate nodes without items are acceptable).
- **FR-012**: The README MUST be updated to reflect the new default storage format, `taxomesh.toml` YAML configuration, the location of the example file, and the `pyyaml` requirement.
- **FR-013**: The system MUST NOT automatically migrate existing `taxomesh.json` files to YAML. Any existing JSON file is silently ignored when the default YAML backend is active.

### Key Entities

- **YAMLRepository**: A storage adapter that reads and writes all taxomesh domain objects (categories, items, tags, and all link types) to a single YAML file on disk. Implements the same repository protocol as `JsonRepository`.
- **Example data file**: A standalone YAML file bundled in the repository demonstrating a realistic multi-level taxonomy with items. Intended for onboarding and documentation, not as a test fixture.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with no `taxomesh.toml` can run any `taxomesh` CLI command and observe that storage is routed to `taxomesh.yaml` — no configuration required.
- **SC-002**: The full test suite passes with `YAMLRepository` as the CLI default backend — all existing tests remain green after the change.
- **SC-003**: The example YAML file loads into `TaxomeshService` without error and produces a taxonomy graph with at least 5 top-level roots and at least one 4-level-deep descendant chain.
- **SC-004**: All four quality gates pass: lint, format check, strict type checking, and tests with ≥ 80% coverage.
- **SC-005**: A user with an existing `taxomesh.toml` containing `type = "json"` experiences no behaviour change after upgrading (backward compatibility preserved).

## Clarifications

### Session 2026-02-24

- Q: When a user who already has data in `taxomesh.json` upgrades, what should happen to their existing data? → A: Leave `taxomesh.json` untouched; start fresh with `taxomesh.yaml`. Users who want their old data configure `type = "json"` in `taxomesh.toml`. No automatic migration.
- Q: Should the example YAML file be bundled as installed package data or kept only in the source repository? → A: Source repository only — placed at `examples/taxomesh_example.yaml` in the repo root, not shipped in the wheel.

## Assumptions

- The YAML serialization format mirrors the JSON layout structurally: same top-level keys (`categories`, `items`, `tags`, `item_tag_links`, `category_parent_links`, `item_parent_links`), same UUID string keys, same Pydantic model serialization shapes. This makes the two backends interchangeable modulo file format.
- `pyyaml` `safe_dump` / `safe_load` are used (not bare `yaml.dump` / `yaml.load`) to prevent arbitrary object deserialization from untrusted files.
- No YAML-specific features (anchors, aliases, custom tags) are used in the output — plain YAML only, for maximum readability and portability.
- The example file is placed at `examples/taxomesh_example.yaml` in the repository root. It is not bundled in the installed wheel.
- Atomic write on YAML uses the same `tempfile.mkstemp` + `os.replace` pattern as `JsonRepository`.
