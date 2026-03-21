# Research: Admin Child Categories Display

**Feature**: 042-admin-child-categories
**Date**: 2026-03-21

## Findings

### How to expose child categories via a reverse inline

**Decision**: Use `admin.TabularInline` on `CategoryParentLinkModel` with `fk_name = "parent_category"`.

**Rationale**: `CategoryParentLinkModel` has two FK columns:
- `category` (the child) — `fk_name = "category"` is used by the existing `CategoryParentLinkInline` (shows parents)
- `parent_category` (the parent) — `fk_name = "parent_category"` reverses the direction and yields all child records

Django's `fk_name` disambiguates which FK to use when a model has more than one FK to the same model. Setting it to `"parent_category"` on an inline registered under `CategoryModelAdmin` causes Django to query `CategoryParentLinkModel.objects.filter(parent_category=<current_category>)`, which is exactly the set of direct child links.

**Alternatives considered**:
- Custom queryset override on a generic inline — more code, not needed because `fk_name` already handles disambiguation cleanly.
- Showing child `CategoryModel` objects directly via a `ManyToManyField` — not applicable; the relationship is expressed through an intermediate link model.

### Read-only inline pattern

**Decision**: Override `has_add_permission`, `has_change_permission`, and `has_delete_permission` to return `False`.

**Rationale**: This is the established pattern in the codebase — `IncomingRelationInline` (admin.py:1222) uses exactly this approach. It requires no template customisation and is the canonical Django way to show data without allowing mutation.

**Alternatives considered**:
- `show_change_link = True` only — still allows add/delete; not sufficient for a read-only requirement.
- Django's `readonly_fields` at the ModelAdmin level — applies to fields, not to entire inlines; not the right tool.

### No service call required

**Decision**: The inline does not override `save_model` or `delete_model`.

**Rationale**: Because all three permission methods return `False`, Django never renders add/change/delete controls, so no save or delete path is reachable. No service delegation is needed.

### `verbose_name` / `verbose_name_plural`

**Decision**: Set `verbose_name = "Child category"` and `verbose_name_plural = "Child categories"` on the inline class.

**Rationale**: Without these overrides, Django derives the name from the model (`CategoryParentLink`), which is confusing in context. The sibling inline `ItemParentLinkInline` sets `verbose_name = "Parent category"` / `verbose_name_plural = "Parent categories"` for the same reason.

### No new migrations

**Decision**: No migrations required.

**Rationale**: The inline reads the existing `CategoryParentLinkModel` table through its already-defined `child_links` reverse relation. No schema change is needed.
