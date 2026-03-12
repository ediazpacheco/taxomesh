# Implementation Plan: Graph Serializer for HTTP Integration

**Branch**: `029-graph-serializer` | **Date**: 2026-03-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-graph-serializer/spec.md`

## Summary

Add `taxomesh/contrib/api/serializers.py` with a single public function `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]` that recursively converts a graph snapshot into a plain JSON-serializable dict using `.model_dump()` on the embedded Pydantic domain models. Re-export `serializers` from `taxomesh/contrib/api/__init__.py`. Cover with unit tests in `tests/contrib/test_api_serializers.py`. No changes to domain models.

## Technical Context

**Language/Version**: Python 3.11 (targets 3.11–3.13)
**Primary Dependencies**: None new — stdlib `typing` only; `Category` and `Item` already Pydantic
**Storage**: N/A — pure read-only serialization; no writes
**Testing**: pytest + `InMemoryRepository` via existing `tests/contrib/conftest.py` fixture
**Target Platform**: Python library
**Performance Goals**: N/A — pure function, no I/O
**Constraints**: `mypy --strict`; `ruff` line-length=119; no HTTP framework imports; coverage ≥ 80% project-wide, ≥ 90% on new file
**Scale/Scope**: Minimal — 1 new source file (~20 LOC), 1 test file (~80 LOC), 1 line change to `__init__.py`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Hexagonal: adapters → application → domain | ✅ | `serializers.py` is in the adapter ring (`contrib/api/`); imports only from `domain/graph.py` — inward dependency, no violation. |
| II — TaxomeshService is the single facade | ✅ | `graph_to_dict` serializes the output of `get_graph()`; does not touch the service or repository directly. |
| III — Repository as Protocol | ✅ | N/A — no storage. |
| IV — Pydantic + mypy --strict | ✅ | `serializers.py` fully type-annotated; passes `mypy --strict`. |
| V — Exception hierarchy | ✅ | No new exceptions; function never raises on valid input. |
| VI — DAG integrity | ✅ | N/A — read-only serialization. |
| VII — Spec-Driven Development | ✅ | Spec and plan exist before code. |
| VIII — Quality Gates | ✅ | ruff, mypy --strict, pytest --cov ≥ 80% required before merge. |
| IX — Framework-Agnostic HTTP Handlers | ✅ | No HTTP framework imports. `serializers.py` is framework-agnostic. |
| X — Named Constants | ✅ | No magic literals; output keys (`"roots"`, `"category"`, `"items"`, `"children"`) are structural — single definition in one function, not duplicated. |
| XI — Object-Oriented by Default | ✅ | `graph_to_dict` is a pure stateless function with no side effects — exempt per the constitution's explicit carve-out for stateless utility functions. |

**Pre-Phase-0 gate**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/029-graph-serializer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api-contract.md  # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
taxomesh/contrib/api/
├── __init__.py          # +1 line: add serializers to import + __all__
├── errors.py            # unchanged
├── handlers.py          # unchanged
├── schemas.py           # unchanged
└── serializers.py       # NEW — graph_to_dict + _node_to_dict

tests/contrib/
├── conftest.py          # unchanged — service fixture reused
├── test_api_errors.py   # unchanged
├── test_api_handlers.py # unchanged
├── test_api_schemas.py  # unchanged
└── test_api_serializers.py  # NEW
```

**Structure Decision**: Single new file in `contrib/api/` following the exact pattern of the three existing modules. One-line change to `__init__.py`. No other files touched.
