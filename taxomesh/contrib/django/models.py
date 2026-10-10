"""The Django ORM models of the taxomesh app.

The module defines seven models, one for each kind of entity and each kind of link:

- :class:`CategoryModel`
- :class:`ItemModel`
- :class:`TagModel`
- :class:`CategoryParentLinkModel`
- :class:`ItemParentLinkModel`
- :class:`ItemTagLinkModel`
- :class:`ItemRelationLinkModel`

It also defines two proxy models of ``CategoryModel``, :class:`CategoryGraphProxy` and
:class:`TaxomeshDebugProxy`, which only add entries to the admin.

Each of the seven models sets ``Meta.app_label`` to ``APP_LABEL`` and ``Meta.db_table`` to its
``*_TABLE`` constant in this module. The two proxies set ``app_label`` only, and use the table of
``CategoryModel``.
"""

from typing import Final
from uuid import uuid4

from django.db import models

from taxomesh.domain.constants import (
    AUDIT_EPOCH,
    DEFAULT_DESCRIPTION,
    MAX_CATEGORY_NAME_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_EXTERNAL_ID_STR_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_SLUG_LENGTH,
    MAX_TAG_NAME_LENGTH,
    RELATION_TYPE_MAX_LENGTH,
)

# ---------------------------------------------------------------------------
# App-level constants
# ---------------------------------------------------------------------------

APP_LABEL: Final[str] = "taxomesh_contrib_django"
"""The Django app label. It must be unique among the ``INSTALLED_APPS``."""

CATEGORY_TABLE: Final[str] = "taxomesh_category"
ITEM_TABLE: Final[str] = "taxomesh_item"
TAG_TABLE: Final[str] = "taxomesh_tag"
CATEGORY_PARENT_LINK_TABLE: Final[str] = "taxomesh_category_parent_link"
ITEM_PARENT_LINK_TABLE: Final[str] = "taxomesh_item_parent_link"
ITEM_TAG_LINK_TABLE: Final[str] = "taxomesh_item_tag_link"
ITEM_RELATION_LINK_TABLE: Final[str] = "taxomesh_item_relation_link"

DJANGO_REPO_USING_DEFAULT: Final[str] = "default"
"""The default Django database alias, ``"default"``: the same value as the default of ``DjangoRepository``."""


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class CategoryModel(models.Model):
    """The ORM model of a category."""

    category_id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(max_length=MAX_CATEGORY_NAME_LENGTH)
    description = models.CharField(max_length=MAX_DESCRIPTION_LENGTH, blank=True, default=DEFAULT_DESCRIPTION)
    enabled = models.BooleanField(default=True)
    external_id = models.CharField(
        max_length=MAX_EXTERNAL_ID_STR_LENGTH, null=True, blank=True, unique=True, default=None
    )
    slug = models.CharField(max_length=MAX_SLUG_LENGTH, blank=True, default="", db_index=True)
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(default=AUDIT_EPOCH)
    updated_at = models.DateTimeField(default=AUDIT_EPOCH)
    version = models.IntegerField(default=0)

    def __str__(self) -> str:
        """Return the label that the admin shows in its selects."""
        slug_part = f"s: {self.slug} - " if self.slug else ""
        return f"📂 {self.name} ({slug_part}id: {self.category_id})"

    class Meta:
        app_label = APP_LABEL
        db_table = CATEGORY_TABLE
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name"], name="taxomesh_category_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=~models.Q(slug=""),
                name="taxomesh_category_slug_unique_nonempty",
            )
        ]


class ItemModel(models.Model):
    """The ORM model of an item."""

    item_id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.CharField(max_length=MAX_ITEM_NAME_LENGTH, blank=True, default="")
    external_id = models.CharField(
        max_length=MAX_EXTERNAL_ID_STR_LENGTH, null=True, blank=True, unique=True, default=None
    )
    slug = models.CharField(max_length=MAX_SLUG_LENGTH, blank=True, default="", db_index=True)
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(default=AUDIT_EPOCH)
    updated_at = models.DateTimeField(default=AUDIT_EPOCH)
    version = models.IntegerField(default=0)

    def __str__(self) -> str:
        slug_part = f"s: {self.slug} - " if self.slug else ""
        return f"🏷️ {self.name} ({slug_part}id: {self.item_id})"

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_TABLE
        verbose_name = "Item"
        verbose_name_plural = "Items"
        indexes = [
            models.Index(fields=["name"], name="taxomesh_item_name_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=~models.Q(slug=""),
                name="taxomesh_item_slug_unique_nonempty",
            )
        ]


class TagModel(models.Model):
    """The ORM model of a tag."""

    tag_id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=MAX_TAG_NAME_LENGTH)
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = APP_LABEL
        db_table = TAG_TABLE
        verbose_name = "Tag"
        verbose_name_plural = "Tags"


class CategoryParentLinkModel(models.Model):
    """The ORM model of a parent link: one category under one parent."""

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
        indexes = [
            models.Index(fields=["parent_category_id", "sort_index"], name="taxomesh_catlink_par_sort_idx"),
        ]


class ItemParentLinkModel(models.Model):
    """The ORM model of a placement: one item in one category."""

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

    def __str__(self) -> str:
        return f"{self.item} → {self.category.name}"

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_PARENT_LINK_TABLE
        unique_together = [("item", "category")]
        indexes = [
            models.Index(fields=["category_id", "sort_index"], name="taxomesh_itemlink_cat_sort_idx"),
        ]


class ItemTagLinkModel(models.Model):
    """The ORM model of a tag link: one tag on one item."""

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


class ItemRelationLinkModel(models.Model):
    """The ORM model of a relation: a directed, typed link from a source item to a target item."""

    source_item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="outgoing_relation_links",
        db_column="source_item_id",
    )
    target_item = models.ForeignKey(
        ItemModel,
        on_delete=models.CASCADE,
        related_name="incoming_relation_links",
        db_column="target_item_id",
    )
    relation_type = models.CharField(max_length=RELATION_TYPE_MAX_LENGTH)
    sort_index = models.IntegerField(default=0)
    metadata = models.JSONField(blank=True, default=dict)

    def __str__(self) -> str:
        return f"{self.source_item.slug} {self.relation_type} → {self.target_item.slug} ({self.pk})"

    class Meta:
        app_label = APP_LABEL
        db_table = ITEM_RELATION_LINK_TABLE
        unique_together = [("source_item", "target_item", "relation_type")]
        indexes = [
            models.Index(
                fields=["source_item_id", "relation_type", "sort_index", "target_item_id"],
                name="taxomesh_rl_src_type_sort_idx",
            ),
            models.Index(
                fields=["target_item_id", "relation_type", "sort_index", "source_item_id"],
                name="taxomesh_rl_tgt_type_sort_idx",
            ),
        ]


class CategoryGraphProxy(CategoryModel):
    """A proxy of ``CategoryModel`` that exists only to show the Graph entry in the admin."""

    class Meta:
        proxy = True
        verbose_name = "Graph"
        verbose_name_plural = " Graph"  # the leading space puts it first in the alphabetical app list
        app_label = APP_LABEL


class TaxomeshDebugProxy(CategoryModel):
    """A proxy of ``CategoryModel`` that exists only to show the Debug page in the admin's taxomesh section."""

    class Meta:
        proxy = True
        verbose_name = "Debug"
        verbose_name_plural = "Debug"
        app_label = APP_LABEL
