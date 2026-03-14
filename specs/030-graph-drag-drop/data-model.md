# Data Model: 030-graph-drag-drop

## No New Domain Models

All required domain models already exist. This feature adds no new Pydantic models, ORM models, or database migrations.

---

## Existing Models Used

### CategoryParentLink (domain)
`taxomesh/domain/models/category_parent_link.py`

| Field | Type | Notes |
|-------|------|-------|
| `category_id` | `UUID` | Child category |
| `parent_category_id` | `UUID` | Parent category |
| `sort_index` | `int` | Display order within parent scope; default 0 |

**Reorder strategy**: When siblings are reordered, `sort_index` is reassigned as a dense sequence `0, 1, 2, …` in the new visual order. Existing link is upserted via `save_category_parent_link`.

### ItemParentLink (domain)
`taxomesh/domain/models/item_parent_link.py`

| Field | Type | Notes |
|-------|------|-------|
| `item_id` | `UUID` | Item being placed |
| `category_id` | `UUID` | Parent category |
| `sort_index` | `int` | Display order within the category; default 0 |

**Reorder strategy**: Same dense-sequence reassignment as above via `save_item_parent_link`.

---

## Modified TypedDict: `GraphEntry`

`taxomesh/contrib/django/admin.py`

Two fields are added to the existing `GraphEntry` TypedDict so the template can pass them as `data-*` attributes to the JS drag-and-drop layer.

| Field | Type | New? | Purpose |
|-------|------|------|---------|
| `depth` | `int` | existing | Indentation depth |
| `kind` | `str` | existing | `"category"` or `"item"` |
| `name` | `str` | existing | Display name |
| `uuid` | `str` | existing | Node's own UUID |
| `enabled` | `bool` | existing | Enabled flag |
| `external_id` | `str` | existing | External identifier |
| `linked_url` | `str \| None` | existing | Admin link URL |
| `has_descendants` | `bool` | existing | Has children or items |
| `depth_limited` | `bool` | existing | Beyond max depth |
| `initially_collapsed` | `bool` | existing | Collapsed on load |
| **`sort_index`** | **`int`** | **NEW** | Current sort position within parent scope |
| **`parent_uuid`** | **`str`** | **NEW** | UUID of immediate parent category (ROOT sentinel for top-level) |

### ROOT Sentinel

Top-level categories (children of the hidden ROOT node) use the ROOT category's actual UUID as `parent_uuid`. This UUID is retrieved from the repository inside `_flatten_graph()` so the reorder endpoint can call `reorder_subcategories(root_uuid, ...)` for root-level reorders.

---

## New Service Methods (signatures)

`taxomesh/application/service.py`

```
reorder_items_in_category(category_id: UUID, item_ids_in_order: list[UUID]) -> None
```
Reassigns `sort_index` values on the `ItemParentLink` records for items in the given category, in the order specified by `item_ids_in_order` (dense 0, 1, 2 …).

Raises `TaxomeshCategoryNotFoundError` if `category_id` does not exist.
Raises `TaxomeshItemNotFoundError` if any UUID in `item_ids_in_order` is not placed in that category.

---

```
reorder_subcategories(parent_id: UUID, category_ids_in_order: list[UUID]) -> None
```
Reassigns `sort_index` values on the `CategoryParentLink` records for child categories of `parent_id`, in the order specified by `category_ids_in_order`.

Raises `TaxomeshCategoryNotFoundError` if `parent_id` or any child UUID does not exist.

---

```
reparent_item(item_id: UUID, old_category_id: UUID, new_category_id: UUID) -> ItemParentLink
```
Atomically removes `ItemParentLink(item_id, old_category_id)` and creates `ItemParentLink(item_id, new_category_id, sort_index=0)`. Returns the new link.

Raises `TaxomeshItemNotFoundError` if item not found.
Raises `TaxomeshCategoryNotFoundError` if either category not found.

---

```
reparent_category(category_id: UUID, old_parent_id: UUID, new_parent_id: UUID) -> CategoryParentLink
```
Atomically removes `CategoryParentLink(category_id, old_parent_id)` and calls `add_category_parent(category_id, new_parent_id, sort_index=0)`, which runs `check_no_cycle` before writing.

Raises `TaxomeshCategoryNotFoundError` if any UUID not found.
Raises `TaxomeshCyclicDependencyError` if the move would create a cycle.

---

## Validation Rules

| Rule | Enforced by |
|------|-------------|
| Reorder list must match exactly the existing siblings | `reorder_items_in_category` / `reorder_subcategories` validate that all UUIDs are currently linked to the given parent |
| No DAG cycle on category reparent | `add_category_parent` → `check_no_cycle` in `domain/dag.py` |
| ROOT category must not be reparented | Admin view rejects `node_uuid == ROOT_UUID` before calling service |
| Admin authentication required | `self.admin_site.admin_view(...)` wrapper on all new endpoints |
