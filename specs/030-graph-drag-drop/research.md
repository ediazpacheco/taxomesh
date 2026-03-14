# Research: 030-graph-drag-drop

## What Already Exists (No New Code Needed)

### Decision: Use existing service methods for reparenting
- **Decision**: `add_category_parent(category_id, parent_id, sort_index)` already performs DAG cycle detection via `check_no_cycle` in `domain/dag.py` before writing. `remove_category_parent` removes the old link. These two compose into a reparent operation.
- **Rationale**: Cycle detection is already a domain responsibility (Constitution Principle VI). No new domain logic needed.
- **Alternatives considered**: Adding a dedicated `reparent_category` service method that wraps remove + add — still valid for clarity, and adopted in plan as thin wrappers.

### Decision: Reuse `save_category_parent_link` / `save_item_parent_link` for bulk reorder
- **Decision**: The repository's `save_category_parent_link(link)` upserts with the new `sort_index` in-place (`update_or_create` with `defaults={"sort_index": ...}`). Bulk reorder = N individual upsert calls with reassigned indices.
- **Rationale**: No new repository protocol method needed; existing upsert already handles sort_index.
- **Alternatives considered**: A dedicated `bulk_update_sort_index` repository method — rejected (YAGNI; N is bounded by the number of siblings, which is small in practice).

### Decision: Graph already sorts by sort_index — no change to `get_graph()`
- **Decision**: `get_graph()` already sorts `node.items` and `node.children` by `sort_index` ascending. After a reorder is persisted, the next call to `get_graph()` returns entries in the updated order. No change needed to the graph builder.
- **Rationale**: The sort is applied in `service.py:698-718` using `sort_index` from link records.
- **Alternatives considered**: None — existing behavior is correct.

---

## Drag-and-Drop JS Approach

### Decision: HTML5 Drag and Drop API (vanilla JS)
- **Decision**: Use the browser-native HTML5 Drag and Drop API with vanilla JS, consistent with the current graph.html approach.
- **Rationale**: The existing graph.html uses zero external JS libraries. Adding SortableJS or similar would require either a CDN dependency (network call, versioning risk) or a JS build pipeline (does not exist in this project). The HTML5 DnD API is sufficient for the admin use case (desktop-primary).
- **Alternatives considered**:
  - SortableJS — better UX, touch support, but requires external dependency.
  - jQuery UI sortable — Django admin ships jQuery but jQuery UI is not included; would need CDN.
  - HTML5 DnD (chosen) — zero dependencies, works in all modern browsers, acceptable for admin.
- **Touch support**: Not implemented in this feature. The spec edge case mentions touch events, but no FR mandates it. Can be added as a follow-on.

---

## `GraphEntry` Additions Needed

Two fields must be added to the `GraphEntry` TypedDict and populated by `_flatten_graph()`:

| Field | Type | Purpose |
|-------|------|---------|
| `sort_index` | `int` | Current sort position of this node within its parent scope. |
| `parent_uuid` | `str` | UUID of the immediate parent category (or the ROOT sentinel string for top-level categories). |

These are needed so the frontend JS can:
1. Know which nodes are siblings (same `parent_uuid`, same `kind`).
2. Send `parent_uuid` in the reorder/reparent request body.

The ROOT category UUID must be threaded through `_flatten_graph()` so root-level categories have a valid `parent_uuid` for the reorder endpoint.

---

## New Service Methods Required

Two thin wrappers are added to `TaxomeshService` for clarity and atomicity:

| Method | Delegates to |
|--------|-------------|
| `reorder_items_in_category(category_id, item_ids_in_order)` | N calls to `save_item_parent_link` with reassigned `sort_index` values |
| `reorder_subcategories(parent_id, category_ids_in_order)` | N calls to `save_category_parent_link` with reassigned `sort_index` values |
| `reparent_item(item_id, old_category_id, new_category_id)` | `remove_item_from_category` then `place_item_in_category` |
| `reparent_category(category_id, old_parent_id, new_parent_id)` | `remove_category_parent` then `add_category_parent` (which runs cycle detection) |

---

## Admin Endpoints

Two new methods added to `CategoryGraphProxyAdmin`, registered in `get_urls()`:

| Endpoint | Method | URL |
|----------|--------|-----|
| `reorder_view` | POST | `graph/reorder/` |
| `reparent_view` | POST | `graph/reparent/` |

Both are wrapped with `self.admin_site.admin_view(...)` — Django admin authentication enforced automatically. Both return `JsonResponse`.

CSRF is handled via the `X-CSRFToken` request header sent by the JS fetch calls (Django admin sets the CSRF cookie; JS reads it from `document.cookie`).

---

## No DB Migration Required

`sort_index` columns already exist on `CategoryParentLinkModel` (line 146), `ItemParentLinkModel` (line 169). No new ORM models or migrations are needed.

---

## Constitution Compliance

| Principle | Status |
|-----------|--------|
| I — Hexagonal architecture | Admin views → Service → Domain. No domain imports in admin layer. ✅ |
| VI — DAG cycle detection in domain | `add_category_parent` calls `check_no_cycle` in `domain/dag.py`. ✅ |
| VIII — Quality gates | ruff + mypy strict + pytest ≥ 80% coverage required. ✅ |
| IX — Framework-agnostic API handlers | Not applicable — these endpoints are Django-admin-specific, not part of `taxomesh.contrib.api`. ✅ |
| X — Named constants | URL names and endpoint path segments defined as `Final[str]` constants. ✅ |
| XI — OO by default | New views are methods on `CategoryGraphProxyAdmin`. New service methods are methods on `TaxomeshService`. ✅ |
