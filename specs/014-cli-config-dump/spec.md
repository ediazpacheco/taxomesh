# Feature Specification: CLI Config Dump — Display Effective Configuration

**Feature Branch**: `014-cli-config-dump`
**Created**: 2026-02-28
**Status**: Implemented
**Input**: User description: "the `taxomesh --config` should display current config being used. In the same toml format for current config (with the defaults applied) to allow to pipe the output for taxomesh.toml and then can change settings. All the available config settings (with their defaults) should be in the output with a comment in the above line with an explain of the settings. Add all the settings configuration settings name should be in a constant as a list."

## Overview

When a user invokes a dedicated CLI trigger, taxomesh prints the current
**effective configuration** in valid TOML format and exits. The output reflects
every supported setting — not just the ones present in the active config file —
with defaults substituted for any unset key. Each setting is preceded by a
comment block that explains the key, its accepted values, and its default.
The output is designed to be piped directly into `taxomesh.toml` to bootstrap or
document a project's configuration. All recognised configuration setting key
names are centralised in a single named constant so they have one authoritative
source of truth.

## Clarifications

### Session 2026-02-28

- Q: The existing CLI already uses `--config <PATH>` as an option to specify
  which TOML file to load. How should the new "show config" trigger be exposed
  without conflicting with that option? → A: New boolean flag `--show-config`.
  No breaking change; combines cleanly with `--config <PATH>`:
  `taxomesh --show-config` or `taxomesh --config file.toml --show-config`.
- Q: Should `--show-config` avoid full service initialisation (which would create
  `data/taxomesh.yaml` and the root category if they don't exist)? → A: Yes —
  `--show-config` MUST only read and parse the TOML config file; it MUST NOT
  trigger `TaxomeshService.__init__()` or any repository I/O. No data files
  are created as a side effect of running `--show-config`.

## User Scenarios & Testing

### User Story 1 — Bootstrap a config file from defaults (Priority: P1)

A developer is setting up taxomesh for the first time and wants to understand
every available setting and its default value. They run a single command and
redirect the output to `taxomesh.toml`. The resulting file is a complete,
valid, annotated configuration ready to edit.

**Why this priority**: This is the core value of the feature: eliminating the
need to consult documentation or copy an example file. Every other story builds
on this output format.

**CLI trigger**: New boolean flag `--show-config` (no breaking change).
Examples: `taxomesh --show-config` or `taxomesh --config taxomesh.toml --show-config`.

**Independent Test**: Run the trigger with no `taxomesh.toml` present; assert
the output is valid TOML containing all settings at their default values with
comment lines above each key.

**Acceptance Scenarios**:

1. **Given** no `taxomesh.toml` exists, **When** the config dump trigger is
   invoked, **Then** the output contains all settings at their default values
   in valid TOML format.
2. **Given** the output is redirected to `taxomesh.toml`, **When** any
   taxomesh CLI command is run, **Then** the command behaves identically to
   running without any config file (defaults produce identical behaviour).
3. **Given** the output is displayed, **Then** each setting has a comment line
   immediately above it explaining the key name, accepted values, and its
   default value.
4. **Given** the output is displayed, **Then** the TOML is parseable by a
   standard TOML parser without errors.

---

### User Story 2 — Inspect the effective config with a partial config file (Priority: P1)

A developer has a `taxomesh.toml` that overrides only some settings. They want
to confirm exactly which values taxomesh is using — including defaults for
every key they did not set.

**Why this priority**: Debugging config drift is as important as bootstrapping.
The output must show the merged result, not just what is in the file.

**Independent Test**: Create a `taxomesh.toml` with only `type = "json"` set;
invoke the trigger; assert the output shows `type = "json"` and `path` at the
JSON default (`"data/taxomesh.json"`), not the YAML default.

**Acceptance Scenarios**:

1. **Given** a `taxomesh.toml` sets `[repository] type = "json"` but not
   `path`, **When** the config dump trigger is invoked, **Then** the output
   shows `type = "json"` and `path = "data/taxomesh.json"` (the JSON default).
2. **Given** a `taxomesh.toml` sets only `path`, **When** the config dump
   trigger is invoked, **Then** the output shows the overridden `path` value
   and `type` at its default (`"yaml"`).
3. **Given** the trigger is combined with `--config <PATH>` pointing to a
   specific TOML file, **When** invoked, **Then** the output reflects the
   effective config for that specific file, not the auto-discovered one.

---

### User Story 3 — All setting names centralised in a constant (Priority: P2)

A developer reading or extending the codebase finds all supported configuration
key names in a single named constant. No key name appears as a bare string
literal in the config-dump business logic; all references go through that
constant.

**Why this priority**: This is a maintainability constraint (constitution
Principle X — Named Constants). It does not affect end-user behaviour but is
required for quality gate compliance.

**Independent Test**: Locate the constant in the source; assert it contains
every key name that appears in the dump output; assert no bare string literals
for config key names appear in the config-dump logic itself.

**Acceptance Scenarios**:

1. **Given** the constant is defined, **Then** it contains exactly the set of
   config key names that the dump output includes — no more, no less.
2. **Given** a new config setting is added in a future spec, **Then** adding it
   to the constant is sufficient to include it in the dump output and in any
   validation or introspection logic.

---

### Edge Cases

- What happens when `taxomesh.toml` exists but is empty? → The dump shows all
  settings at their defaults (same as if no file existed).
- What happens when `taxomesh.toml` is malformed TOML? → A user-readable error
  is emitted to stderr and the process exits with a non-zero code. No partial
  TOML output is written to stdout.
- What if `--config <PATH>` points to a non-existent file? → All defaults are
  shown (consistent with how the service already handles a missing explicit
  config path).
- What if the config dump trigger is combined with a subcommand (e.g.
  `taxomesh --show-config category list`)? → The dump is shown and the process
  exits; the subcommand is not executed. Config dump is always a terminal action.
- What does the path default in the output look like when `type` has been
  overridden to `"json"` but `path` is unset? → The output shows the JSON
  backend's default path (`"data/taxomesh.json"`), not the YAML default.

## Requirements

### Functional Requirements

- **FR-001**: The CLI MUST expose a new boolean flag `--show-config` that,
  when present, prints the effective configuration to stdout in TOML format
  and exits with code 0. No other command output is emitted to stdout.
- **FR-002**: The output MUST include every supported configuration setting,
  including those absent from the active config file, with built-in defaults
  applied for any unset key.
- **FR-003**: Each setting in the output MUST be immediately preceded by a
  comment block stating: (a) what the setting controls, (b) all accepted
  values, and (c) the default value.
- **FR-004**: The output MUST be valid TOML, parseable by a standard TOML
  library, so it can be redirected directly to `taxomesh.toml`.
- **FR-005**: When a config file is active (auto-discovered or via
  `--config <PATH>`), the output MUST reflect merged effective values: file
  values take precedence; defaults fill in all missing keys.
- **FR-006**: All recognised configuration setting key names MUST be enumerated
  in a single named constant at module level. No config key name may appear as
  a bare string literal in the config-dump logic (``dump_config()`` and
  ``_resolve_effective_config()`` in ``taxomesh/adapters/cli/config.py``).
- **FR-007**: The config dump trigger MUST be a terminal action: when it is
  present, the effective configuration is printed and the process exits.
  Any subcommand present on the same invocation is ignored.
- **FR-008**: If the active config file is syntactically invalid, the command
  MUST emit a user-readable error message to stderr and exit with a non-zero
  code. No partial TOML output is written to stdout.
- **FR-009**: The `--show-config` flag MUST NOT conflict with the existing
  `--config <PATH>` option. Both flags MAY be combined in a single invocation;
  when `--show-config` is present, the effective config for the path given by
  `--config` (or the auto-discovered default) is what gets printed.
  *(Note: FR-010 merged into this requirement — 2026-03-01)*
- **FR-011**: `--show-config` MUST NOT trigger full service initialisation.
  It MUST only read the TOML config file (if present) to resolve effective
  values. No repository is constructed, no data directory is created, and
  no root category is written as a side effect of this command.

### Key Entities

- **Effective Configuration**: The merged set of all supported settings,
  combining values from the active TOML file (if any) with built-in defaults
  for every absent key. Always covers every supported setting, never just the
  subset present in the file.
- **Config Setting**: A single TOML key with a name, a type, a default value,
  a set of accepted values, and a human-readable description. Each setting is
  an entry in the named constant (FR-006).
- **Config Dump Output**: The TOML-formatted string produced by the trigger.
  Consists of section headers, comment blocks, and key-value pairs covering
  all settings. Written to stdout; errors written to stderr.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A developer can pipe the config dump output directly into
  `taxomesh.toml` and run any taxomesh command without error or behaviour
  change — verifiable in an automated test.
- **SC-002**: Every supported configuration setting appears in the dump output
  even when no config file is present on disk.
- **SC-003**: Every setting in the output is immediately preceded by a comment
  explaining its purpose, accepted values, and default.
- **SC-004**: All config key names are defined in exactly one named constant;
  zero bare string literals for those key names appear in the config-dump
  business logic.
- **SC-005**: All quality gates pass with no regressions: linting, formatting,
  strict type checking, and test coverage ≥ 80%.

## Assumptions

- The only supported TOML settings at the time of this spec are
  `[repository] type` and `[repository] path`. Future specs that add new
  settings must also add them to the named constant and to the dump template.
- The path default is backend-dependent: `"data/taxomesh.yaml"` when
  `type = "yaml"` and `"data/taxomesh.json"` when `type = "json"`. The dump
  output shows the default appropriate for the effective `type` value.
- The config dump trigger MUST NOT trigger full service initialisation. It
  reads only the TOML config file (if present) to resolve effective values;
  no repository is constructed and no data files are created (see FR-011).
- stdout is used for TOML output so shell redirection (`> taxomesh.toml`) works
  naturally. Error messages go to stderr so they do not corrupt redirected
  output.
- `--show-config` is the resolved flag name (Option A, chosen 2026-02-28).
