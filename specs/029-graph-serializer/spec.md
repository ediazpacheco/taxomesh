# Feature Specification: Graph Serializer for HTTP Integration

**Feature Branch**: `029-graph-serializer`
**Created**: 2026-03-11
**Status**: Draft
**Input**: User description: "Add taxomesh/contrib/api/serializers.py with a graph_to_dict(graph: TaxomeshGraph) -> dict function that recursively serializes a TaxomeshGraph snapshot into a plain JSON-serializable dict. Each CategoryNode becomes {category: {...}, items: [...], children: [...]} where category and items use .model_dump() (already Pydantic). Re-export serializers from taxomesh/contrib/api/__init__.py alongside the existing schemas/handlers/errors modules. Add unit tests in tests/contrib/test_api_serializers.py using InMemoryRepository. No changes to domain models — TaxomeshGraph and CategoryNode stay as dataclasses."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Serialize graph for an HTTP response (Priority: P1)

A developer using taxomesh in a web application calls `get_graph()` and needs to return the result as a JSON HTTP response. Without a serializer, they must manually walk the dataclass tree and call `.model_dump()` on each nested Pydantic model. With `serializers.graph_to_dict`, one call converts the entire graph into a plain dict that any HTTP framework can serialize directly.

**Why this priority**: This is the sole purpose of the feature. Everything else (re-export, tests) exists to support this function.

**Independent Test**: Call `serializers.graph_to_dict(graph)` on a graph with nested categories, items, and children. Confirm the returned dict is JSON-serializable and matches the expected structure at every level.

**Acceptance Scenarios**:

1. **Given** a `TaxomeshGraph` with root categories, items, and nested child categories, **When** `graph_to_dict(graph)` is called, **Then** it returns a dict with a `"roots"` key containing a list where each element has `"category"`, `"items"`, and `"children"` keys.
2. **Given** a `CategoryNode` with three child nodes each with their own children, **When** the graph is serialized, **Then** the nesting is preserved recursively at every depth — no node is flattened or dropped.
3. **Given** a `TaxomeshGraph` with no categories, **When** `graph_to_dict(graph)` is called, **Then** it returns `{"roots": []}`.
4. **Given** a category with no items and no children, **When** serialized, **Then** its node contains `"items": []` and `"children": []`.

---

### User Story 2 - Discover the serializer via the contrib.api package (Priority: P2)

A developer who already imports `schemas`, `handlers`, and `errors` from `taxomesh.contrib.api` finds `serializers` available from the same import path without hunting through submodules.

**Why this priority**: Discoverability. Consistent with how the other three modules are exposed.

**Independent Test**: `from taxomesh.contrib.api import serializers` succeeds and `serializers.graph_to_dict` is callable.

**Acceptance Scenarios**:

1. **Given** a Python environment with taxomesh installed, **When** a developer writes `from taxomesh.contrib.api import serializers`, **Then** the import succeeds and `serializers.graph_to_dict` is accessible.

---

### Edge Cases

- What happens when a `CategoryNode` has items but no children? → `"children": []` in output.
- What happens when a `CategoryNode` has children but no items? → `"items": []` in output.
- What happens when the graph has multiple root categories? → `"roots"` list contains all of them in order.
- What happens when a category appears under multiple parents (DAG with shared nodes)? → Each appearance is serialized independently as a separate node; no deduplication.
- What happens when `category.metadata` contains nested dicts? → Delegated entirely to Pydantic's `.model_dump()` — same behaviour as calling it directly on `Category`.

## Requirements *(mandatory)*

### Functional Requirements

**`serializers.py` — graph serialization**

- **FR-001**: `taxomesh/contrib/api/serializers.py` MUST expose a public function `graph_to_dict(graph: TaxomeshGraph) -> dict[str, Any]` that converts a `TaxomeshGraph` snapshot into a plain, JSON-serializable dict.
- **FR-002**: The top-level dict returned by `graph_to_dict` MUST have the shape `{"roots": list[dict]}`.
- **FR-003**: Each `CategoryNode` MUST be serialized as `{"category": dict, "items": list[dict], "children": list[dict]}` where `"category"` is `node.category.model_dump(mode="json")`, `"items"` is `[item.model_dump(mode="json") for item in node.items]`, and `"children"` is the recursively serialized list of child nodes.
- **FR-004**: The function MUST be fully recursive — child nodes are serialized to arbitrary depth using the same structure.
- **FR-005**: `TaxomeshGraph` and `CategoryNode` MUST remain unmodified as dataclasses — no changes to `taxomesh/domain/graph.py`.

**Module organisation**

- **FR-006**: `taxomesh/contrib/api/__init__.py` MUST re-export the `serializers` module alongside the existing `schemas`, `handlers`, and `errors` modules, enabling `from taxomesh.contrib.api import serializers`.
- **FR-007**: `serializers.py` MUST pass `mypy --strict` with zero errors.
- **FR-008**: Unit tests MUST be added in `tests/contrib/test_api_serializers.py` covering: empty graph, single-node graph, multi-level nested graph, multiple roots, and nodes with both items and children present simultaneously.

### Key Entities

- **`TaxomeshGraph`**: Read-only dataclass snapshot produced by `TaxomeshService.get_graph()`. Contains `roots: list[CategoryNode]`.
- **`CategoryNode`**: Read-only dataclass representing one category in the tree. Contains `category: Category`, `items: list[Item]`, `children: list[CategoryNode]` (recursive).
- **`graph_to_dict`**: Pure function. Input: `TaxomeshGraph`. Output: `dict[str, Any]` — fully JSON-serializable, no dataclass or Pydantic model instances anywhere in the output.

## Assumptions

- `Category` and `Item` are Pydantic `BaseModel` subclasses; `.model_dump()` is available and produces JSON-serializable output for all their fields.
- `TaxomeshGraph` and `CategoryNode` stay as `@dataclass` — converting them to Pydantic models is explicitly out of scope.
- The output dict is intended for JSON serialization (HTTP responses). No round-trip deserialization is required.
- `model_dump(mode="json")` is used on `Category` and `Item` to convert UUID fields to strings, ensuring the output passes `json.dumps()` without a `TypeError`. This is required to satisfy SC-002.
- Tests use `InMemoryRepository` via the existing `tests/contrib/conftest.py` `service` fixture.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A consuming app can return a fully serialized taxonomy graph from an HTTP endpoint by writing exactly one line beyond the handler call: `return serializers.graph_to_dict(handlers.get_graph(service))`.
- **SC-002**: `graph_to_dict` produces output that passes `json.dumps(result)` without raising `TypeError` for any valid graph returned by `TaxomeshService.get_graph()`.
- **SC-003**: `mypy --strict .` reports zero errors across all files in `taxomesh/contrib/api/`.
- **SC-004**: `tests/contrib/test_api_serializers.py` covers ≥ 90% of lines in `taxomesh/contrib/api/serializers.py`; total project coverage remains ≥ 80%.
