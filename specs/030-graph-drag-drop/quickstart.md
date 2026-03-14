# Quickstart: 030-graph-drag-drop

## What This Feature Adds

Drag-and-drop reordering and reparenting on the taxonomy graph admin view
(`/admin/taxomesh_contrib_django/categorygraphproxy/graph/`).

- Drag an **item** up/down within its category → updates sort order.
- Drag an **item** onto a different category → reassigns the item to that category.
- Drag a **category** up/down among its siblings → updates sort order.
- Drag a **category** onto a different parent → moves the category in the DAG (cycle detection enforced).

All changes are persisted immediately via lightweight JSON endpoints inside the Django admin.

---

## Prerequisites

- Django admin is configured with `taxomesh_contrib_django` in `INSTALLED_APPS`.
- The existing graph view works: `/admin/taxomesh_contrib_django/categorygraphproxy/graph/`.
- No new Python packages or JS libraries required.

---

## Files Changed

| File | Change |
|------|--------|
| `taxomesh/application/service.py` | Add `reorder_items_in_category`, `reorder_subcategories`, `reparent_item`, `reparent_category` |
| `taxomesh/contrib/django/admin.py` | Add `reorder_view`, `reparent_view`; update `get_urls()`, `GraphEntry`, `_flatten_graph()` |
| `taxomesh/contrib/django/templates/admin/taxomesh_contrib_django/graph.html` | Add drag handles, DnD JS, AJAX calls |
| `tests/contrib/django/test_admin_graph.py` | Add tests for new service methods and admin endpoints |

---

## How Reorder Works (end to end)

1. User drags node A above node B in the graph.
2. JS collects all sibling UUIDs in their new order.
3. JS posts to `graph/reorder/` with `{kind, parent_uuid, ordered_uuids}`.
4. `reorder_view` calls `svc.reorder_items_in_category(...)` or `svc.reorder_subcategories(...)`.
5. Service reassigns `sort_index` values as `0, 1, 2, …` and upserts each link record.
6. Endpoint returns `{"ok": true}`.
7. JS updates the DOM to reflect the new order.
8. On error: endpoint returns `{"error": "..."}`, JS reverts the DOM and shows the message.

## How Reparent Works (end to end)

1. User drags a node and drops it onto a different parent node.
2. JS posts to `graph/reparent/` with `{kind, node_uuid, old_parent_uuid, new_parent_uuid}`.
3. `reparent_view` calls `svc.reparent_item(...)` or `svc.reparent_category(...)`.
4. For categories: `reparent_category` calls `add_category_parent` which runs `check_no_cycle` in `domain/dag.py`. If a cycle is detected, `TaxomeshCyclicDependencyError` is raised.
5. On success: endpoint returns `{"ok": true}`; JS moves the node in the DOM.
6. On cycle or other error: endpoint returns `{"error": "..."}`, JS reverts and shows the message.
