# Implementation Plan: YAML Repository

**Branch**: `007-yaml-repository` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-yaml-repository/spec.md`

## Summary

Add a `YAMLRepository` storage adapter that fully satisfies `TaxomeshRepositoryBase`, make it the default backend for the CLI (replacing `taxomesh.json` with `taxomesh.yaml`), promote `pyyaml` from an optional to a required runtime dependency, and ship an example YAML data file at `examples/taxomesh_example.yaml`. The `TaxomeshService()` default (JsonRepository) is unchanged per Principle II; only the CLI `build()` factory changes its default.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pyyaml ≥ 6.0 (required runtime), types-PyYAML (dev — for mypy --strict)
**Storage**: Single YAML file on disk; atomic writes via tempfile + os.replace
**Testing**: pytest + pytest-cov; target ≥ 80% coverage
**Target Platform**: Local filesystem (same as JsonRepository)
**Project Type**: Library + CLI
**Performance Goals**: No specific latency targets — local file backend, read-once-at-init pattern
**Constraints**: mypy --strict must pass; `types-PyYAML` stubs required; safe_load/safe_dump only
**Scale/Scope**: Single-file storage; same constraints as JsonRepository

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal Architecture | ✅ PASS | `YAMLRepository` → `adapters/repositories/`; no domain imports in adapter |
| II — TaxomeshService facade | ✅ PASS | `TaxomeshService()` default stays `JsonRepository`; only CLI `build()` changes. See R-004. |
| III — Protocol structural typing | ✅ PASS | YAMLRepository satisfies TaxomeshRepositoryBase without inheritance |
| IV — Pydantic + mypy strict | ✅ PASS (with action) | `types-PyYAML` added to dev deps; `safe_load` result annotated as `Any` then narrowed |
| V — Exception hierarchy | ✅ PASS | `TaxomeshRepositoryError` raised for invalid path/parse failures |
| VIII — Quality gates | ✅ PASS | Tests written before implementation (TDD); ≥ 80% coverage enforced |
| **Toolchain** | ⚠ AMENDMENT | Constitution says pyyaml is optional; FR-010 promotes to required. Constitution must be updated. |

**Constitution amendment required**: Toolchain section currently reads "pyyaml is optional (`pip install taxomesh[yaml]`)". This feature promotes pyyaml to a mandatory runtime dependency. The constitution must be updated (PATCH-level change — clarification of dependency status) as part of this feature before merging to main.

## Project Structure

### Documentation (this feature)

```text
specs/007-yaml-repository/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── yaml-file-schema.md   ← YAML on-disk format contract
│   └── toml-config-schema.md ← taxomesh.toml repository config contract
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── adapters/
│   └── repositories/
│       ├── __init__.py                    (no change)
│       ├── json_repository.py             (no change)
│       └── yaml_repository.py             ← NEW
│   └── cli/
│       └── config.py                      ← MODIFY: default type + YAML branch
├── ...

examples/
└── taxomesh_example.yaml                  ← NEW (source only, not in wheel)

tests/
└── service/
    └── test_yaml_repository.py            ← NEW
tests/
└── test_cli.py                            ← MODIFY: add YAML default + type="yaml" tests
tests/
└── test_example_yaml.py                   ← NEW

pyproject.toml                             ← MODIFY: pyyaml → required; types-PyYAML → dev
.specify/memory/constitution.md            ← MODIFY: pyyaml toolchain entry
README.md                                  ← MODIFY: default format, config, example file
```

**Structure Decision**: Single-project layout, extending the existing `adapters/repositories/` package. No new top-level packages. The `examples/` directory is new but sits at repo root (not inside `taxomesh/`), making it clear it is not installed package data.

## Complexity Tracking

No constitution violations requiring justification. The toolchain amendment is PATCH-level (dependency status change, not architectural change).
