# Data Model: Django Repository

**Branch**: `012-django-repository` | **Date**: 2026-02-28

---

## Overview

This feature introduces no new taxomesh domain entities. `DjangoRepository` stores the
existing domain objects (`Category`, `Item`, `Tag`, `CategoryParentLink`, `ItemParentLink`,
`ItemTagLink`) in a Django-managed relational database using six ORM models.

This document specifies the **ORM model definitions** and **database schema** for the
`taxomesh.contrib.django` app.

---

## Named Constants

All constants are defined in `taxomesh/contrib/django/models.py` (imported by
`django_repository.py`). All use `typing.Final`.

### In `taxomesh/domain/constants.py` (new — single source of truth for field constraints)

```python
from typing import Final

# Shared field length constraints — imported by both Pydantic models and Django ORM models
MAX_CATEGORY_NAME_LENGTH: Final[int] = 256
MAX_TAG_NAME_LENGTH: Final[int] = 25
MAX_DESCRIPTION_LENGTH: Final[int] = 100_000
MAX_EXTERNAL_ID_STR_LENGTH: Final[int] = 256   # Python ExternalId str type constraint
MAX_EXTERNAL_ID_DB_LENGTH: Final[int] = 512    # DB CharField width (UUID 36, int ~20, str 256)
MAX_EXTERNAL_ID_TYPE_LENGTH: Final[int] = 8    # "uuid" / "int" / "str" discriminator
```

### In `taxomesh/contrib/django/models.py` (ORM-specific constants)

```python
from typing import Final

APP_LABEL: Final[str] = "taxomesh_contrib_django"

CATEGORY_TABLE: Final[str] = "taxomesh_category"
ITEM_TABLE: Final[str] = "taxomesh_item"
TAG_TABLE: Final[str] = "taxomesh_tag"
CATEGORY_PARENT_LINK_TABLE: Final[str] = "taxomesh_category_parent_link"
ITEM_PARENT_LINK_TABLE: Final[str] = "taxomesh_item_parent_link"
ITEM_TAG_LINK_TABLE: Final[str] = "taxomesh_item_tag_link"

EXTERNAL_ID_TYPE_UUID: Final[str] = "uuid"
EXTERNAL_ID_TYPE_INT: Final[str] = "int"
EXTERNAL_ID_TYPE_STR: Final[str] = "str"
EXTERNAL_ID_TYPE_CHOICES: Final[list[tuple[str, str]]] = [
    (EXTERNAL_ID_TYPE_UUID, "UUID"),
    (EXTERNAL_ID_TYPE_INT, "Integer"),
    (EXTERNAL_ID_TYPE_STR, "String"),
]

DJANGO_REPO_USING_DEFAULT: Final[str] = "default"
```

---

## ORM Model Definitions

### CategoryModel

**Table**: `taxomesh_category`
**Domain entity**: `taxomesh.domain.models.Category`

```python
class CategoryModel(models.Model):
    category_id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=256)
    description = models.CharField(max_length=100_000, default="")
    enabled = models.BooleanField(default=True)
    external_id = models.CharField(max_length=512, default="")
    external_id_type = models.CharField(
        max_length=8, choices=EXTERNAL_ID_TYPE_CHOICES, default=EXTERNAL_ID_TYPE_STR
    )
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = CATEGORY_TABLE
```

**Notes**:
- `category_id` is a `UUIDField(primary_key=True)` — matches the domain model's `UUID` type.
- `description` defaults to `""` (not `null`) — matches `Category.description` default.
- `external_id` + `external_id_type` encode the `ExternalId` union (see research.md R-003).
- `metadata` is a `JSONField` — stores arbitrary `dict[str, Any]`.

---

### ItemModel

**Table**: `taxomesh_item`
**Domain entity**: `taxomesh.domain.models.Item`

```python
class ItemModel(models.Model):
    item_id = models.UUIDField(primary_key=True)
    external_id = models.CharField(max_length=512)
    external_id_type = models.CharField(
        max_length=8, choices=EXTERNAL_ID_TYPE_CHOICES, default=EXTERNAL_ID_TYPE_STR
    )
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_TABLE
```

---

### TagModel

**Table**: `taxomesh_tag`
**Domain entity**: `taxomesh.domain.models.Tag`

```python
class TagModel(models.Model):
    tag_id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=256)
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = TAG_TABLE
```

---

### CategoryParentLinkModel

**Table**: `taxomesh_category_parent_link`
**Domain entity**: `taxomesh.domain.models.CategoryParentLink`

```python
class CategoryParentLinkModel(models.Model):
    category = models.ForeignKey(
        CategoryModel,
        on_delete=models.CASCADE,
        related_name="parent_links",
        db_column="category_id",
    )
    parent_category = models.ForeignKey(
        CategoryModel,
        on_delete=models.CASCADE,
        related_name="child_links",
        db_column="parent_category_id",
    )
    sort_index = models.IntegerField(default=0)

    class Meta:
        app_label = APP_LABEL
        db_table = CATEGORY_PARENT_LINK_TABLE
        unique_together = [("category", "parent_category")]
```

**Notes**:
- Two FKs to `CategoryModel` (self-referential link).
- `unique_together` enforces the upsert contract — only one link per `(category, parent)` pair.
- `on_delete=CASCADE` — deleting a category removes its parent links automatically.

---

### ItemParentLinkModel

**Table**: `taxomesh_item_parent_link`
**Domain entity**: `taxomesh.domain.models.ItemParentLink`

```python
class ItemParentLinkModel(models.Model):
    item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="category_links",
        db_column="item_id",
    )
    category = models.ForeignKey(
        CategoryModel,
        on_delete=models.CASCADE,
        related_name="item_links",
        db_column="category_id",
    )
    sort_index = models.IntegerField(default=0)

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_PARENT_LINK_TABLE
        unique_together = [("item", "category")]
```

---

### ItemTagLinkModel

**Table**: `taxomesh_item_tag_link`
**Domain entity**: `taxomesh.domain.models.ItemTagLink`

```python
class ItemTagLinkModel(models.Model):
    tag = models.ForeignKey(
        TagModel,
        on_delete=models.CASCADE,
        related_name="item_links",
        db_column="tag_id",
    )
    item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="tag_links",
        db_column="item_id",
    )

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_TAG_LINK_TABLE
        unique_together = [("tag", "item")]
```

---

## Domain Entity → ORM Mapping

| Domain field | Python type | ORM field | ORM type | Notes |
|---|---|---|---|---|
| `Category.category_id` | `UUID` | `CategoryModel.category_id` | `UUIDField(primary_key=True)` | |
| `Category.name` | `str[256]` | `CategoryModel.name` | `CharField(max_length=256)` | |
| `Category.description` | `str[100000]` | `CategoryModel.description` | `CharField(max_length=100_000)` | default `""` |
| `Category.enabled` | `bool` | `CategoryModel.enabled` | `BooleanField` | default `True` |
| `Category.external_id` | `ExternalId` | `external_id` + `external_id_type` | `CharField` × 2 | type discriminator |
| `Category.metadata` | `dict[str,Any]` | `CategoryModel.metadata` | `JSONField` | |
| `Item.item_id` | `UUID` | `ItemModel.item_id` | `UUIDField(primary_key=True)` | |
| `Item.external_id` | `ExternalId` | `external_id` + `external_id_type` | `CharField` × 2 | type discriminator |
| `Item.enabled` | `bool` | `ItemModel.enabled` | `BooleanField` | |
| `Item.metadata` | `dict[str,Any]` | `ItemModel.metadata` | `JSONField` | |
| `Tag.tag_id` | `UUID` | `TagModel.tag_id` | `UUIDField(primary_key=True)` | |
| `Tag.name` | `str[256]` | `TagModel.name` | `CharField(max_length=256)` | |
| `Tag.metadata` | `dict[str,Any]` | `TagModel.metadata` | `JSONField` | |
| `CategoryParentLink.category_id` | `UUID` | `CategoryParentLinkModel.category_id` (FK) | `ForeignKey(CategoryModel)` | |
| `CategoryParentLink.parent_category_id` | `UUID` | `CategoryParentLinkModel.parent_category_id` (FK) | `ForeignKey(CategoryModel)` | |
| `CategoryParentLink.sort_index` | `int` | `CategoryParentLinkModel.sort_index` | `IntegerField` | |
| `ItemParentLink.item_id` | `UUID` | `ItemParentLinkModel.item_id` (FK) | `ForeignKey(ItemModel)` | |
| `ItemParentLink.category_id` | `UUID` | `ItemParentLinkModel.category_id` (FK) | `ForeignKey(CategoryModel)` | |
| `ItemParentLink.sort_index` | `int` | `ItemParentLinkModel.sort_index` | `IntegerField` | |
| `ItemTagLink.tag_id` | `UUID` | `ItemTagLinkModel.tag_id` (FK) | `ForeignKey(TagModel)` | |
| `ItemTagLink.item_id` | `UUID` | `ItemTagLinkModel.item_id` (FK) | `ForeignKey(ItemModel)` | |

---

## ExternalId Serialization

```python
def _serialize_external_id(value: ExternalId) -> tuple[str, str]:
    """Return (serialized_str, type_code) for an ExternalId value."""
    if isinstance(value, UUID):
        return str(value), EXTERNAL_ID_TYPE_UUID
    if isinstance(value, int):
        return str(value), EXTERNAL_ID_TYPE_INT
    return value, EXTERNAL_ID_TYPE_STR


def _deserialize_external_id(serialized: str, type_code: str) -> ExternalId:
    """Reconstruct an ExternalId from its serialized form and type discriminator."""
    if type_code == EXTERNAL_ID_TYPE_UUID:
        return UUID(serialized)
    if type_code == EXTERNAL_ID_TYPE_INT:
        return int(serialized)
    return serialized
```

These helpers are defined as module-level functions in `django_repository.py` (pure, stateless,
no side effects — appropriate as module-level per Constitution Principle XI).

---

## Validation Rules (on load from DB)

| Condition | Behaviour |
|-----------|-----------|
| Row with unknown `external_id_type` | `TaxomeshRepositoryError` raised (data corruption guard) |
| `DatabaseError` on any read/write | Caught, re-raised as `TaxomeshRepositoryError` (chained) |
| Missing row for `get_category/item/tag` | Returns `None` (Protocol contract) |
| Duplicate `(category, parent)` in link | `update_or_create` handles silently (upsert) |
