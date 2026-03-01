"""Django ORM models for the taxomesh contrib app.

Defines six ORM models that mirror the taxomesh domain entities:
- :class:`CategoryModel`
- :class:`ItemModel`
- :class:`TagModel`
- :class:`CategoryParentLinkModel`
- :class:`ItemParentLinkModel`
- :class:`ItemTagLinkModel`

All models carry ``Meta.app_label = APP_LABEL`` and ``Meta.db_table`` set to
the corresponding ``*_TABLE`` constant defined in this module.
"""

from typing import Final
from uuid import uuid4

from django.db import models

from taxomesh.domain.constants import (
    DEFAULT_CATEGORY_EXTERNAL_ID,
    DEFAULT_DESCRIPTION,
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_TAG_NAME_LENGTH,
)

# ---------------------------------------------------------------------------
# App-level constants
# ---------------------------------------------------------------------------

APP_LABEL: Final[str] = "taxomesh_contrib_django"
"""Django app label. Must be unique across all INSTALLED_APPS."""

CATEGORY_TABLE: Final[str] = "taxomesh_category"
ITEM_TABLE: Final[str] = "taxomesh_item"
TAG_TABLE: Final[str] = "taxomesh_tag"
CATEGORY_PARENT_LINK_TABLE: Final[str] = "taxomesh_category_parent_link"
ITEM_PARENT_LINK_TABLE: Final[str] = "taxomesh_item_parent_link"
ITEM_TAG_LINK_TABLE: Final[str] = "taxomesh_item_tag_link"

DJANGO_REPO_USING_DEFAULT: Final[str] = "default"
"""Default Django database alias used by DjangoRepository."""


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class CategoryModel(models.Model):
    """ORM representation of a taxomesh Category."""

    category_id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(max_length=MAX_CATEGORY_NAME_LENGTH)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, blank=True, default=DEFAULT_DESCRIPTION)
    enabled = models.BooleanField(default=True)
    external_id = models.CharField(
        max_length=MAX_EXTERNAL_ID_STR_LENGTH, blank=True, default=DEFAULT_CATEGORY_EXTERNAL_ID
    )
    metadata = models.JSONField(blank=True, default=dict)

    def __str__(self) -> str:
        """Return a human-readable label used in admin dropdowns."""
        return f"{self.name} ({self.category_id})"

    class Meta:
        app_label = APP_LABEL
        db_table = CATEGORY_TABLE
        verbose_name = "Category"
        verbose_name_plural = "Categories"


class ItemModel(models.Model):
    """ORM representation of a taxomesh Item."""

    item_id = models.UUIDField(primary_key=True, default=uuid4)
    external_id = models.CharField(max_length=MAX_EXTERNAL_ID_STR_LENGTH)
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_TABLE
        verbose_name = "Item"
        verbose_name_plural = "Items"


class TagModel(models.Model):
    """ORM representation of a taxomesh Tag."""

    tag_id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=MAX_TAG_NAME_LENGTH)
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = TAG_TABLE
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class CategoryParentLinkModel(models.Model):
    """ORM representation of a directed edge in the category DAG."""

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


class ItemParentLinkModel(models.Model):
    """ORM representation of an item's placement in a category."""

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


class ItemTagLinkModel(models.Model):
    """ORM representation of a tag assignment to an item."""

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


class CategoryGraphProxy(CategoryModel):
    """Proxy of CategoryModel used solely to surface the Graph link in admin."""

    class Meta:
        proxy = True
        verbose_name = "Graph"
        verbose_name_plural = " Graph"  # leading space forces top position in alphabetical app list
        app_label = APP_LABEL
