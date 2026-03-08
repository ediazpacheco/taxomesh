# Data Model: Unified __str__ + Django Admin Graph Links

**Feature**: 022-unified-str-admin-links
**Date**: 2026-03-08

## String Representation Format

This feature does not add new fields or entities. It defines a formal contract for the
human-readable string representation of existing domain models.

### Category.__str__

**Format**: `📂 <name> (<parts>)`

Where `<parts>` is a ` - ` joined list of:

| Segment | Condition | Format |
|---------|-----------|--------|
| `slug: <value>` | `category.slug` is truthy | `slug: rock` |
| `id: <value>` | always present | `id: 3f2a...` |
| `ext_id: <value>` | `category.external_id` is truthy | `ext_id: genre-rock` |

**Examples**:
```
📂 Rock (id: 3f2a1b...)
📂 Rock (slug: rock - id: 3f2a1b...)
📂 Rock (slug: rock - id: 3f2a1b... - ext_id: genre-rock)
📂 Rock (id: 3f2a1b... - ext_id: genre-rock)
```

### Item.__str__

**Format**: `🏷️ <name> (<parts>)`

Same conditional logic as Category, using `item_id` and `item.external_id`.

| Segment | Condition | Format |
|---------|-----------|--------|
| `slug: <value>` | `item.slug` is truthy | `slug: my-item` |
| `id: <value>` | always present | `id: a1b2...` |
| `ext_id: <value>` | `item.external_id` is truthy | `ext_id: EXT-001` |

**Examples**:
```
🏷️ Product (id: a1b2...)
🏷️ Product (slug: p1 - id: a1b2... - ext_id: EXT-001)
```

## _flatten_graph Entry Schema

Each entry returned by `_flatten_graph` contains:

| Key | Type | Description |
|-----|------|-------------|
| `depth` | `int` | Nesting depth (0 = root) |
| `kind` | `str` | `"category"` or `"item"` |
| `name` | `str` | `str(category)` or `str(item)` |
| `uuid` | `str` | UUID string used for admin change-page URL |
| `enabled` | `bool` | Whether the entity is enabled |

**Removed keys** (compared to previous implementation): `slug`, `external_id`, `indent_em`.
