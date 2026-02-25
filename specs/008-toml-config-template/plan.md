# Implementation Plan: taxomesh.toml Configuration Template

**Branch**: `008-toml-config-template` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-toml-config-template/spec.md`

**Note**: This plan is produced by the `/speckit.plan` command.

---

## Summary

Adds a self-documenting `taxomesh.toml.example` template at the repository root, a top-level
`## Configuration` section to `README.md`, and makes `TaxomeshService` config-aware:
auto-discovers `taxomesh.toml` from CWD, accepts an explicit `config_path`, exposes a `repository`
property, and raises `TaxomeshConfigError` for all config failures (invalid TOML, unsupported
`type`, OS read errors — all with exception chaining).

No new runtime dependencies. `tomllib` is Python 3.11 stdlib. All existing call sites are
backward-compatible (the new `config_path` parameter is keyword-only with a `None` default).

Architecture note (FR-014): default storage paths (`data/taxomesh.yaml`, `data/taxomesh.json`)
are owned exclusively by their respective adapter modules as `Final` constants. The service is
repository-agnostic at the config level — it calls `YAMLRepository()` / `JsonRepository()` with
no explicit path when no path is configured, delegating defaults entirely to the adapter layer.

---

## Technical Context

**Language/Version**: Python 3.11 (`tomllib` is stdlib from 3.11+)
**Primary Dependencies**: stdlib `tomllib`, `pathlib.Path` — no new runtime dependencies
**Storage**: Single TOML file on disk (read-only at `TaxomeshService` init time)
**Testing**: pytest, pytest-cov
**Target Platform**: macOS / Linux / Windows (cross-platform via `pathlib`)
**Project Type**: Library + CLI adapter
**Performance Goals**: Config read is a one-shot O(1) file read at `TaxomeshService.__init__`; no ongoing cost
**Constraints**: No new runtime deps; backward-compatible constructor signature; `tomllib` stdlib only
**Scale/Scope**: Single config file; `[repository]` section with two keys (`type`, `path`)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Hexagonal — dependency direction | ✅ PASS | Adapter imports remain lazy inside `if repository is None:` guard (composition-root exception). `DEFAULT_YAML_PATH` / `DEFAULT_JSON_PATH` live exclusively in adapter modules; the service calls constructors with no explicit path when none is configured (FR-014 / "adapter defaults stay in adapters" clause). |
| II. Single facade | ✅ PASS | `TaxomeshService` gains `config_path` and `repository`; remains the sole public entry point for all user operations. |
| III. Structural typing | ✅ PASS | `TaxomeshRepositoryBase` protocol is unchanged. |
| IV. Pydantic + mypy strict | ✅ PASS | No new domain models. `mypy --strict` passes with zero suppressions across all 35 source files. |
| V. Exception hierarchy | ✅ PASS | `TaxomeshConfigError(TaxomeshError)` added as a direct child — not under `ValidationError` or `RepositoryError`. Exported from `taxomesh/__init__.py`. |
| VI. DAG cycle detection | ✅ PASS | Not touched by this feature. |
| VII. Spec-driven | ✅ PASS | Spec, clarifications, research, data-model, contracts, and plan all present before implementation. |
| VIII. Quality gates | ✅ PASS | `ruff check`, `ruff format --check`, `mypy --strict`, `pytest --cov ≥ 80%` — all pass (268 tests, 93% coverage). |

No violations. Complexity Tracking table not required.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-toml-config-template/
├── plan.md              # This file
├── research.md          # Phase 0 — path resolution, OSError wrapping, type-specific defaults
├── data-model.md        # Phase 1 — TaxomeshConfigError, config dict shape, TaxomeshService extensions
├── quickstart.md        # Phase 1 — CLI and Python API usage examples
├── contracts/
│   └── service-init.md  # Phase 1 — TaxomeshService.__init__ signature + behaviour matrix
└── tasks.md             # Phase 2 — T001–T014, all complete ✅
```

### Source Code (files touched by this feature)

```text
taxomesh/
├── exceptions.py                          # TaxomeshConfigError added
├── __init__.py                            # TaxomeshConfigError exported
├── application/
│   └── service.py                         # config_path param (keyword-only), repository property,
│                                          #   _build_repo_from_config static method,
│                                          #   ROOT_CATEGORY_NAME + _DEFAULT_CONFIG_FILENAME constants
├── adapters/
│   ├── cli/
│   │   └── config.py                      # build() simplified; Final annotation on _CONFIG_FILENAME
│   └── repositories/
│       ├── yaml_repository.py             # DEFAULT_YAML_PATH: Final[Path] constant
│       └── json_repository.py             # DEFAULT_JSON_PATH: Final[Path] constant

taxomesh.toml.example                      # New — self-documenting TOML template at repo root
README.md                                  # ## Configuration section added; two comment lines updated

tests/
├── service/
│   ├── test_service_config.py             # New — FR-008–FR-013 + FR-011 OSError chaining
│   └── test_json_repository.py            # test_service_default_repository_uses_yaml updated (data/ prefix)
└── test_cli.py                            # Three assertions updated for data/ path prefix
```

**Structure Decision**: Single-project layout. No new directories or packages created.
`taxomesh.toml.example` lives at the repository root (outside the package) and is not shipped
in the installed wheel — consistent with the `examples/` content policy (no `pyproject.toml`
changes needed; hatchling only packages the `taxomesh/` directory).

---

## Phase 0: Research

**Output**: [`research.md`](./research.md)

Three decisions resolved before implementation began:

| Decision | Outcome |
|----------|---------|
| Relative `path` resolution base | CWD at `TaxomeshService()` construction time |
| OSError handling on config read | Wrap in `TaxomeshConfigError` with chaining (`from exc`) |
| Type-specific `path` defaults | `"data/taxomesh.yaml"` for yaml, `"data/taxomesh.json"` for json |

No NEEDS CLARIFICATION items remained after research. All three informed FR updates in spec.md.

---

## Phase 1: Design & Contracts

### Data Model

**Output**: [`data-model.md`](./data-model.md)

No new domain entities (`pydantic.BaseModel` subclasses). Two additions to the application layer:

1. **`TaxomeshConfigError`** — new exception, direct child of `TaxomeshError`. Raised for invalid
   TOML syntax, unsupported `type` value, and OS read errors on the config file. All three cases
   chain the original exception via `from exc`.

2. **`TaxomeshService` extensions**:
   - `config_path: Path | str | None = None` — new keyword-only `__init__` parameter.
   - `repository` property — returns `self._repo`, the active backend.
   - `_build_repo_from_config(config, config_path)` — private static method; all adapter imports
     inside this method (composition-root exception). Calls `YAMLRepository()` /
     `JsonRepository()` with no explicit path when the config omits `path` (adapter owns its
     default — FR-014).

### Contracts

**Output**: [`contracts/service-init.md`](./contracts/service-init.md)

Documents the `TaxomeshService.__init__` signature update and the full five-row behaviour matrix
covering all combinations of `repository`, `config_path`, and config-file existence.

### Quickstart

**Output**: [`quickstart.md`](./quickstart.md)

CLI and Python API usage examples covering: auto-discovery, explicit `config_path`, repository
bypass, config error handling, and minimal TOML examples for both backends.

---

## Key Design Decisions

### FR-014: Adapter defaults stay in adapters

The most architecturally significant decision of this feature (captured in constitution v1.2.4).

**Problem**: An earlier implementation placed `_DEFAULT_YAML_PATH` and `_DEFAULT_JSON_PATH`
string constants in `service.py`. This leaked storage-specific knowledge into the application
layer, violating the hexagonal architecture boundary.

**Solution**: Constants live exclusively in the adapter modules as public `Final[Path]` constants
(`DEFAULT_YAML_PATH`, `DEFAULT_JSON_PATH`). When no `path` is provided in the config, the
service calls the repository constructor with no argument — the adapter's default parameter takes
effect. The service never names a path it doesn't need to know.

**Consequence**: `service.py` is genuinely repository-agnostic at the config level. Changing the
default path for any adapter requires touching only that adapter module.

### taxomesh.toml is a library config, not a CLI config

`taxomesh.toml` is read by `TaxomeshService`, not by the CLI. The CLI calls `TaxomeshService`
(which reads the file) and inherits whatever backend was constructed. This means:
- Unknown-key warnings, if ever added, belong in the service layer — not in `--verbose` output.
- Format versioning (if ever needed) is a service concern — not a CLI concern.
- The `--config` flag is a CLI convenience to override which file `TaxomeshService` receives as
  `config_path`; it is not documented inside `taxomesh.toml.example` itself.

---

## Complexity Tracking

No constitution violations. Table omitted.
