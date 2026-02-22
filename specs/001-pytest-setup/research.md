# Research: Dev Toolchain Bootstrap

**Feature**: 001-pytest-setup
**Date**: 2026-02-22

No NEEDS CLARIFICATION items were present in the spec. All decisions were pre-determined
by the constitution and project choices made during governance setup.

This document records the rationale for each tooling configuration decision.

---

## Decision: ruff as unified lint + format tool

**Decision**: Use `ruff` for both linting and formatting (replaces flake8, pylint, isort,
black).

**Rationale**: Constitutionally mandated (Principle VIII). ruff is 10–100× faster than
the tools it replaces and consolidates configuration into a single `pyproject.toml` section.

**Rule selection** — `["E", "F", "I", "UP", "B", "SIM", "PL"]`:
- `E` / `F` — pycodestyle errors and pyflakes (core correctness)
- `I` — isort-compatible import sorting
- `UP` — pyupgrade: enforce modern Python syntax (aligned with Python ≥ 3.11 target)
- `B` — flake8-bugbear: common bug patterns
- `SIM` — flake8-simplify: simplification opportunities
- `PL` — pylint-equivalent checks (see dedicated decision below)

**Alternatives considered**: Starting with `select = ["ALL"]` — rejected; too noisy for
initial setup. Starting with only `["E", "F"]` — rejected; misses import ordering and
modern-syntax enforcement which are constitutional requirements.

---

## Decision: mypy strict mode

**Decision**: `strict = true` in `[tool.mypy]`.

**Rationale**: Constitutionally mandated (Principle IV). Strict mode enables
`--disallow-untyped-defs`, `--disallow-any-generics`, `--warn-return-any`, and others.
`Any` usage is explicitly forbidden by the constitution unless commented.

**fastapi and pydantic typing**: Both fastapi (≥ 0.110) and pydantic v2 ship `py.typed`
markers and are fully typed. No stubs package (`types-*`) is needed for either.

**Alternatives considered**: `disallow_untyped_defs = true` without full strict — rejected;
constitution mandates `--strict`, not a partial approximation.

---

## Decision: pytest-cov with term-missing report and --cov-fail-under=80

**Decision**: `addopts = "--cov=taxomesh --cov-report=term-missing --cov-fail-under=80"` —
coverage always runs and fails the suite if coverage drops below 80%.

**Rationale**: Constitution Principle VIII mandates `pytest --cov=taxomesh
--cov-fail-under=80` unconditionally. The smoke test achieves 100% coverage on the
current minimal codebase, so the gate passes immediately.

**Alternatives considered**: Deferring `--cov-fail-under=80` until domain code lands —
rejected; constitution Principle VIII allows no exceptions.

---

## Decision: fastapi ≥ 0.110 as core runtime dependency

**Decision**: `fastapi>=0.110` in `[project.dependencies]`.

**Rationale**: Constitutionally mandated (Principle IX). FastAPI 0.110 introduced
`fastapi.testclient` improvements and is the first version to fully support Pydantic v2
without compatibility shims.

**Pydantic**: fastapi ≥ 0.110 depends on pydantic ≥ 2.0. No separate pydantic declaration
is needed in runtime deps — it arrives transitively.

**Alternatives considered**: `fastapi>=0.100` — rejected; 0.100–0.109 have partial pydantic
v2 support via compatibility layer. Cleaner to require 0.110+.

---

## Decision: dev group includes fastapi

**Decision**: `fastapi>=0.110` is listed in both `[project.dependencies]` (runtime) and
`[project.optional-dependencies] dev`.

**Rationale**: When a contributor installs with `uv sync --extra dev`, they get a fully
functional environment including the runtime dep. This is idiomatic for Python libraries
where the library itself is installed in editable mode alongside dev tools.

---

## Decision: ruff PL rule set for pylint-equivalent coverage

**Decision**: Add `"PL"` to `[tool.ruff.lint] select`.

**Rationale**: ruff implements pylint checks natively under the `PL` prefix —
`PLC` (convention), `PLE` (error), `PLR` (refactor), `PLW` (warning). Verified via
`uv run ruff linter | grep -i pylint` which confirms `PL Pylint` is a supported rule
set. Constitution Principle VIII states `ruff check .` replaces pylint; enabling PL
rules fulfils that intent without installing pylint as a separate tool (FR-007).

**Alternatives considered**: Installing pylint separately — rejected; contradicts
constitution Principle VIII explicitly.

---

## Decision: PLC0415 violation in smoke test — module-level import

**Decision**: Move `import taxomesh` to module level in `tests/test_smoke.py`.

**Rationale**: Enabling `PL` reveals one violation — `PLC0415`
(import-outside-top-level) on the in-function import. Moving it to module level is the
idiomatic pytest pattern: collection fails with `ImportError` if `taxomesh/__init__.py`
is broken, satisfying US2:AS2 without any `noqa` suppression. The existing `# noqa: F401`
is also no longer needed because the module-level `taxomesh` name is used in the assert.

**Alternatives considered**:
- `# noqa: PLC0415` inline (rejected: suppresses a valid rule for a structural reason
  that disappears after the refactor).
- Global `ignore = ["PLC0415"]` (rejected: project-wide suppression defeats the rule).

---

## Decision: No pytest-asyncio at this stage

**Decision**: `pytest-asyncio` is NOT added to the dev group in this feature.

**Rationale**: The only test in this feature is a synchronous smoke test. pytest-asyncio
is needed when testing async FastAPI views, which belongs to the API adapter feature spec.
Adding it now would be premature.
