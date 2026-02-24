# Implementation Plan: CLI Verbose Mode & List Enhancements

**Branch**: `005-cli-verbose` | **Date**: 2026-02-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-cli-verbose/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command.

---

## Summary

Extend the taxomesh CLI with three related improvements: a `--verbose` boolean flag
that prints repository type, configuration, and config-file path before any command
output; headers and footers on all three `list` sub-commands showing entity label and
record count; and a new `get_config_summary() -> str` method added to
`TaxomeshRepositoryBase` (Protocol) and implemented by `JsonRepository`. No new
domain entities are introduced. Changes touch the ports layer (protocol), one
repository adapter, and the CLI adapter (`config.py` + `main.py`).

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Typer (CLI), Pydantic v2 (domain models), FastAPI (mandatory runtime per constitution)
**Storage**: JSON file via `JsonRepository` (single-file, atomic writes)
**Testing**: pytest + Typer `CliRunner`
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows)
**Project Type**: Library + CLI
**Performance Goals**: N/A — output is a handful of lines; no throughput concern
**Constraints**: mypy `--strict`; line length 119; ruff clean; coverage ≥ 80%
**Scale/Scope**: Three files modified; one new dataclass; one new protocol method

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal Architecture | ✅ PASS | CLI adapter → ports protocol; no application → adapter import introduced. `config.py` already imports `JsonRepository` at the adapter layer — no new coupling. |
| II. TaxomeshService as facade | ✅ PASS | `TaxomeshService` is not changed. The CLI holds the repo reference internally for verbose display only; end-users never access it directly. |
| III. Repository as Protocol | ✅ PASS | `get_config_summary()` added as the 19th Protocol method. Structural typing preserved — no inheritance required. All existing implementations (only `JsonRepository`) will be updated. |
| IV. Pydantic models + mypy strict | ✅ PASS | No new domain models. `BuildResult` dataclass is in the adapter layer. `get_config_summary() -> str` is fully typed. `ctx.obj` typed via access helpers. |
| V. Custom exception hierarchy | ✅ PASS | `get_config_summary()` MUST NOT raise (per FR-011 and research Decision 7). No new exception types needed. |
| VI. DAG integrity | ✅ N/A | No category relationship changes. |
| VII. Spec-driven development | ✅ PASS | Spec exists at `specs/005-cli-verbose/spec.md`. |
| VIII. Quality gates | ✅ PASS | All gates enforced: ruff, mypy --strict, pytest ≥ 80% coverage. Existing `test_cli.py` output-assertion tests will need updating for new headers/footers. |
| IX. Pluggable REST views | ✅ N/A | No REST view changes. |

**Post-design re-check**: No violations introduced. No Complexity Tracking entry required.

---

## Project Structure

### Documentation (this feature)

```text
specs/005-cli-verbose/
├── plan.md                                  # This file
├── research.md                              # Phase 0 output
├── data-model.md                            # Phase 1 output
├── quickstart.md                            # Phase 1 output
├── contracts/
│   ├── cli-verbose.md                       # CLI option + output format contract
│   └── repository-config-method.md          # get_config_summary() contract
├── checklists/
│   └── requirements.md                      # Spec quality checklist
└── tasks.md                                 # Phase 2 output (/speckit.tasks)
```

### Source Code (modified files only)

```text
taxomesh/
├── ports/
│   └── repository.py            # + get_config_summary() as 19th Protocol method
├── adapters/
│   ├── repositories/
│   │   └── json_repository.py   # + get_config_summary() implementation
│   └── cli/
│       ├── config.py            # BuildResult dataclass; build() replaces build_service()
│       └── main.py              # --verbose flag; verbose block; list headers/footers

tests/
└── test_cli.py                  # Extended: verbose tests + header/footer tests
```

**Structure Decision**: Single-project layout (existing). No new packages or modules;
all changes are modifications to existing files.

---

## Design Decisions (from research.md)

### `--verbose` implementation
Use `typer.Option(False, "--verbose", is_flag=True)` — a plain boolean flag.
Present = verbose enabled; absent = verbose disabled. No integer levels.

### `ctx.obj` structure
`dict[str, Any]` with keys `config_path: Path | None` and `verbose: bool`.
Access via typed helper functions `_verbose(ctx) -> bool` and `_config_path(ctx)`. Service
construction remains lazy (inside each sub-command) to avoid side effects on `--help`.

### `build_service()` → `build()` returning `BuildResult`
`config.py` gains a `BuildResult` dataclass with `service`, `repository`,
`config_file_path` (absolute `Path`), and `config_file_exists` (`bool`).
Each sub-command calls `build(_config_path(ctx))`, then if verbose ≥ 1 calls
`_print_verbose(result)` before the command's own output.

### `get_config_summary()` method
Named `get_config_summary() -> str`. Added to `TaxomeshRepositoryBase` Protocol as
method 19. Contracts: non-empty, no raise, no secrets. `JsonRepository` returns
`str(self._path)`.

### Verbose block format
```
Repository  : JsonRepository
Config      : taxomesh.json
Config file : /abs/path/taxomesh.toml [not found]
```
Printed to stdout unconditionally when verbose ≥ 1, before any sub-command output.

### List header/footer format
```
--- Categories ---
<records>
--- Total: N ---
```
Entity labels: `Categories`, `Items`, `Tags`. Always printed, regardless of verbosity.

---

## Complexity Tracking

> No constitution violations to justify.
