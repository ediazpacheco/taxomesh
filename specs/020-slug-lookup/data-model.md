# Data Model: Service Slug Lookup Methods (020-slug-lookup)

## Overview

This feature introduces no new domain entities, no new fields, and no schema migrations.
It adds two read-only service methods that query entities whose models already carry a
`slug` field.

---

## Affected Entities (read-only)

### Category

| Field         | Type                      | Constraint                          |
|---------------|---------------------------|-------------------------------------|
| `category_id` | `UUID`                    | Primary key, library-assigned       |
| `name`        | `str`                     | max `MAX_CATEGORY_NAME_LENGTH`      |
| `slug`        | `str`                     | max `MAX_SLUG_LENGTH`; unique when non-empty |
| `description` | `str`                     | max `MAX_DESCRIPTION_LENGTH`        |
| `enabled`     | `bool`                    | defaults to `True`                  |
| `external_id` | `str`                     | max `MAX_EXTERNAL_ID_STR_LENGTH`    |
| `metadata`    | `dict[str, Any]`          | arbitrary key-value pairs           |

**Lookup key for this feature**: `slug` — unique within the category namespace,
enforced at write time. The root category (`name == ROOT_CATEGORY_NAME`) is never
assigned a slug.

### Item

| Field         | Type                      | Constraint                          |
|---------------|---------------------------|-------------------------------------|
| `item_id`     | `UUID`                    | Primary key, library-assigned       |
| `name`        | `str`                     | max `MAX_ITEM_NAME_LENGTH`          |
| `slug`        | `str`                     | max `MAX_SLUG_LENGTH`; unique when non-empty |
| `external_id` | `str`                     | max `MAX_EXTERNAL_ID_STR_LENGTH`    |
| `enabled`     | `bool`                    | defaults to `True`                  |
| `metadata`    | `dict[str, Any]`          | arbitrary key-value pairs           |

**Lookup key for this feature**: `slug` — unique within the item namespace,
enforced at write time.

---

## No migrations required

All adapters already store and index the `slug` field. The repository protocol already
declares `get_category_by_slug` and `get_item_by_slug`. No storage change is needed.
