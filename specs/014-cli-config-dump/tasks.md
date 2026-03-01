# Tasks: CLI Config Dump — Display Effective Configuration

**Input**: Design documents from `/specs/014-cli-config-dump/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cli.md ✅

**TDD**: All implementation tasks are preceded by a failing-test task per project constitution.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-progress tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Each file path is absolute from project root

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: `CONFIG_KEYS` constant and `dump_config()` pure function are shared by all
user stories. Both must be in place before any story's `--show-config` behaviour can be
implemented or tested end-to-end.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write first — must FAIL before T002/T003)

- [ ] T001 Write failing unit tests for `CONFIG_KEYS` shape and `dump_config()` behaviour in `tests/adapters/cli/test_config_dump.py`. Tests to include:
  - `test_config_keys_is_list_of_dotted_path_strings` — assert `CONFIG_KEYS` is a `list[str]` where every element matches `"<section>.<key>"` format
  - `test_dump_config_yaml_defaults_is_valid_toml` — `dump_config("yaml", "data/taxomesh.yaml")` → `tomllib.loads()` succeeds without error
  - `test_dump_config_json_defaults_is_valid_toml` — `dump_config("json", "data/taxomesh.json")` → `tomllib.loads()` succeeds
  - `test_dump_config_reflects_provided_type_and_path` — output contains the exact `repo_type` and `repo_path` values passed in
  - `test_dump_config_each_key_has_comment_above` — for every TOML key in the output there is a `#`-prefixed comment line immediately above it
  - `test_dump_config_contains_all_config_keys_entries` — every dotted-path in `CONFIG_KEYS` corresponds to a key present in the parsed TOML output

### Implementation

- [ ] T002 Add the following constants:
  - `YAML_REPO_TYPE: Final[str] = "yaml"` to `taxomesh/adapters/repositories/yaml_repository.py`
  - `JSON_REPO_TYPE: Final[str] = "json"` to `taxomesh/adapters/repositories/json_repository.py`
  - `CONFIG_KEYS: Final[list[str]] = ["repository.type", "repository.path"]` to `taxomesh/adapters/cli/config.py`
  - Import `Final` from `typing` where not already imported. Import `YAML_REPO_TYPE`/`JSON_REPO_TYPE` into `config.py` from their respective modules.

- [ ] T003 Implement `dump_config(repo_type: str, repo_path: str) -> str` in `taxomesh/adapters/cli/config.py`. Function must:
  - Return a valid TOML string (parseable by `tomllib.loads()`)
  - Include a header comment block explaining the output and `--show-config > taxomesh.toml` usage
  - Include `[repository]` section header
  - Precede each key with a multi-line comment stating: (a) what it controls, (b) accepted values, (c) default value
  - Emit `type = "<repo_type>"` and `path = "<repo_path>"` as key-value pairs
  - Reference `CONFIG_KEYS` (no bare string literals for key names in the function body)
  - Terminate output with a trailing newline

- [ ] T004 Run `pytest tests/adapters/cli/test_config_dump.py` — confirm all T001 tests pass; fix any issues before proceeding to Phase 2

**Checkpoint**: `CONFIG_KEYS` and `dump_config()` work correctly in isolation.

---

## Phase 2: User Story 1 — Bootstrap Config from Defaults (Priority: P1) 🎯 MVP

**Goal**: `taxomesh --show-config` with no `taxomesh.toml` present prints all settings
at their defaults in valid, annotated TOML format and exits 0. Output can be redirected
to create a working `taxomesh.toml`.

**Independent Test**: Run `taxomesh --show-config` in a temp directory with no
`taxomesh.toml`; assert stdout contains `type = "yaml"`, `path = "data/taxomesh.yaml"`,
is parseable by `tomllib`, and exit code is 0.

### Tests for User Story 1 (write first — must FAIL before T006/T007)

- [ ] T005 [US1] Write failing CLI integration tests for the default-config scenario in `tests/adapters/cli/test_config_dump.py`. Use `typer.testing.CliRunner`. Tests to include:
  - `test_show_config_no_config_file_contains_yaml_defaults` — invoke with `["--show-config"]` in a tmp dir with no toml; assert `'type = "yaml"'` and `'path = "data/taxomesh.yaml"'` in stdout
  - `test_show_config_exit_code_zero` — assert `result.exit_code == 0`
  - `test_show_config_stdout_is_valid_toml` — `tomllib.loads(result.stdout)` succeeds
  - `test_show_config_no_stderr_on_success` — assert `result.stderr` (or captured stderr) is empty
  - `test_show_config_exits_before_subcommand` — invoke with `["--show-config", "category", "list"]`; assert exit code 0 and output does NOT contain category listing (only TOML config)

### Implementation for User Story 1

- [ ] T006 [US1] Implement `_resolve_effective_config(config_path: Path | None) -> tuple[str, str]` in `taxomesh/adapters/cli/config.py`. Function must:
  - If `config_path` is `None`, auto-discover `Path.cwd() / "taxomesh.toml"`
  - If the resolved path does not exist: return `("yaml", str(DEFAULT_YAML_PATH))` — import `DEFAULT_YAML_PATH` from `taxomesh.adapters.repositories.yaml_repository`
  - If the file exists: parse with `tomllib`; read `config.get("repository", {})`:
    - `repo_type = section.get("type", "yaml")`
    - If `repo_type == "yaml"` and `"path"` absent → `repo_path = str(DEFAULT_YAML_PATH)`
    - If `repo_type == "json"` and `"path"` absent → `repo_path = str(DEFAULT_JSON_PATH)` — import `DEFAULT_JSON_PATH` from `taxomesh.adapters.repositories.json_repository`
    - If `"path"` present → `repo_path = section["path"]`
  - Raise `TaxomeshConfigError` on `tomllib.TOMLDecodeError` or `OSError`
  - Return `(repo_type, repo_path)` as `tuple[str, str]`

- [ ] T007 [US1] Add `--show-config` boolean flag to `main()` callback in `taxomesh/adapters/cli/main.py`. Changes:
  - Change `@app.callback()` to `@app.callback(invoke_without_command=True)` so the flag can exit without a subcommand being required
  - Add `show_config: bool = typer.Option(False, "--show-config", help="Print effective configuration in TOML format and exit.")` parameter to `main()` signature
  - After storing existing options in `ctx.obj`, add early-exit block:
    ```
    if show_config:
        try:
            repo_type, repo_path = _resolve_effective_config(config)
            typer.echo(dump_config(repo_type, repo_path), nl=False)
            raise typer.Exit()
        except TaxomeshConfigError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1)
    ```
  - Import `_resolve_effective_config`, `dump_config` from `taxomesh.adapters.cli.config`
  - Import `TaxomeshConfigError` from `taxomesh.exceptions`

- [ ] T008 [US1] Run `pytest tests/adapters/cli/test_config_dump.py` — confirm all T005 tests pass; fix any issues before proceeding

**Checkpoint**: `taxomesh --show-config` works end-to-end for the all-defaults case.

---

## Phase 3: User Story 2 — Inspect Effective Config with Partial File (Priority: P1)

**Goal**: `taxomesh --show-config` with a `taxomesh.toml` that overrides only some keys
shows the merged result — active file values plus defaults for all missing keys.

**Independent Test**: Create a `taxomesh.toml` with only `[repository]\ntype = "json"`;
invoke `--show-config`; assert output shows `type = "json"` and `path = "data/taxomesh.json"`
(JSON default, not YAML default).

### Tests for User Story 2 (write first — must FAIL before running)

- [ ] T009 [US2] Write failing CLI integration tests for the partial-config and error scenarios in `tests/adapters/cli/test_config_dump.py`. Tests to include:
  - `test_show_config_json_type_uses_json_default_path` — toml with `[repository]\ntype = "json"`, no `path`; assert output `path = "data/taxomesh.json"`
  - `test_show_config_yaml_type_with_custom_path` — toml with `[repository]\ntype = "yaml"\npath = "custom/store.yaml"`; assert output shows `path = "custom/store.yaml"`
  - `test_show_config_path_only_no_type_defaults_to_yaml` — toml with only `path` set (no `type`); assert output shows `type = "yaml"` and the overridden path (US2 AC2)
  - `test_show_config_with_explicit_config_flag` — pass `["--config", str(toml_path), "--show-config"]`; assert output reflects that file's values
  - `test_show_config_empty_config_file_uses_all_defaults` — empty toml file; assert output identical to no-file case
  - `test_show_config_malformed_toml_exits_nonzero` — malformed toml; assert `result.exit_code != 0`
  - `test_show_config_malformed_toml_error_to_stderr` — malformed toml; assert stdout is empty and stderr contains error message
  - `test_dump_output_usable_as_config_file` (class `TestShowConfigEndToEnd`) — pipe dump output to `tmp_path/taxomesh.toml`; invoke `category list` using that file; assert exit 0 (SC-001 end-to-end verification)

- [ ] T010 [US2] Run `pytest tests/adapters/cli/test_config_dump.py` — confirm all T009 tests pass. No new implementation is required; `_resolve_effective_config` from T006 handles all cases. Fix `_resolve_effective_config` if any test reveals a missing edge case.

**Checkpoint**: All P1 acceptance scenarios from spec FR-005, FR-008, FR-009 pass.

---

## Phase 4: User Story 3 — CONFIG_KEYS Completeness Invariant (Priority: P2)

**Goal**: The `CONFIG_KEYS` named constant is the single authoritative source of all
supported TOML setting names. Tests enforce that the dump output and the constant stay
in sync.

**Independent Test**: Parse the output of `dump_config()` with `tomllib`; assert that
every dotted-path in `CONFIG_KEYS` corresponds to a key present in the parsed output
and vice versa.

### Tests for User Story 3 (write first — must FAIL before running)

- [ ] T011 [US3] Write failing invariant tests for `CONFIG_KEYS` completeness in `tests/adapters/cli/test_config_dump.py`. Tests to include:
  - `test_config_keys_covers_all_dump_output_keys` — parse `dump_config("yaml", "data/taxomesh.yaml")` with `tomllib`; flatten to dotted paths; assert the set equals `set(CONFIG_KEYS)`
  - `test_dump_output_has_no_keys_outside_config_keys` — same parse; assert no key in parsed output is absent from `CONFIG_KEYS`
  - `test_config_keys_has_no_duplicates` — assert `len(CONFIG_KEYS) == len(set(CONFIG_KEYS))`

- [ ] T012 [US3] Run `pytest tests/adapters/cli/test_config_dump.py` — confirm all T011 tests pass. No new implementation required; `CONFIG_KEYS` was defined in T002 and `dump_config` in T003. Fix either if the invariant test reveals a mismatch.

**Checkpoint**: All three user stories fully functional and independently testable.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Docstrings, quality gate compliance, final validation.

- [ ] T013 [P] Add Google-style module, function, and constant docstrings to all new additions in `taxomesh/adapters/cli/config.py`:
  - Module docstring (update if already present)
  - `CONFIG_KEYS` inline comment explaining purpose
  - `_resolve_effective_config` — Args, Returns, Raises sections
  - `dump_config` — Args, Returns sections

- [ ] T014 [P] Run `ruff check . && ruff format --check .` — fix any linting or formatting issues in `taxomesh/adapters/cli/config.py` and `taxomesh/adapters/cli/main.py`

- [ ] T015 [P] Run `mypy --strict .` — fix any type errors in the two modified files. Pay attention to:
  - `CONFIG_KEYS: Final[list[str]]` annotation
  - `_resolve_effective_config` return type `tuple[str, str]`
  - `dump_config` parameter and return types
  - `show_config: bool` parameter in `main()`

- [ ] T016 Run `pytest --cov=taxomesh --cov-fail-under=80` — confirm coverage gate passes with no regressions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately
- **User Stories (Phase 2–4)**: All depend on Phase 1 completion
  - US1 (Phase 2) and US2 (Phase 3) share the same implementation; US2 adds only tests
  - US3 (Phase 4) depends on Phase 1 for `CONFIG_KEYS`; can run after Phase 1 independently
- **Polish (Phase 5)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only — implements `_resolve_effective_config` + `--show-config` flag
- **US2 (P1)**: Depends on US1 completion — adds test coverage for merged-config scenarios; no new implementation
- **US3 (P2)**: Depends on Foundational only — tests `CONFIG_KEYS` invariant; no new implementation

### Within Each Phase

```
Phase 1:  T001 → T002 → T003 → T004
Phase 2:  T005 → T006 → T007 → T008
Phase 3:  T009 → T010
Phase 4:  T011 → T012
Phase 5:  T013 [P], T014 [P], T015 [P] → T016
```

### Parallel Opportunities

```
# Phase 5 tasks can run in parallel (different concerns):
Task T013: "Add docstrings to taxomesh/adapters/cli/config.py"
Task T014: "Run ruff check + format check"
Task T015: "Run mypy --strict ."
# Then sequentially:
Task T016: "Run pytest --cov=taxomesh --cov-fail-under=80"
```

---

## Implementation Strategy

### MVP (User Stories 1 and 2 — both P1)

1. Complete Phase 1: Foundational (`CONFIG_KEYS` + `dump_config`)
2. Complete Phase 2: US1 (`_resolve_effective_config` + `--show-config` flag)
3. Complete Phase 3: US2 (additional tests only)
4. **STOP and VALIDATE**: All P1 acceptance scenarios pass
5. Proceed to US3 (P2) and Polish

### Key Constraints

- Per project constitution: every test in T001, T005, T009, T011 MUST fail before the corresponding implementation task begins
- `dump_config()` must never reference config key names as bare string literals — all key references must flow through `CONFIG_KEYS`
- `_resolve_effective_config` must never construct `TaxomeshService`, call `build()`, or perform any repository I/O (FR-011)
- stdout receives only TOML output; stderr receives only error messages (enables safe shell redirection)
