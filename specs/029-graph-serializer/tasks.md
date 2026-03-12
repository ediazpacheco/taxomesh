# Tasks: Graph Serializer for HTTP Integration

**Input**: Design documents from `/specs/029-graph-serializer/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story. TDD is mandatory — test tasks always precede their implementation tasks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to ([US1], [US2])

---

## Phase 1: Setup

**Purpose**: No new dependencies, packages, or directories are required. All infrastructure (InMemoryRepository, service fixture, contrib/api/ package) is already in place.

_No setup tasks — existing structure is ready._

---

## Phase 2: Foundational

**Purpose**: No foundational prerequisites beyond the existing codebase.

_No foundational tasks — proceed directly to user story phases._

---

## Phase 3: User Story 1 — Serialize graph for an HTTP response (Priority: P1) 🎯 MVP

**Goal**: Implement `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]` as a pure, recursive serializer that converts any `TaxomeshGraph` into a fully JSON-serializable dict with shape `{"roots": [...]}`.

**Independent Test**: `json.dumps(serializers.graph_to_dict(service.get_graph()))` must not raise, and the returned dict must match the expected structure at every depth.

### Tests for User Story 1 (TDD — write first, verify they FAIL, then implement)

- [X] T001 [US1] Write failing tests for `graph_to_dict` in `tests/contrib/test_api_serializers.py` covering: empty graph (`{"roots": []}`), single root with no items/children, root with items and no children, root with children and no items, multi-level nesting (root → child → grandchild), multiple root categories, node with both items and children simultaneously, and JSON-serializability via `json.dumps(result)` (use existing `service` fixture from `tests/contrib/conftest.py`)

### Implementation for User Story 1

- [X] T002 [US1] Implement `graph_to_dict` and `_node_to_dict` in `taxomesh/contrib/api/serializers.py` — `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]` returns `{"roots": [_node_to_dict(n) for n in graph.roots]}`; `_node_to_dict(node: CategoryNode) -> dict[str, Any]` returns `{"category": node.category.model_dump(), "items": [item.model_dump() for item in node.items], "children": [_node_to_dict(c) for c in node.children]}`; fully type-annotated; passes `mypy --strict`

**Checkpoint**: Run `pytest tests/contrib/test_api_serializers.py` — all US1 tests must pass before proceeding.

---

## Phase 4: User Story 2 — Discover the serializer via the contrib.api package (Priority: P2)

**Goal**: Re-export `serializers` from `taxomesh/contrib/api/__init__.py` so `from taxomesh.contrib.api import serializers` works and `serializers.graph_to_dict` is accessible alongside `schemas`, `handlers`, and `errors`.

**Independent Test**: `from taxomesh.contrib.api import serializers; assert callable(serializers.graph_to_dict)` succeeds.

### Tests for User Story 2 (TDD — write first, verify they FAIL, then implement)

- [X] T003 [US2] Add import test to `tests/contrib/test_api_serializers.py`: assert `from taxomesh.contrib.api import serializers` succeeds and `serializers.graph_to_dict` is callable; assert `"serializers"` is in `taxomesh.contrib.api.__all__`

### Implementation for User Story 2

- [X] T004 [US2] Update `taxomesh/contrib/api/__init__.py`: add `from taxomesh.contrib.api import serializers` import and add `"serializers"` to `__all__` alongside `"errors"`, `"handlers"`, `"schemas"`

**Checkpoint**: Run `pytest tests/contrib/test_api_serializers.py` — all US1 and US2 tests must pass.

---

## Phase 5: Polish & Quality Gates

**Purpose**: Verify all quality gates required before merge.

- [X] T005 [P] Run `ruff check .` and `ruff format --check .` — zero errors; fix any ruff issues in `taxomesh/contrib/api/serializers.py` and `taxomesh/contrib/api/__init__.py`
- [X] T006 [P] Run `mypy --strict .` — zero errors across all files in `taxomesh/`; fix any type annotation issues in `serializers.py`
- [X] T007 Run `pytest --cov=taxomesh --cov-fail-under=80` and verify `taxomesh/contrib/api/serializers.py` has ≥ 90% line coverage

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1/2**: N/A — infrastructure already exists
- **Phase 3 (US1)**: No external dependencies — start immediately
- **Phase 4 (US2)**: Requires T002 complete (`serializers.py` must exist before it can be re-exported)
- **Phase 5 (Polish)**: Requires T004 complete — all implementation done

### Within Each User Story

- T001 → T002 (tests must exist and fail before implementation)
- T003 → T004 (import test must fail before adding re-export)
- T002 must complete before T003 (T003 imports from serializers.py)

### Parallel Opportunities

- T005 and T006 (Polish phase) are independent and can run in parallel
- T001 and any other pre-existing test files in `tests/contrib/` are unaffected

---

## Parallel Example: User Story 1

```bash
# Only one test file, no parallelism within the story.
# But US1 tests and US2 tests are separate tasks:
Task T001: Write all US1 tests first (empty, single, nested, multi-root, json-safe)
Task T002: Implement serializers.py (after T001 tests fail)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 3: write failing tests (T001) → implement (T002)
2. **STOP and VALIDATE**: `pytest tests/contrib/test_api_serializers.py` — all pass
3. Proceed to Phase 4 (US2) only after MVP validation

### Incremental Delivery

1. T001 → T002: `graph_to_dict` works and is tested
2. T003 → T004: serializers accessible via `from taxomesh.contrib.api import serializers`
3. T005, T006, T007: quality gates pass — ready for PR

---

## Notes

- `tests/contrib/conftest.py` provides the `service` fixture backed by `InMemoryRepository` — reuse it directly; do not create a new fixture
- `graph_to_dict` must never raise for any valid `TaxomeshGraph` from `service.get_graph()`
- `model_dump(mode="json")` is used on `Category` and `Item` to ensure UUID fields serialize to strings
- Line length: 119 (ruff config in `pyproject.toml`)
- No new runtime dependencies — only stdlib `typing` (`Any`)
