# Data Model: Admin Metadata Fields

**Feature**: 019-admin-metadata-fields
**Date**: 2026-03-01

## No schema changes

This feature introduces no new entities and no database schema changes. Both `CategoryModel.metadata`
and `ItemModel.metadata` already exist as `JSONField(blank=True, default=dict)` in the database.

## Affected entities

### Category (domain model)

| Field | Type | Constraint | Notes |
|-------|------|-----------|-------|
| `category_id` | `UUID` | required | Unchanged |
| `name` | `str` | max 256 chars | Unchanged |
| `description` | `str` | max 100 000 chars | Unchanged |
| `slug` | `str` | max 256 chars | Unchanged |
| `enabled` | `bool` | — | Unchanged |
| `external_id` | `str \| None` | max 256 chars | Unchanged |
| `metadata` | `dict[str, Any]` | default `{}` | **Now writable via admin** |

### Item (domain model)

| Field | Type | Constraint | Notes |
|-------|------|-----------|-------|
| `item_id` | `UUID` | required | Unchanged |
| `name` | `str` | max 256 chars | Unchanged |
| `external_id` | `str` | max 256 chars | Unchanged |
| `slug` | `str` | max 256 chars | Unchanged |
| `enabled` | `bool` | — | Unchanged |
| `metadata` | `dict[str, Any]` | default `{}` | **Now writable via admin** |

## Service method changes

### `TaxomeshService.update_category`

New signature (parameter added):

```
update_category(
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
    slug: str | None = None,
    metadata: dict[str, Any] | None = None,   # NEW
) -> Category
```

Behaviour: when `metadata` is not `None`, the category's `metadata` field is replaced with the
provided value. When `None`, the existing metadata is preserved unchanged.

### `TaxomeshService.update_item`

New signature (parameter added):

```
update_item(
    item_id: UUID,
    enabled: bool | None = None,
    slug: str | None = None,
    name: str | None = None,
    metadata: dict[str, Any] | None = None,   # NEW
) -> Item
```

Behaviour: identical pattern to `update_category` above.
