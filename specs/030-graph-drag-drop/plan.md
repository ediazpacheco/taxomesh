# Implementation Plan: Graph Drag-and-Drop Reordering

**Branch**: `030-graph-drag-drop` | **Date**: 2026-03-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/030-graph-drag-drop/spec.md`

## Summary

Add drag-and-drop reordering and reparenting to the taxonomy graph admin view. Items and categories can be dragged to new positions within their parent (reorder) or dropped onto a different parent (reparent). Changes are persisted via two lightweight JSON endpoints on `CategoryGraphProxyAdmin`. Cycle detection for category reparenting is enforced by the existing `check_no_cycle` function in `domain/dag.py`. No new DB migrations, no new JS libraries, no new Python packages required.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django ≥ 4.2 (admin), Pydantic v2 (domain models), stdlib `json` (endpoint parsing), HTML5 Drag and Drop API (frontend — no external JS library)
**Storage**: Django ORM — `CategoryParentLinkModel.sort_index`, `ItemParentLinkModel.sort_index` (both columns already exist; no migration needed)
**Testing**: pytest + pytest-django (`admin_client` fixture)
**Target Platform**: Django admin (desktop browser, staff users)
**Project Type**: Library contrib module (Django admin extension)
**Performance Goals**: Reorder/reparent endpoints respond within normal Django admin latency; no special targets
**Constraints**: No new Python runtime dependencies; no external JS libraries; mypy strict must pass
**Scale/Scope**: Admin-only; bounded by taxonomy size (typically < 1 000 nodes)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I — Hexagonal architecture | Admin views → Service → Domain. No admin-layer imports in service or domain. | ✅ |
| II — TaxomeshService is single facade | New service methods added to `TaxomeshService`; no bypass. | ✅ |
| III — Repository as Protocol | No new repository methods; existing `save_*_link` methods handle sort_index upserts. | ✅ |
| IV — Pydantic + mypy strict | No new domain models; existing models used. mypy strict enforced. | ✅ |
| V — Exception hierarchy | `TaxomeshCyclicDependencyError`, `TaxomeshCategoryNotFoundError`, `TaxomeshItemNotFoundError` used. | ✅ |
| VI — DAG cycle detection in domain | `reparent_category` delegates to `add_category_parent` → `check_no_cycle` in `domain/dag.py`. | ✅ |
| VII — Spec-driven development | Spec exists at `specs/030-graph-drag-drop/spec.md`. | ✅ |
| VIII — Quality gates | ruff + mypy strict + pytest ≥ 80% coverage required before merge. | ✅ |
| IX — Framework-agnostic API handlers | Not applicable — these endpoints are Django-admin-internal, not part of `taxomesh.contrib.api`. | ✅ |
| X — Named constants | Endpoint paths and URL names defined as `Final[str]` constants. | ✅ |
| XI — OO by default | New views are methods on `CategoryGraphProxyAdmin`; new service methods on `TaxomeshService`. | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/030-graph-drag-drop/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── admin-endpoints.md  ← Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (files touched)

```text
taxomesh/
├── application/
│   └── service.py                          # +4 new methods
└── contrib/
    └── django/
        ├── admin.py                        # +2 new views, get_urls(), GraphEntry, _flatten_graph()
        └── templates/admin/taxomesh_contrib_django/
            └── graph.html                  # drag handles + DnD JS + AJAX

tests/
└── contrib/
    └── django/
        └── test_admin_graph.py             # +reorder and reparent tests
```

No new files created. No new directories. No migrations.

**Structure Decision**: Single-project layout. All changes are additive on existing files in the `contrib/django` module. The frontend (graph.html) remains a server-rendered Django template with vanilla JS; no build pipeline introduced.

---

## Implementation Phases

### Phase A — Service Layer (TDD first)

**A1 — Tests for `reorder_items_in_category`**

Write failing tests in `tests/contrib/django/test_admin_graph.py` (or a new `tests/service/test_service_reorder.py`):
- Correct `sort_index` values are written after reorder.
- Raises `TaxomeshCategoryNotFoundError` for unknown category.
- Raises `TaxomeshItemNotFoundError` for UUID not in that category.

**A2 — Implement `reorder_items_in_category`**

```python
def reorder_items_in_category(self, category_id: UUID, item_ids_in_order: list[UUID]) -> None:
```
- Load all `ItemParentLink` records for the category.
- Validate all UUIDs are present.
- Reassign `sort_index` as `0, 1, 2, …` and call `save_item_parent_link` for each.

**A3 — Tests for `reorder_subcategories`**

- Correct `sort_index` values written after reorder.
- Raises `TaxomeshCategoryNotFoundError` for unknown parent.

**A4 — Implement `reorder_subcategories`**

```python
def reorder_subcategories(self, parent_id: UUID, category_ids_in_order: list[UUID]) -> None:
```
Same pattern as A2 but for `CategoryParentLink`.

**A5 — Tests for `reparent_item`**

- Item moves from old category to new category.
- Old link removed; new link created.
- Raises on item/category not found.

**A6 — Implement `reparent_item`**

```python
def reparent_item(self, item_id: UUID, old_category_id: UUID, new_category_id: UUID) -> ItemParentLink:
```
- `remove_item_from_category(item_id, old_category_id)`
- `place_item_in_category(item_id, new_category_id, sort_index=0)`

**A7 — Tests for `reparent_category`**

- Category moves from old parent to new parent.
- Cycle-inducing move raises `TaxomeshCyclicDependencyError`.
- Raises on category not found.

**A8 — Implement `reparent_category`**

```python
def reparent_category(self, category_id: UUID, old_parent_id: UUID, new_parent_id: UUID) -> CategoryParentLink:
```
- `remove_category_parent(category_id, old_parent_id)`
- `add_category_parent(category_id, new_parent_id, sort_index=0)` (cycle check inside)

---

### Phase B — GraphEntry and _flatten_graph()

**B1 — Update `GraphEntry` TypedDict**

Add two fields:
```python
sort_index: int
parent_uuid: str
```

**B2 — Update `_flatten_graph()`**

- Accept `root_uuid: str` parameter (UUID of the ROOT category).
- Thread `parent_uuid` through recursive `_visit()` calls.
- Populate `sort_index` from the link record sort_index for each node.
- Root-level categories use `root_uuid` as `parent_uuid`.

**B3 — Update `graph_view()`**

- Retrieve ROOT category UUID from repository before calling `_flatten_graph()`.
- Pass `root_uuid` to `_flatten_graph()`.

---

### Phase C — Admin Endpoints

**C1 — Tests for `reorder_view`**

Using `admin_client` fixture:
- POST with `kind="item"` → items reordered, HTTP 200 `{"ok": true}`.
- POST with `kind="category"` → categories reordered, HTTP 200.
- POST with missing fields → HTTP 400 with error message.
- POST with unknown UUID → HTTP 400.
- GET request → HTTP 405.

**C2 — Implement `reorder_view`**

```python
def reorder_view(self, request: HttpRequest) -> HttpResponse:
```
- Reject non-POST.
- Parse JSON body.
- Validate `kind`, `parent_uuid`, `ordered_uuids`.
- Call `svc.reorder_items_in_category` or `svc.reorder_subcategories`.
- Return `JsonResponse({"ok": True})` or `JsonResponse({"error": ...}, status=400)`.

**C3 — Tests for `reparent_view`**

- POST to reparent item → item moved, HTTP 200.
- POST to reparent category → category moved, HTTP 200.
- POST cycle-inducing category reparent → HTTP 400 with cycle error.
- ROOT category reparent → HTTP 400.
- GET request → HTTP 405.

**C4 — Implement `reparent_view`**

```python
def reparent_view(self, request: HttpRequest) -> HttpResponse:
```
- Reject non-POST.
- Parse JSON body.
- Validate `kind`, `node_uuid`, `old_parent_uuid`, `new_parent_uuid`.
- Reject ROOT.
- Call `svc.reparent_item` or `svc.reparent_category`.
- Catch `TaxomeshCyclicDependencyError` → HTTP 400 with cycle message.
- Return `JsonResponse({"ok": True})` or error.

**C5 — Register in `get_urls()`**

Add two constants and two URL entries:
```python
GRAPH_REORDER_URL_NAME: Final[str] = "taxomesh_contrib_django_graph_reorder"
GRAPH_REPARENT_URL_NAME: Final[str] = "taxomesh_contrib_django_graph_reparent"
```

---

### Phase D — Template (graph.html)

**D1 — Add data attributes to `.taxomesh-entry`**

Add `data-uuid`, `data-parent-uuid`, `data-sort-index` to each entry div.

**D2 — Add drag handles**

Add a `draggable="true"` wrapper or handle element to each non-ROOT node. Style the cursor as `grab`.

**D3 — Implement DnD JS (reorder)**

Using HTML5 DnD API:
- `dragstart` → record dragged node UUID, kind, parent_uuid.
- `dragover` → highlight potential drop position within same parent + kind scope.
- `drop` → compute new sibling order, POST to `graph/reorder/`, update DOM on success, revert on error.

**D4 — Implement DnD JS (reparent)**

- Drop onto a category node with a different `parent_uuid` → POST to `graph/reparent/`, move node in DOM on success, revert on error.

**D5 — Loading state and error display**

- Disable all drag handles during an in-flight request.
- Show inline error message on failure (dismiss on next drag start).

---

### Phase E — Quality Gates

Run locally before proposing commit:
```bash
ruff check .
ruff format --check .
mypy --strict .
pytest --cov=taxomesh --cov-fail-under=80
```

---

## Named Constants to Add

| Constant | Value | Location |
|----------|-------|----------|
| `GRAPH_REORDER_URL_NAME` | `"taxomesh_contrib_django_graph_reorder"` | `admin.py` |
| `GRAPH_REPARENT_URL_NAME` | `"taxomesh_contrib_django_graph_reparent"` | `admin.py` |
| `GRAPH_REORDER_PATH` | `"graph/reorder/"` | `admin.py` |
| `GRAPH_REPARENT_PATH` | `"graph/reparent/"` | `admin.py` |
| `ROOT_PARENT_SENTINEL` | `"root"` (or actual ROOT UUID) | `admin.py` |
| `DRAG_KIND_ITEM` | `"item"` | `admin.py` |
| `DRAG_KIND_CATEGORY` | `"category"` | `admin.py` |

---

## Complexity Tracking

No constitution violations.
