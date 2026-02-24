# Feature Specification: CLI Verbose Mode & List Enhancements

**Feature Branch**: `005-cli-verbose`
**Created**: 2026-02-23
**Status**: Draft
**Input**: Improve CLI: add `--verbose` boolean flag with repository info display; add header/footer to list commands; add repository configuration method to `TaxomeshRepositoryBase`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Inspect active repository at startup with `--verbose` (Priority: P1)

A developer is troubleshooting why a CLI command is reading from an unexpected file.
They append `--verbose` to any taxomesh command and immediately see which repository
backend is in use and its configuration details (e.g., the JSON file path) before
any command output appears.

**Why this priority**: Knowing which repository is active is critical for debugging
misconfigured or default file paths. This is the highest-impact user-facing improvement.

**Independent Test**: Can be fully tested by invoking `taxomesh --verbose category list`
via Typer's `CliRunner` and asserting that repository information appears before
category records in stdout.

**Acceptance Scenarios**:

1. **Given** a valid `taxomesh.toml` pointing to `custom.json`, **When** the developer
   runs `taxomesh --verbose category list`, **Then** the first line(s) of stdout contain
   the repository type name, the resolved path to `custom.json`, and the path to the
   config file in use (`taxomesh.toml` or the `--config` path), before any category records.
2. **Given** no `taxomesh.toml` exists (defaults apply), **When** the developer runs
   `taxomesh --verbose tag list`, **Then** stdout begins with repository type, the
   default path (`taxomesh.json`), and the default config file path (`taxomesh.toml`)
   with a clear indication that the file does not exist, before any tag records.
3. **Given** the developer runs `taxomesh category list` (no `--verbose`), **Then** no
   repository info is printed; output is identical to current behavior.

---

### User Story 2 — List commands show structured header and record count footer (Priority: P1)

A developer runs `taxomesh category list` and wants at a glance to know how many
records were returned, without counting lines manually. Every list command now prints
a descriptive header before the records and a footer with the total count after.
This behavior is always active, regardless of verbosity level.

**Why this priority**: Improves usability for all users of list commands without
requiring any flag — zero configuration change needed.

**Independent Test**: Can be fully tested by invoking any `list` sub-command via
Typer's `CliRunner` and asserting that a header line appears before the first record
and a footer line appears after the last record, both containing a meaningful label
and count.

**Acceptance Scenarios**:

1. **Given** three categories exist, **When** the developer runs `taxomesh category list`,
   **Then** stdout contains a header before the records and a footer after all records
   that reports a total of 3.
2. **Given** no categories exist, **When** the developer runs `taxomesh category list`,
   **Then** stdout contains a header and a footer reporting 0 records.
3. **Given** two items exist, **When** the developer runs `taxomesh item list`,
   **Then** stdout contains a header and a footer reporting a total of 2.
4. **Given** five tags exist, **When** the developer runs `taxomesh tag list`,
   **Then** stdout contains a header and a footer reporting a total of 5.
5. **Given** a category has two child items and `taxomesh item list --category-id <id>` is run,
   **Then** the footer reports 2, not the total item count.

---

### User Story 3 — Repository exposes its own configuration for programmatic introspection (Priority: P2)

A developer building a plugin or diagnostic tool on top of taxomesh needs to
programmatically discover how a repository is configured at runtime. They call the
new configuration method on any repository instance and receive a human-readable
string describing its configuration (e.g., the file path for `JsonRepository`,
or a connection string for a future database repository). This is also what the
CLI uses internally to display configuration in verbose mode.

**Why this priority**: This is a prerequisite capability for User Story 1's config
display, and provides standalone value for programmatic introspection.

**Independent Test**: Can be fully tested by constructing a `JsonRepository` instance
and asserting that the new method returns a non-empty string containing the configured
file path.

**Acceptance Scenarios**:

1. **Given** a `JsonRepository` configured with path `/data/taxonomy.json`, **When** the
   new method is called, **Then** the returned string contains `/data/taxonomy.json`.
2. **Given** a `JsonRepository` configured with the default path `taxomesh.json`, **When**
   the new method is called, **Then** the returned string contains `taxomesh.json`.
3. **Given** any repository that satisfies `TaxomeshRepositoryBase`, **When** the method
   is called, **Then** it returns a non-empty string (never raises, never returns empty).

---

### Edge Cases

- `--verbose` is a global option on the root command; it applies to all sub-commands.
- List commands with `--parent-id` or `--category-id` filters: the footer count reflects
  the filtered result count, not the total unfiltered count.
- A list command that raises an error (e.g., invalid `--category-id`): the verbose block
  (repo type, config, config file path) IS still printed to stdout if `--verbose` is active
  — it appears before the error. No footer is printed. The error is reported to stderr and
  the process exits non-zero as currently.
- Verbose output (repository info) is printed to stdout, not stderr.

---

## Requirements *(mandatory)*

### Functional Requirements

**Verbose flag:**
- **FR-001**: The root `taxomesh` command MUST accept a `--verbose` boolean flag. When
  present, verbose mode is enabled. When omitted, verbose mode is disabled (output is
  identical to running without the flag).
- **FR-005**: The verbose state MUST be threaded through the Typer context (`ctx.obj`) so
  that all sub-commands can access it without re-parsing.

**Verbose output — repository info:**
- **FR-006**: When `--verbose` is active, the CLI MUST print the repository type and its
  configuration string to stdout BEFORE any command output is produced. This output MUST
  appear unconditionally — regardless of whether the subsequent command succeeds or fails.
- **FR-007**: The repository type label MUST be the class name of the active repository
  (e.g., `JsonRepository`).
- **FR-008**: The configuration string displayed MUST be obtained by calling the new
  repository configuration method (see FR-011).
- **FR-015**: When `--verbose` is active, the CLI MUST also print the path of the active
  configuration file — either the default `taxomesh.toml` in the current working directory,
  or the path supplied via `--config`. If no file exists at that path, the output MUST
  indicate this clearly (e.g., "[not found]"), so the user understands they can create
  the file there to customise the repository backend.

**List command headers and footers:**
- **FR-009**: Every `list` sub-command (`category list`, `item list`, `tag list`) MUST print
  a header line to stdout before the first record.
- **FR-010**: Every `list` sub-command MUST print a footer line to stdout after the last
  record. The footer MUST include the total count of records returned. The count MUST
  reflect the actual number of records printed (i.e., after any filtering).

**Repository configuration method:**
- **FR-011**: `TaxomeshRepositoryBase` MUST be extended with a new method (the 19th protocol
  method) that returns a human-readable string describing the repository's configuration.
  The method MUST return a non-empty string and MUST NOT raise. The returned string MUST
  NOT contain secrets, credentials, or passwords; implementations are contractually required
  to sanitize or omit sensitive values.
- **FR-012**: `JsonRepository` MUST implement this method by returning a string that includes
  the as-configured path of the JSON storage file.

**Tests:**
- **FR-013**: `tests/test_cli.py` MUST be extended to cover: verbose output appearing before
  command output, absent `--verbose` producing no extra output, `--verbose` flag producing
  verbose output, config file path present in verbose output (existing and non-existing file),
  header/footer present on all three list commands, footer count accuracy (including filtered
  results), and the new repository method returning the expected string.

### Key Entities

- **`TaxomeshRepositoryBase`** (modified): gains one new Protocol method returning a
  configuration string.
- **`JsonRepository`** (modified): implements the new configuration method.
- **`taxomesh/adapters/cli/main.py`** (modified): adds `--verbose` to root callback;
  threads verbosity through context; prints repo info when verbose ≥ 1; adds headers and
  footers to all three `list` commands.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `taxomesh --verbose category list` produces repository type, repository
  configuration, and config file path on the first output line(s), before any category
  records, and exits 0.
- **SC-001b**: When no `taxomesh.toml` exists, `taxomesh --verbose tag list` shows the
  default config file path with a "not found" indicator in the verbose header.
- **SC-003**: `taxomesh category list` (three categories exist) produces a header line,
  three record lines, and a footer reporting `3`, then exits 0.
- **SC-004**: `taxomesh item list` (zero items) produces a header, zero record lines, and
  a footer reporting `0`, then exits 0.
- **SC-005**: `taxomesh tag list` (two tags) produces a header, two record lines, and a
  footer reporting `2`, then exits 0.
- **SC-006**: Calling the new repository configuration method on a `JsonRepository`
  returns a string containing the configured file path.
- **SC-007**: All quality gates pass: `ruff check`, `ruff format --check`, `mypy --strict`,
  `pytest --cov=taxomesh --cov-fail-under=80`.

---

## Assumptions

- Header/footer output applies to all list commands unconditionally (not gated on verbose).
- Verbose output (repository info) is printed to stdout. If a command writes to stderr
  for errors, that behavior is unchanged.
- `--verbose` is a boolean flag (present/absent). No integer values are accepted.
- The new repository configuration method returns a plain string. No structured data
  (dict, dataclass) is returned. Formatting is left to each implementation.
- The `--verbose` flag is a global option on the root `app` callback, not repeated on
  each sub-command.
- The exact format of the header, footer, and verbose prefix lines (labels, separators)
  is a planning-phase design decision; the spec only requires their presence and the
  count accuracy of the footer.
- The verbose state (`bool`) is passed via `ctx.obj` alongside the config path.
- No changes are made to non-list commands (add, update, delete) output format.
- Existing tests in `tests/test_cli.py` that assert exact output strings may need
  updating to account for the new header/footer lines in list commands.

---

## Clarifications

### Session 2026-02-23

- Q: Should verbose output include the config file path, even when using the default and/or when the file does not exist? → A: Yes; always show the config file path in verbose mode; indicate clearly when the file does not exist, as a hint to the user that it can be created there.
- Q: When verbose mode is active and a command fails, is the verbose block (repo type, config, config file path) still printed? → A: Yes; always print the verbose block unconditionally at startup, before command execution, regardless of success or failure.
- Q: Should the repository configuration method's return value be contractually forbidden from containing secrets or credentials? → A: Yes; the protocol contract explicitly requires sanitized output — no passwords or credentials may appear in the returned string.
