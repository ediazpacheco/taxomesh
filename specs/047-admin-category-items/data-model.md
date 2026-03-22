# Data Model: 047-admin-category-items

## No Model Changes

This feature introduces no new models, no new fields, and no migrations.

## Existing Entity: ItemParentLinkModel

| Field | Type | Notes |
|-------|------|-------|
| `item` | FK → `ItemModel` | The item being placed |
| `category` | FK → `CategoryModel` | The category the item belongs to |
| `sort_index` | `int` | Display order; defaults to 0 |

**Constraints**:
- `unique_together = [("item", "category")]` — prevents duplicate placements.
- `Index(fields=["category_id", "sort_index"])` — efficient lookup of items by category.

## Join Table Usage

The inline on `CategoryModelAdmin` uses `ItemParentLinkModel` with `fk_name = "category"`. Django filters the queryset to `category = <current CategoryModel>` automatically. The `item` FK is the editable field (autocomplete).

## No DAG Concern

Item-to-category placements are flat assignments, not graph edges. No cycle detection is required. The DAG logic applies only to category-to-category parent links.
