# Data Model: Admin Child Categories Editable Inline (044)

## Affected Entities

### CategoryParentLinkModel (existing — no changes)

This feature re-uses the existing join model without modification.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | Auto PK | — | Django auto field |
| `category` | ForeignKey → CategoryModel | NOT NULL, related_name="parent_links" | The **child** in the relationship |
| `parent_category` | ForeignKey → CategoryModel | NOT NULL, related_name="child_links" | The **parent** in the relationship |
| `sort_index` | IntegerField | default=0 | Ordering of the child among siblings under this parent |

**Unique constraint**: `(category, parent_category)` — one link per child/parent pair.

**Reverse relations used by inlines**:
- `CategoryModel.parent_links` → all links where this category is the child (used by `CategoryParentLinkInline`)
- `CategoryModel.child_links` → all links where this category is the parent (used by `CategoryChildLinkInline`)

---

## New Admin Components (no DB schema change)

### CategoryChildLinkForm

A `ModelForm` for `CategoryParentLinkModel` that adds domain-level validation:

| Validation Rule | Source | Error Target |
|-----------------|--------|--------------|
| Selected child must not already be a direct child of this parent | `unique_together` / service | `category` field |
| Adding child must not create a cycle in the category DAG | `TaxomeshCyclicDependencyError` from service | `category` field |
| Selected child must not be the current category itself (self-link) | form `clean()` | `category` field |

### CategoryChildLinkInline (replacement for current read-only version)

| Property | Value |
|----------|-------|
| Base | `TaxomeshAdminMixin, admin.TabularInline` |
| Model | `CategoryParentLinkModel` |
| `fk_name` | `"parent_category"` (filters records by the parent being edited) |
| `form` | `CategoryChildLinkForm` |
| `autocomplete_fields` | `["category"]` (searchable child category selector) |
| `extra` | `0` |
| `verbose_name` | "Child category" |
| `verbose_name_plural` | "Child categories" |

**Write operations** (both delegate to `TaxomeshService`):

| Operation | Service call |
|-----------|--------------|
| Add link | `svc.add_category_parent(category_id=obj.category_id, parent_category_id=obj.parent_category_id)` |
| Remove link | `svc.remove_category_parent(category_id=obj.category_id, parent_category_id=obj.parent_category_id)` |

---

## No New Migrations

Zero schema changes. This feature is a pure admin UI change over the existing `CategoryParentLinkModel` table.
