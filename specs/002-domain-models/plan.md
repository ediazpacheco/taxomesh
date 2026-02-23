# Implementation Plan: Extract ExternalId TypeAlias (002-domain-models)

**Branch**: `002-domain-models` | **Date**: 2026-02-22 | **Spec**: [spec.md](spec.md)
**Input**: "to avoid repeat `UUID | Annotated[str, Field(max_length=256)] | int` for external_id create a type and using it. Put the type in a proper module"

## Summary

`Item.external_id` is typed as the inline union `UUID | Annotated[str, Field(max_length=256)] | int`.
This union will be repeated verbatim every time a future layer (application services, repository
adapters, view functions) needs to reference the same type. Extracting it into a named `TypeAlias`
in a dedicated module gives it a stable, importable name and a single definition point.

**Approach**: Create `taxomesh/domain/types.py` with an `ExternalId` TypeAlias, then replace the
inline union in `Item.external_id` with `ExternalId`.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python = ">=3.11"`)
**Primary Dependencies**: pydantic v2 (transitive via `fastapi ≥ 0.110`) — no new dependencies
**Storage**: N/A — pure in-memory domain models; no persistence
**Testing**: pytest + pytest-cov; mypy --strict
**Target Platform**: any (library)
**Project Type**: library
**Performance Goals**: N/A — no runtime behaviour change; purely structural refactoring
**Constraints**: must pass all four quality gates unchanged; `TypeAlias` must be Python 3.11-compatible
**Scale/Scope**: 2 files modified/created; 0 tests changed

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Principle | Status | Notes |
|---|---|---|---|
| No domain→adapter import | I | ✅ PASS | `types.py` imports only `uuid` (stdlib) and `pydantic` (domain's own library) |
| Single public facade | II | ✅ N/A | No service-layer change |
| Protocol / structural typing | III | ✅ N/A | No interface change |
| Pydantic models + mypy strict | IV | ✅ PASS | `TypeAlias` from `typing` is valid in strict mode; `typing.TypeAlias` is the correct Python 3.11 form (PEP 695 `type X = ...` requires 3.12+) |
| Custom exception hierarchy | V | ✅ N/A | No error path change |
| DAG integrity | VI | ✅ N/A | No relationship model change |
| Spec-driven | VII | ✅ PASS | This plan documents the change |
| Quality gates non-negotiable | VIII | ✅ PASS | All four gates pass after implementation |
| Pluggable REST views | IX | ✅ N/A | No adapter change |

No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-domain-models/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Updated — Decision 8 added for TypeAlias
├── data-model.md        # Updated — ExternalId type alias documented
├── quickstart.md        # Updated — ExternalId importable from taxomesh.domain.types
├── contracts/
│   └── python-api.md    # Updated — ExternalId added to import surface
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code

```text
taxomesh/
└── domain/
    ├── __init__.py       # unchanged
    ├── types.py          # NEW — ExternalId TypeAlias
    └── models.py         # MODIFIED — import ExternalId; use in Item.external_id
tests/
└── domain/
    └── test_models.py    # unchanged — observable behaviour of Item.external_id is identical
```

## Files

| File | Action | Change |
|---|---|---|
| `taxomesh/domain/types.py` | Create | Declare `ExternalId` TypeAlias |
| `taxomesh/domain/models.py` | Modify | Import `ExternalId`; replace inline union in `Item.external_id` |

## Implementation Detail

### Step 1 — `taxomesh/domain/types.py`

```python
from typing import Annotated, TypeAlias
from uuid import UUID

from pydantic import Field

ExternalId: TypeAlias = UUID | Annotated[str, Field(max_length=256)] | int
```

- `TypeAlias` from `typing` is the Python 3.11-compatible annotation form.
  `type ExternalId = ...` (PEP 695) requires Python 3.12+ and is therefore forbidden.
- Imports only: stdlib (`uuid`, `typing`) and pydantic (already the domain model library).
  No Principle I violation.

### Step 2 — `taxomesh/domain/models.py`

- **Add** import: `from taxomesh.domain.types import ExternalId`
- **Keep** `UUID` in `from uuid import UUID, uuid4` — still used for all primary key fields.
- **Keep** `Annotated` in `from typing import Annotated, Any` — still used by `Category.name`,
  `Category.description`, and `Tag.name`.
- **Replace** field declaration:
  ```python
  # Before
  external_id: UUID | Annotated[str, Field(max_length=256)] | int
  # After
  external_id: ExternalId
  ```

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict .
uv run pytest --cov=taxomesh --cov-fail-under=80
```

No test changes needed — observable behaviour of `Item.external_id` is unchanged;
only the location of the type definition moves.
