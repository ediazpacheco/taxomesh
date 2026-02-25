# Feature Specification: taxomesh.toml Configuration Template

**Feature Branch**: `008-toml-config-template`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "add a taxomesh.toml config file. With examples and basic documentation about their settings. update README.md adding taxomesh.toml existence (not much info in the README.md because the details of the config should be in the taxomesh.toml itself)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Developer Discovers and Uses the Config Template (Priority: P1)

A developer wants to customise how taxomesh stores its taxonomy (e.g., use a different file path, or switch from YAML to JSON). They look for a configuration reference and find `taxomesh.toml.example` at the root of the repository. They copy it to their project as `taxomesh.toml`, uncomment the settings they need, and the CLI immediately respects those values. Every setting in the template is self-explanatory through inline comments — the developer never needs to open external documentation.

**Why this priority**: This is the core deliverable. Without a self-documenting template, users must read source code or prior feature specs to understand what settings are accepted. The template closes this gap entirely and is independently useful without any README change.

**Independent Test**: Open `taxomesh.toml.example` and verify it contains every supported `[repository]` key with comments explaining accepted values and defaults. Copy it to a temp directory as `taxomesh.toml`, change the `path` value, run a CLI command, and observe the CLI uses the new path.

**Acceptance Scenarios**:

1. **Given** the repository root, **When** a developer looks for a configuration reference, **Then** a file named `taxomesh.toml.example` exists at the root alongside `README.md`.
2. **Given** the template file, **When** a developer reads it, **Then** a header comment block explains what the file is, that it is optional, and how to activate it (copy to the project root as `taxomesh.toml`).
3. **Given** the template file, **When** a developer reads it, **Then** every supported key in the `[repository]` section (`type`, `path`) is present with an inline comment explaining its purpose, accepted values, and default.
4. **Given** the template file, **When** a developer reads it, **Then** at least one complete, working example is present for each supported backend (`yaml`, `json`).
5. **Given** a developer has copied the template to their project root as `taxomesh.toml` and set a custom `path`, **When** they run any CLI command, **Then** the CLI uses that custom path.

---

### User Story 2 — README Points to the Config Template (Priority: P2)

A developer skimming the README encounters the CLI configuration section and sees the existing TOML examples. They also notice a new sentence pointing to `taxomesh.toml.example` for the complete, up-to-date reference. The existing README content is preserved; only a pointer is added.

**Why this priority**: Secondary to the template itself. Developers who find the template directly get everything they need. The README update is additive — a single pointer sentence that improves discoverability without disrupting existing content.

**Independent Test**: Open `README.md` and verify the CLI/configuration section contains a new sentence referencing `taxomesh.toml.example`. Confirm existing TOML code blocks are unchanged.

**Acceptance Scenarios**:

1. **Given** the README, **When** a developer reads the CLI section, **Then** they see a new sentence pointing to `taxomesh.toml.example` for the full, authoritative setting reference.
2. **Given** the README, **When** a developer reads it, **Then** the existing TOML configuration code blocks are unchanged — the update is additive only.

---

### User Story 3 — Python API Users Configure via taxomesh.toml (Priority: P3)

A Python API user wants `TaxomeshService` to automatically pick up `taxomesh.toml` without having to
construct repositories manually. They place a `taxomesh.toml` in their project root and instantiate
`TaxomeshService()` — the service reads the file and configures the correct backend. Advanced users
can also pass an explicit `config_path` or bypass config entirely by supplying a `repository`.

**Why this priority**: Extends the config system from CLI-only to the full Python API surface.
Users who rely solely on the API should not need to import and construct repository adapters manually
just to change a storage path.

**Acceptance Scenarios**:

1. `TaxomeshService()` auto-discovers `taxomesh.toml` from CWD when present.
2. `TaxomeshService(config_path=...)` reads an explicit file.
3. `TaxomeshService(repository=repo)` bypasses config entirely.
4. Invalid TOML raises `TaxomeshConfigError`.
5. Unsupported `type` raises `TaxomeshConfigError`.
6. No config file → `TaxomeshService()` starts successfully using its default repository backend.

---

### Edge Cases

- What if a user's `taxomesh.toml` contains unknown section or key names? → Silently ignored at all verbosity levels in this spec. `taxomesh.toml` is a library-level config read by `TaxomeshService`, not a CLI-only artefact; any future unknown-key diagnostic belongs in the service layer, not the CLI `--verbose` output. Deferred to a future spec.
- What if `taxomesh.toml.example` were named `taxomesh.toml` and committed to the repo root? → The CLI would pick it up when run from the repo root, potentially interfering with library development. The `.example` suffix avoids this.
- What if a future feature adds new `taxomesh.toml` settings? → `taxomesh.toml.example` will be updated in that feature's spec cycle. This spec covers only the currently supported `[repository]` section.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A file named `taxomesh.toml.example` MUST exist at the repository root (same level as `README.md`).
- **FR-002**: The template MUST include a header comment block stating: what the file is, that the CLI works without it (all settings have defaults), and how to use it (copy to the project root as `taxomesh.toml`).
- **FR-003**: The template MUST document the `[repository]` section with all currently supported keys: `type` (accepted values: `"yaml"`, `"json"`; default: `"yaml"`) and `path` (the storage file path; relative paths are resolved from CWD at `TaxomeshService()` construction time; default: `"data/taxomesh.yaml"` for `type = "yaml"`, `"data/taxomesh.json"` for `type = "json"`).
- **FR-004**: Every key in the template MUST be accompanied by an inline comment explaining its purpose, all accepted values, and its default value.
- **FR-005**: The template MUST include a complete, uncommented working example using the YAML backend, and a fully commented-out alternative block showing the JSON backend.
- **FR-006**: The README MUST be updated to mention `taxomesh.toml` and point to `taxomesh.toml.example`, within a top-level `## Configuration` section.
- **FR-007**: The README `## Configuration` section MUST NOT duplicate config key details — those belong in `taxomesh.toml.example` exclusively.
- **FR-008**: `TaxomeshService.__init__` MUST accept `config_path: Path | str | None = None` as a keyword-only parameter.
- **FR-009**: When `repository` is `None` and a config file exists (at `config_path` or auto-discovered from CWD), the service MUST read it to construct the repository.
- **FR-010**: When `repository` is explicitly provided, `config_path` is ignored entirely.
- **FR-011**: A `TaxomeshConfigError` MUST be raised for: invalid TOML syntax, unsupported `type` values, and OS-level read errors (e.g. `PermissionError`). The original exception MUST be chained (`raise TaxomeshConfigError(...) from exc`) so the underlying cause is visible in tracebacks.
- **FR-012**: `TaxomeshService` MUST expose a `repository` property returning the active backend.
- **FR-013**: The README config docs MUST be in a top-level `## Configuration` section, not under `## CLI`.
- **FR-014**: Default storage file paths MUST be defined as named module-level `Final[...]` constants in `UPPER_CASE` (e.g. `DEFAULT_YAML_PATH`, `DEFAULT_JSON_PATH`) inside each repository adapter module, not as inline string literals. The application layer (`service.py`) MUST NOT define or replicate these defaults; it MUST call repository constructors with no explicit path argument when no path is configured, delegating the default entirely to the adapter.

### Key Entities

- **`taxomesh.toml.example`**: A ready-to-copy TOML template file at the repository root. Self-documenting via inline comments. Not shipped in the installed wheel.
- **`TaxomeshConfigError`**: New exception raised when `taxomesh.toml` cannot be parsed or specifies an unsupported option.
- **`TaxomeshService.repository`**: New property exposing the active backend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can copy `taxomesh.toml.example`, rename it to `taxomesh.toml`, uncomment one setting, and have the CLI respect it — without reading any documentation other than the file itself.
- **SC-002**: The template documents 100% of currently supported `taxomesh.toml` keys (both keys in the `[repository]` section: `type` and `path`).
- **SC-003**: The README has a top-level `## Configuration` section pointing to `taxomesh.toml.example`.
- **SC-004**: All quality gates pass (lint, format, type-check, tests ≥ 80% coverage).
- **SC-005**: `TaxomeshService(config_path=path_to_toml_example)` produces a `YAMLRepository` instance.

## Clarifications

### Session 2026-02-24

- Q: When `path` in `taxomesh.toml` is a relative path, what is it relative to? → A: CWD at `TaxomeshService()` construction time.
- Q: Should OS-level read errors (e.g. `PermissionError`) on the config file be wrapped in `TaxomeshConfigError` or propagate as raw `OSError`? → A: Wrap in `TaxomeshConfigError` with the original exception chained (`from exc`).
- Q: Should FR-003 document type-specific `path` defaults (`"taxomesh.yaml"` for yaml, `"taxomesh.json"` for json) rather than a single universal default? → A: Yes — document type-specific defaults.
- Q: Should `taxomesh.toml` include a format version field for forward-compatibility? → A: No — no version field now; add in a future spec when a breaking config change is actually planned.
- Q: Should `--verbose` mode surface a warning for unrecognised keys in `taxomesh.toml`? → A: No — unknown keys are silently ignored at all verbosity levels. `taxomesh.toml` is a library-level config (not CLI-only); any future unknown-key diagnostic belongs in `TaxomeshService`, not the CLI adapter. Out of scope for this spec.
- Q: How should US3 scenario 6 express the no-config-file fallback? → A: As a config-system behaviour only — "no config file found → `TaxomeshService()` starts successfully using its default repository backend." The service is agnostic about repositories; which backend is used is an adapter detail not visible at the service config spec level.

## Assumptions

- Currently supported settings are limited to `[repository] type` and `[repository] path`. No other sections or keys are in scope for this feature.
- No format version key (`format_version`) will be added to `taxomesh.toml` in this feature. Format versioning is explicitly deferred to the spec in which a breaking config change is first introduced.
- The `--config` CLI flag (to override the config file location at invocation time) does not require documentation inside the template — it is a CLI flag, not a TOML setting.
- `taxomesh.toml.example` is placed at the repository root. It is not bundled in the installed wheel, consistent with the `examples/` content policy (no `pyproject.toml` changes needed).
