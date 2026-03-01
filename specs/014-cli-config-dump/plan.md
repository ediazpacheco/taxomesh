# Implementation Plan: CLI Config Dump — Display Effective Configuration

**Branch**: `014-cli-config-dump` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-cli-config-dump/spec.md`

## Summary

Add a `--show-config` boolean flag to the taxomesh CLI. When present, it prints
the effective configuration — active TOML file values merged with built-in defaults —
in annotated TOML format to stdout, then exits. All recognised TOML configuration
key names are centralised in a `CONFIG_KEYS` named constant. No new domain entities,
protocol methods, or storage changes are required.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer ≥ 0.12 (CLI), stdlib `tomllib` (TOML parsing, already used)
**Storage**: N/A — read-only feature; no writes to any repository
**Testing**: pytest
**Target Platform**: CLI (cross-platform: macOS, Linux, Windows)
**Project Type**: Library + CLI tool
**Performance Goals**: N/A — startup-time output
**Constraints**: Output must be valid TOML; stdout must be silent when `--show-config` is absent
**Scale/Scope**: 2 existing files modified, 1 new test file; no new runtime dependencies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal (dependency direction) | ✅ PASS | Config dump lives in `adapters/cli/` — the outermost layer. `_resolve_effective_config` imports `DEFAULT_YAML_PATH`/`DEFAULT_JSON_PATH` from sibling adapter modules (adapter→adapter, both in the outermost layer). No domain or application imports added. |
| I — Adapter defaults stay in adapters | ✅ PASS | `DEFAULT_YAML_PATH` and `DEFAULT_JSON_PATH` are imported from their respective adapter modules; not redefined anywhere else. |
| I — Composition-root exception | ✅ N/A | No new lazy imports needed. |
| II — TaxomeshService is single public facade | ✅ PASS | No new service methods; `TaxomeshService` is not instantiated by `--show-config`. Config is resolved via a lightweight TOML parse only. |
| III — Repository as Protocol | ✅ PASS | No changes to the protocol. |
| IV — Pydantic models + mypy strict | ✅ PASS | No new domain models. All new code will be fully typed. |
| V — Custom exception hierarchy | ✅ PASS | No new exceptions. Existing `TaxomeshConfigError` propagates unchanged. |
| VIII — Quality gates non-negotiable | ✅ PASS | Full gate run required before PR. |
| X — Named constants, no magic literals | ✅ PASS | `CONFIG_KEYS` constant defined; path defaults imported from adapter constants. `YAML_REPO_TYPE` and `JSON_REPO_TYPE` constants defined in their respective repository modules and imported into `config.py`; no bare type-identifier literals remain in config-dump logic. |
| XI — OO by default | ✅ PASS | `dump_config()` is a pure stateless function (no side effects, no state). Constitution clause: "Pure stateless utility functions MAY remain module-level when they have no side effects and do not logically belong to a class." |

**Gate result: ALL PASS — proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/014-cli-config-dump/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── cli.md           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (files touched by this feature)

```text
taxomesh/
└── adapters/
    ├── repositories/
    │   ├── yaml_repository.py   # MODIFIED: add YAML_REPO_TYPE constant
    │   └── json_repository.py   # MODIFIED: add JSON_REPO_TYPE constant
    └── cli/
        ├── config.py            # MODIFIED: add CONFIG_KEYS, dump_config(), _resolve_effective_config()
        └── main.py              # MODIFIED: add --show-config flag + early-exit block

tests/
└── adapters/
    └── cli/
        └── test_config_dump.py  # NEW: all tests for --show-config behaviour
```

**Structure Decision**: Single project layout. No new modules or packages. The feature
is a small, self-contained extension of the existing CLI adapter layer.

## Post-Clarification Amendment (2026-02-28)

**FR-011 added** during `/speckit.clarify`: `--show-config` MUST NOT trigger
`TaxomeshService` initialisation or any repository I/O.

**Impact on plan**:

| Item | Original | Revised |
|------|----------|---------|
| `dump_config()` signature | `dump_config(result: BuildResult) -> str` | `dump_config(repo_type: str, repo_path: str) -> str` |
| Effective values source | `BuildResult.repository` introspection | New `_resolve_effective_config(config_path) -> tuple[str, str]` helper |
| Service init on `--show-config` | Yes (via `build()`) | No — lightweight `tomllib` parse only |
| `DEFAULT_YAML_PATH` / `DEFAULT_JSON_PATH` | Not imported by dump (read from repo) | Imported in `_resolve_effective_config` to apply defaults |
| New helper needed | No | Yes: `_resolve_effective_config` in `config.py` |

**Updated source files list**:
```text
taxomesh/
└── adapters/
    ├── repositories/
    │   ├── yaml_repository.py  # add YAML_REPO_TYPE constant
    │   └── json_repository.py  # add JSON_REPO_TYPE constant
    └── cli/
        ├── config.py   # add CONFIG_KEYS + _resolve_effective_config() + dump_config()
        └── main.py     # add --show-config flag + early-exit calling above helpers
                        # NOTE: @app.callback() requires invoke_without_command=True so
                        #       --show-config can exit without a subcommand being provided.

tests/
└── adapters/
    └── cli/
        └── test_config_dump.py   # NEW: tests for --show-config behaviour
```

**Implementation notes**:

- `YAML_REPO_TYPE = "yaml"` and `JSON_REPO_TYPE = "json"` are defined in their
  respective repository modules and imported into `config.py`. This keeps the
  type-identifier strings as named constants (constitution Principle X) with a
  single canonical source of truth in the adapter that owns each backend.
- `invoke_without_command=True` on `@app.callback()` is required because Typer
  normally mandates a subcommand; without it, `taxomesh --show-config` (no
  subcommand) fails with "Missing command". The existing `no_args_is_help=True`
  on the `Typer()` instance continues to show help when no arguments are given.

## Complexity Tracking

> No constitution violations to justify.
