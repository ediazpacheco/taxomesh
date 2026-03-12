# Research: Graph Serializer for HTTP Integration

**Feature**: 029-graph-serializer | **Date**: 2026-03-11

## Phase 0 Findings

No external research was required. All decisions are resolved by inspecting existing code.

---

### Decision 1: Serialization approach — recursive pure function vs dataclasses.asdict

**Decision**: Recursive pure function using `.model_dump()` on `Category` and `Item`.

**Rationale**: `dataclasses.asdict()` recursively processes all nested objects — including the Pydantic domain models (`Category`, `Item`). It would bypass Pydantic's serialization logic and produce raw dict representations that may differ from `.model_dump()` output (e.g., UUID fields would be serialized as `UUID` objects rather than strings, validators would not run). Using `.model_dump()` explicitly on the Pydantic members guarantees consistent, JSON-safe output.

**Alternatives considered**:
- `dataclasses.asdict(graph)` — rejected: bypasses Pydantic serialization; UUIDs become UUID objects, not strings.
- Converting `TaxomeshGraph`/`CategoryNode` to Pydantic models — rejected: they are read-only computed aggregates, not persisted entities; adding Pydantic validation overhead on recursive construction is unnecessary.

---

### Decision 2: Function signature — `graph_to_dict(graph)` vs `node_to_dict(node)` as public API

**Decision**: Only `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]` is public. The per-node helper is a private nested or module-level function prefixed `_`.

**Rationale**: Consumers always have a `TaxomeshGraph` (from `handlers.get_graph`). Exposing `node_to_dict` as a second public function creates unnecessary surface area — no consumer needs to serialize a bare `CategoryNode` outside of graph context.

---

### Decision 3: Where the private node helper lives

**Decision**: Private module-level function `_node_to_dict(node: CategoryNode) -> dict[str, Any]` in `serializers.py`.

**Rationale**: A nested function inside `graph_to_dict` avoids the name being importable but is harder to test. A private module-level function with `_` prefix is equally un-importable from outside, and is readable and testable if needed.

---

### Codebase findings

- `Category` and `Item` both inherit from `ModelBase(BaseModel)` — `.model_dump()` is available on both.
- `CategoryNode.children: list[CategoryNode]` — recursive field; handled by the recursive function.
- `taxomesh/domain/graph.py` uses `from __future__ import annotations` for the forward reference on `children` — no impact on serializer.
- `taxomesh/contrib/api/__init__.py` currently exports `errors`, `handlers`, `schemas` — `serializers` is a straightforward addition following the same pattern.
- `tests/contrib/conftest.py` provides a `service: TaxomeshService` fixture backed by `InMemoryRepository` — directly reusable in the new test file.
