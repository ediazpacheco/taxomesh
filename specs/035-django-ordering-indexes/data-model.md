# Data Model: Database Indexes for Django Ordering Performance

**Feature**: `035-django-ordering-indexes`
**Date**: 2026-03-15

No new fields, entities, or relationships are introduced. This document records the
index additions as schema changes to existing models.

---

## Index Additions

| Model | Table | Index Name | Fields | Type | Purpose |
|-------|-------|------------|--------|------|---------|
| CategoryModel | taxomesh_category | taxomesh_category_name_idx | (name) | Single-column | Optimise ORDER BY name for list_categories() and list_categories_by_external_id() |
| ItemModel | taxomesh_item | taxomesh_item_name_idx | (name) | Single-column | Optimise ORDER BY name for list_items() and list_items_by_external_id() |
| CategoryParentLinkModel | taxomesh_category_parent_link | taxomesh_catlink_parent_sort_idx | (parent_category_id, sort_index) | Composite | Optimise ORDER BY parent_category_id, sort_index for list_category_parent_links() |
| ItemParentLinkModel | taxomesh_item_parent_link | taxomesh_itemlink_cat_sort_idx | (category_id, sort_index) | Composite | Optimise ORDER BY category_id, sort_index for list_item_parent_links() |

---

## Existing Indexes (unchanged)

| Model | Index | Source |
|-------|-------|--------|
| CategoryModel.external_id | db_index=True | spec 032 |
| CategoryModel.slug | db_index=True | existing |
| CategoryModel.category_id | PRIMARY KEY | existing |
| ItemModel.external_id | db_index=True | spec 032 |
| ItemModel.slug | db_index=True | existing |
| ItemModel.item_id | PRIMARY KEY | existing |
| CategoryParentLinkModel.(category_id, parent_category_id) | unique_together | existing |
| CategoryParentLinkModel.category_id | FK auto-index | existing |
| CategoryParentLinkModel.parent_category_id | FK auto-index | existing |
| ItemParentLinkModel.(item_id, category_id) | unique_together | existing |
| ItemParentLinkModel.item_id | FK auto-index | existing |
| ItemParentLinkModel.category_id | FK auto-index | existing |
| ItemRelationLinkModel.source_item_id | FK auto-index | existing |
| ItemRelationLinkModel.target_item_id | FK auto-index | existing |

---

## Intentionally Excluded

| Model | Column | Reason |
|-------|--------|--------|
| ItemRelationLinkModel | sort_index | list_item_relation_links() always filters by FK (source/target item) first; result sets are small; index would not be used by query planner |
