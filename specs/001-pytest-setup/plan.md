# Implementation Plan: Dev Toolchain Bootstrap

**Branch**: `001-pytest-setup` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-pytest-setup/spec.md`

## Summary

Configure the project's development toolchain so that a contributor can go from fresh clone
to a fully green quality suite in two commands. This means:

1. Adding `fastapi` as the core runtime dependency and `ruff`, `mypy` to the dev group.
2. Wiring pytest, ruff, and mypy configuration into `pyproject.toml` (no extra config files).
3. Enabling pylint-equivalent rule checks (PL prefix) in the ruff linter configuration.
4. Writing one smoke test that verifies `import taxomesh` works.
5. Confirming all four quality gates (`ruff check`, `ruff format --check`, `mypy --strict`,
   `pytest --cov=taxomesh --cov-fail-under=80`) pass on the resulting minimal codebase.

## Technical Context

**Language/Version**: Python ≥ 3.11
**Primary Dependencies**: fastapi ≥ 0.110 (runtime); pytest, pytest-cov, ruff, mypy (dev)
**Storage**: N/A
**Testing**: pytest + pytest-cov
**Target Platform**: macOS / Linux (Windows via WSL supported by uv)
**Project Type**: Python library
**Performance Goals**: N/A — tooling setup only
**Constraints**: All tool configuration MUST live in `pyproject.toml`; no `.ruff.toml`,
`.mypy.ini`, `setup.cfg`, or `pytest.ini` files
**Scale/Scope**: Single `pyproject.toml` change + one new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Hexagonal Architecture | ✅ N/A | No domain code in this feature |
| II. TaxomeshService facade | ✅ N/A | No application code in this feature |
| III. Repository Protocol | ✅ N/A | No repository code in this feature |
| IV. Pydantic + mypy strict | ✅ Required | `mypy --strict` config is a deliverable of this feature |
| V. Exception hierarchy | ✅ N/A | No exceptions introduced |
| VI. DAG integrity | ✅ N/A | No category logic |
| VII. Spec-driven | ✅ Pass | Spec exists at `specs/001-pytest-setup/spec.md` |
| VIII. Quality gates | ✅ Required | This feature IS the quality gates setup; PL rules extend lint coverage |
| IX. Pluggable REST Views | ✅ N/A | No REST views introduced here |

No violations. No complexity tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/001-pytest-setup/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── quickstart.md        ← Phase 1 output (developer setup guide)
└── tasks.md             ← Phase 2 output (/speckit.tasks — not created here)
```

No `data-model.md` — this feature introduces no domain entities.
No `contracts/` — this feature defines no external interfaces.

### Source Code (repository root)

```text
pyproject.toml           ← modified: add fastapi dep, ruff/mypy/pytest config sections; add PL to ruff select
tests/
└── test_smoke.py        ← new: import smoke test (module-level import; no noqa needed)
```

No new source directories. The existing `taxomesh/__init__.py` and `tests/__init__.py`
are unchanged.

**Structure Decision**: Single-project library layout. The `taxomesh/` package and `tests/`
directory already exist. This feature only touches configuration and adds one test file.

## Phase 0: Research

See [research.md](research.md) — all decisions resolved. No NEEDS CLARIFICATION items.

## Phase 1: Design

### pyproject.toml changes

**Runtime dependency** (`[project.dependencies]`):
```toml
dependencies = ["fastapi>=0.110"]
```

**Dev dependency group** (`[project.optional-dependencies]`):
```toml
[project.optional-dependencies]
yaml = ["pyyaml>=6.0"]
dev = [
    "fastapi>=0.110",
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "pyyaml>=6.0",
]
```

**Ruff configuration** (`[tool.ruff]`):
```toml
[tool.ruff]
target-version = "py311"
line-length = 119

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "PL"]
ignore = []
```

`PL` enables all four pylint rule categories: `PLC` (convention), `PLE` (error),
`PLR` (refactor), `PLW` (warning). No separate pylint installation required.

**Mypy configuration** (`[tool.mypy]`):
```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

**Pytest configuration** (`[tool.pytest.ini_options]`):
```toml
[tool.pytest.ini_options]
addopts = "--cov=taxomesh --cov-report=term-missing --cov-fail-under=80"
testpaths = ["tests"]
```

### Smoke test

Enabling `PL` rules surfaces `PLC0415` (import-outside-top-level) on the original
in-function import. The fix is to move the import to module level — this is more
idiomatic pytest and still validates importability: if `taxomesh/__init__.py` is
broken, pytest collection fails with an `ImportError` before any test runs.

`tests/test_smoke.py`:
```python
import taxomesh


def test_taxomesh_importable() -> None:
    assert taxomesh.__version__ is not None
```

No `noqa` suppressions required. F401 does not trigger because `taxomesh` is used
in the assertion.

### Quickstart

See [quickstart.md](quickstart.md).
