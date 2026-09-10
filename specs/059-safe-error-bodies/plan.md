# Implementation Plan: Safe HTTP 500 response bodies

**Branch**: `059-safe-error-bodies` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/059-safe-error-bodies/spec.md`

## Summary

`errors.to_tuple` builds one body — `{"detail": str(exc)}` — before it decides on a
status, and hands that same body to every branch including the two that return 500.
`DjangoRepository` raises `TaxomeshRepositoryError(str(exc))` in 14 places, so the
backend's own message is what reaches the HTTP client: constraint names, table and
column names, and for the file backends absolute paths.

The fix is to build the body per branch rather than once up front. Client-error
branches keep `str(exc)`; the two server-error branches return a single named constant
and log the exception at error level on the module logger, which is a child of the
`taxomesh` logger that already carries a `NullHandler`.

## Technical Context

**Language/Version**: Python 3.11+ syntax targeting 3.13 (`requires-python = ">=3.13"`, `ruff target-version = "py313"`)
**Primary Dependencies**: None new — stdlib `logging` and `typing.Final` only
**Storage**: N/A — this feature touches only the error-mapping primitive
**Testing**: pytest; `caplog` for log assertions (built-in, no new dev dependency)
**Target Platform**: Library consumed by any Python web framework
**Project Type**: Single library package
**Performance Goals**: N/A — `to_tuple` runs once per failed request
**Constraints**: `to_tuple` keeps its signature and its `detail` body key; no HTTP framework import (constitution IX); the generic message is a named constant (constitution X)
**Scale/Scope**: One function in one module (~50 lines), its test module, and one docs page

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies | Assessment |
|---|---|---|
| I. Hexagonal architecture | Yes | `contrib.api.errors` sits at the outermost adapter edge and imports only from `taxomesh.exceptions` and stdlib. Dependency direction unchanged. |
| II. `TaxomeshService` sole facade | No | This feature does not touch the service. |
| III. Repository as protocol | No | No repository change. |
| IV. Pydantic + mypy strict | Yes | `contrib/api/` is inside the `mypy --strict` surface (only `contrib/django/` is excluded). The changed function keeps full annotations. |
| V. Exception hierarchy, no silent failures | Yes | **Closest call in this feature.** Redacting the client-facing body is not a silent failure *provided* the detail is relocated, not dropped — hence FR-005 makes logging mandatory, not optional. Exceptions still propagate; `to_tuple` only maps them. |
| VI. DAG integrity | No | Unrelated. |
| VII. Spec-driven development | Yes | This spec exists; artifacts committed under `specs/059-safe-error-bodies/`. |
| VIII. Quality gates | Yes | SC-004 requires all four gates green. |
| IX. Framework-agnostic HTTP handlers | Yes | No HTTP framework import added. `to_tuple` remains the sole error-mapping primitive with an unchanged signature (FR-008). |
| X. Named constants | Yes | The generic message becomes `GENERIC_SERVER_ERROR_DETAIL: Final[str]`, matching the existing `_HTTP_*: Final[int]` constants in the same module. |
| XI. Object-oriented by default | Tolerated | `errors.py` is already a single module-level function, fixed by principle IX's stated contract (`errors.to_tuple(exc) -> (status, body)`). Introducing a class would break that documented signature. No new violation; no change in direction. |

**Result: PASS.** No violations to justify; the Complexity Tracking table stays empty.

**Post-Phase-1 re-check**: PASS, unchanged. The design adds one constant, one module
logger, and one `logger.error(..., exc_info=exc)` call. It introduces no new module,
no new dependency, and no new public name beyond the exported constant required by
FR-004.

## Project Structure

### Documentation (this feature)

```text
specs/059-safe-error-bodies/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── error-mapping.md # Phase 1 output — the to_tuple contract
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/
├── contrib/
│   └── api/
│       ├── errors.py        # CHANGED — the whole implementation lives here
│       ├── handlers.py       # unchanged
│       ├── schemas.py        # unchanged
│       └── serializers.py    # unchanged
└── exceptions.py             # unchanged — read only

tests/
└── contrib/
    └── test_api_errors.py    # CHANGED — two existing assertions updated, new cases added

docs/
└── http-api-integration.md   # CHANGED — document the generic 500 body (FR-011)
```

**Structure Decision**: No new files in the package. The feature is a behavior change
confined to `taxomesh/contrib/api/errors.py`; the existing test module already owns the
mapping's coverage, including the exhaustiveness guard, so it is extended rather than
supplemented.

## Complexity Tracking

> No constitution violations. Table intentionally empty.
