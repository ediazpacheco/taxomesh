# Implementation Plan: Framework-Agnostic HTTP API Handlers

**Branch**: `028-contrib-api` | **Date**: 2026-03-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-contrib-api/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Remove the FastAPI transitive dependency and make Pydantic v2 an explicit runtime dep. Ship a new `taxomesh/contrib/api/` module with three framework-agnostic artefacts — `schemas.py` (Pydantic request models), `handlers.py` (pure delegation functions to `TaxomeshService`), and `errors.py` (`to_tuple` exception mapper) — so that consuming apps need ≤10 lines of HTTP glue per endpoint. Update `README.md` with a prominent "HTTP API integration" section showing FastAPI and Django wiring examples.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: Pydantic v2 ≥ 2.0 (now explicit direct dep; was transitive via FastAPI)
**Storage**: N/A — no new storage; handlers delegate entirely to `TaxomeshService`
**Testing**: pytest + `InMemoryRepository` (no HTTP server, no framework dep in tests)
**Target Platform**: Python library — consumed by any web framework (FastAPI, Django, Flask, etc.)
**Project Type**: Library
**Performance Goals**: N/A — handlers are thin pass-through wrappers; perf is dominated by service + repository
**Constraints**: `mypy --strict`; `ruff` line-length=119; no HTTP framework imports anywhere in taxomesh source; coverage ≥ 80%
**Scale/Scope**: Small — 4 new source files (~300 LOC), 3 test files (~280 LOC), 1 README section

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal: adapters → application → domain | ✅ | `contrib/api/` is a new adapter layer; imports only from `application/` and `domain/`. No inward-facing import violations. |
| II — TaxomeshService is the single facade | ✅ | Every handler calls `TaxomeshService`; no direct repository access. |
| III — Repository as Protocol | ✅ | Not applicable to this feature. |
| IV — Pydantic + mypy --strict | ✅ | All schemas are `pydantic.BaseModel`; all new files type-checked under `mypy --strict`. |
| V — Exception hierarchy | ✅ | `errors.py` maps the existing hierarchy; no new exceptions introduced. |
| VI — DAG integrity | ✅ | Not applicable to this feature. |
| VII — Spec-Driven Development | ✅ | This spec and plan exist before code is merged. |
| VIII — Quality Gates | ✅ | ruff, mypy --strict, pytest --cov ≥ 80% are all required before merge. |
| IX — Framework-Agnostic HTTP Handlers | ✅ | Constitution IX amended in this feature: renamed from "Pluggable REST Views", removed FastAPI mandatory dep, updated Toolchain table. Principle now aligns with `taxomesh.contrib.api` design. |
| X — Named Constants | ✅ | HTTP status codes in `errors.py` use `Final[int]` constants (`_HTTP_404`, `_HTTP_409`, etc.). |
| XI — Object-Oriented by Default | ⚠️ | Handlers are module-level functions, not class methods. Justified: they are stateless delegation stubs with no shared mutable state, no side effects of their own, and no logical class to belong to. The constitution explicitly permits "pure stateless utility functions MAY remain module-level when they have no side effects and do not logically belong to a class." |

**Pre-Phase-0 gate**: PASS (two warnings noted and justified in Complexity Tracking below).

## Project Structure

### Documentation (this feature)

```text
specs/028-contrib-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-contract.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/contrib/api/
├── __init__.py          # re-exports schemas, handlers, errors modules
├── schemas.py           # Pydantic request models (8 classes)
├── handlers.py          # delegation functions → TaxomeshService (24 functions)
└── errors.py            # to_tuple() exception mapper

tests/contrib/
├── conftest.py          # service fixture (wraps InMemoryRepository)
├── test_api_schemas.py  # Pydantic validation tests
├── test_api_handlers.py # handler delegation tests
└── test_api_errors.py   # exception mapping tests

pyproject.toml           # dependency change: remove fastapi, add pydantic>=2.0
README.md                # new "HTTP API integration" section
```

**Structure Decision**: `contrib/api/` follows the existing `contrib/django/` pattern — optional extras that sit in the adapter ring without polluting the core library. All new test files live under `tests/contrib/` to mirror the source layout.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle IX: FastAPI removed as mandatory dep | FastAPI was never imported in taxomesh source — listing it as a dep was purely to pull Pydantic v2 transitively. Making Pydantic an explicit dep achieves the same result without binding taxomesh to a full web framework. | Keeping FastAPI listed would silently force any taxomesh consumer to install a 50+ dependency web framework even when building a plain CLI or Django app. |
| Principle XI: module-level handler functions | Handlers are pure delegation stubs: `return service.some_method(...)`. There is no shared state, no configuration, no constructor argument, no method that logically groups with another. A class with 24 `@staticmethod` methods would add ceremony with zero benefit. | A handler class would require instantiation or `@staticmethod` decoration on every method, introducing boilerplate that violates KISS without enabling any reuse or encapsulation. |
