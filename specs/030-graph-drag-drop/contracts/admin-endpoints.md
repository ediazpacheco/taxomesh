# Admin Endpoint Contracts: 030-graph-drag-drop

These endpoints are Django admin-internal. They are not part of `taxomesh.contrib.api` and are not exposed to external consumers. Both are registered on `CategoryGraphProxyAdmin` via `get_urls()` and wrapped with `self.admin_site.admin_view()` (staff login required).

---

## POST `graph/reorder/`

Reorders siblings within the same parent scope. Accepts either items within a category or child-categories within a parent category.

**Full admin URL (example):**
```
POST /admin/taxomesh_contrib_django/categorygraphproxy/graph/reorder/
```

**Headers:**
```
Content-Type: application/json
X-CSRFToken: <token from cookie>
```

**Request body:**
```json
{
  "kind": "item",
  "parent_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "ordered_uuids": [
    "aaa00000-0000-0000-0000-000000000001",
    "aaa00000-0000-0000-0000-000000000002",
    "aaa00000-0000-0000-0000-000000000003"
  ]
}
```

| Field | Type | Values | Required | Description |
|-------|------|--------|----------|-------------|
| `kind` | string | `"item"` \| `"category"` | yes | What type of node is being reordered |
| `parent_uuid` | string (UUID) | any valid UUID | yes | UUID of the parent category whose children are being reordered |
| `ordered_uuids` | array of strings (UUIDs) | non-empty | yes | All sibling UUIDs in the desired final order (dense 0-indexed sort will be applied) |

**Success response — HTTP 200:**
```json
{"ok": true}
```

**Error responses:**

| HTTP status | Body | Cause |
|-------------|------|-------|
| 400 | `{"error": "Invalid JSON"}` | Malformed request body |
| 400 | `{"error": "Missing field: <field>"}` | Required field absent |
| 400 | `{"error": "Invalid kind: <value>"}` | `kind` not in `{"item", "category"}` |
| 400 | `{"error": "<message>"}` | UUID not found, not a sibling, etc. |
| 405 | `{"error": "Method not allowed"}` | Non-POST request |
| 500 | `{"error": "<message>"}` | Unexpected server error |

---

## POST `graph/reparent/`

Moves a node (item or category) from one parent to another. For categories, runs DAG cycle detection before writing.

**Full admin URL (example):**
```
POST /admin/taxomesh_contrib_django/categorygraphproxy/graph/reparent/
```

**Headers:**
```
Content-Type: application/json
X-CSRFToken: <token from cookie>
```

**Request body:**
```json
{
  "kind": "category",
  "node_uuid": "bbb00000-0000-0000-0000-000000000001",
  "old_parent_uuid": "ccc00000-0000-0000-0000-000000000001",
  "new_parent_uuid": "ddd00000-0000-0000-0000-000000000001",
  "insert_before_uuid": "eee00000-0000-0000-0000-000000000001"
}
```

| Field | Type | Values | Required | Description |
|-------|------|--------|----------|-------------|
| `kind` | string | `"item"` \| `"category"` | yes | What type of node is being moved |
| `node_uuid` | string (UUID) | any valid UUID | yes | UUID of the item or category to move |
| `old_parent_uuid` | string (UUID) | any valid UUID | yes | UUID of the current parent to remove the node from |
| `new_parent_uuid` | string (UUID) | any valid UUID | yes | UUID of the target parent to add the node to |
| `insert_before_uuid` | string (UUID) or `null` | valid UUID or null | yes | UUID of the existing sibling in the new parent that the node should be inserted before; `null` means append at the end |

**Insertion position logic**: The backend reads all current siblings in `new_parent`, inserts `node_uuid` before `insert_before_uuid` (or at the end if `null`), then reassigns sort-order values as a dense sequence `0, 1, 2, …` across all siblings including the moved node.

**Success response — HTTP 200:**
```json
{"ok": true}
```

**Error responses:**

| HTTP status | Body | Cause |
|-------------|------|-------|
| 400 | `{"error": "Invalid JSON"}` | Malformed request body |
| 400 | `{"error": "Missing field: <field>"}` | Required field absent |
| 400 | `{"error": "Invalid kind: <value>"}` | `kind` not in `{"item", "category"}` |
| 400 | `{"error": "Cannot reparent ROOT category"}` | `node_uuid` is the ROOT category |
| 400 | `{"error": "Cycle detected: ..."}` | Move would create a DAG cycle (categories only) |
| 400 | `{"error": "<message>"}` | Node or parent not found |
| 405 | `{"error": "Method not allowed"}` | Non-POST request |
| 500 | `{"error": "<message>"}` | Unexpected server error |

---

## Frontend JS Contract

The JS in `graph.html` is the sole consumer of both endpoints. It reads the following `data-*` attributes from `.taxomesh-entry` elements:

| Attribute | Source in `GraphEntry` | Purpose |
|-----------|----------------------|---------|
| `data-uuid` | `entry.uuid` | Node's own UUID |
| `data-kind` | `entry.kind` | `"item"` or `"category"` |
| `data-depth` | `entry.depth` | Indentation; used to scope siblings |
| `data-parent-uuid` | `entry.parent_uuid` | Parent scope for reorder calls |
| `data-sort-index` | `entry.sort_index` | Initial sort position |

CSRF token is read from the `csrftoken` cookie and sent as the `X-CSRFToken` header on all fetch calls.
