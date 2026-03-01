# ORM Contract: External-ID Lookup (013)

## Overview

No new ORM models or migrations. This contract documents the existing ORM column contract
relied upon by the two new filter methods in `DjangoRepository`.

---

## Filter Contract: list_items_by_external_id

**Model**: `taxomesh.contrib.django.models.ItemModel`

**Filter predicate**:
```
external_id     = str(value)           # serialised via _serialize_external_id()
external_id_type = type_code           # "uuid" | "int" | "str"
```

**Type serialisation** (via `_serialize_external_id(value: ExternalId)`):

| Python type | `external_id` value | `external_id_type` value |
|---|---|---|
| `UUID` | `str(uuid)` | `"uuid"` |
| `int` | `str(n)` | `"int"` |
| `str` | `s` | `"str"` |

**Returns**: ORM queryset iterated to `list[Item]` via `_row_to_item()`.

---

## Filter Contract: list_categories_by_external_id

**Model**: `taxomesh.contrib.django.models.CategoryModel`

**Filter predicate**: same type-serialisation logic as items (above).

**Returns**: ORM queryset iterated to `list[Category]` via `_row_to_category()`.

---

## Filter Contract: assignable_categories_qs

**Model**: `taxomesh.contrib.django.models.CategoryModel`

**Filter predicate**:
```
enabled = True
name    ≠ "__root__"      # excluded via .exclude(name=ROOT_CATEGORY_NAME)
```

**Returns**: Lazy `QuerySet[CategoryModel]` — NOT converted to domain objects. Consumer
receives ORM rows directly for use in Django admin autocomplete or further queryset chaining.

**Error handling**: `DatabaseError` → `TaxomeshRepositoryError` (chained).

---

## Pre-existing columns (spec 012, no migration needed)

```
taxomesh_item:
  external_id       VARCHAR(MAX_EXTERNAL_ID_DB_LENGTH)
  external_id_type  VARCHAR(MAX_EXTERNAL_ID_TYPE_LENGTH)  CHECK IN ('uuid','int','str')

taxomesh_category:
  external_id       VARCHAR(MAX_EXTERNAL_ID_DB_LENGTH)
  external_id_type  VARCHAR(MAX_EXTERNAL_ID_TYPE_LENGTH)  CHECK IN ('uuid','int','str')
  enabled           BOOLEAN
  name              VARCHAR(MAX_CATEGORY_NAME_LENGTH)
```
