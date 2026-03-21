# Data Model: Admin Child Categories Display

**Feature**: 042-admin-child-categories
**Date**: 2026-03-21

## No schema changes

This feature introduces no new models, fields, or migrations.

## Existing entities used

### CategoryParentLinkModel (existing, unchanged)

| Field | Type | Role |
|-------|------|------|
| `category` | FK → CategoryModel | The **child** category in the edge |
| `parent_category` | FK → CategoryModel | The **parent** category in the edge |
| `sort_index` | IntegerField | Ordering of the edge |

The model already declares `related_name="child_links"` on the `parent_category` FK, which Django uses internally when `fk_name = "parent_category"` is set on the new inline.

## New inline class (admin layer only)

**`CategoryChildLinkInline`** — a `TabularInline` subclass registered in `CategoryModelAdmin`.

| Attribute | Value | Effect |
|-----------|-------|--------|
| `model` | `CategoryParentLinkModel` | Same join table as the parents inline |
| `fk_name` | `"parent_category"` | Filters by `parent_category = <current_category>` |
| `extra` | `0` | No blank rows shown |
| `verbose_name` | `"Child category"` | Label per row |
| `verbose_name_plural` | `"Child categories"` | Section header |
| `has_add_permission` | returns `False` | Read-only |
| `has_change_permission` | returns `False` | Read-only |
| `has_delete_permission` | returns `False` | Read-only |
