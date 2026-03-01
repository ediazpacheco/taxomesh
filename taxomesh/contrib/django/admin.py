"""Django admin registrations for taxomesh ORM models."""

from django.contrib import admin

from taxomesh.contrib.django.models import (
    CategoryModel,
    ItemModel,
    TagModel,
)


@admin.register(CategoryModel)
class CategoryModelAdmin(admin.ModelAdmin):
    """Admin view for Category records."""

    list_display = ("category_id", "name", "enabled", "external_id")
    search_fields = ("name",)
    list_filter = ("enabled",)


@admin.register(ItemModel)
class ItemModelAdmin(admin.ModelAdmin):
    """Admin view for Item records."""

    list_display = ("item_id", "external_id", "enabled")
    search_fields = ()
    list_filter = ("enabled",)


@admin.register(TagModel)
class TagModelAdmin(admin.ModelAdmin):
    """Admin view for Tag records."""

    list_display = ("tag_id", "name")
    search_fields = ("name",)
