"""Migration 0011: bring every category to the top-level invariant.

A category holds a link to the implicit root exactly when it holds no other parent link, and no item
is placed in the root. This deletes a root link held beside another parent, gives a category holding
no parent link a root link at sort index 0, as ``create`` makes it, and deletes every item placement
in the root. A store that already holds the invariant is not changed. It changes the database being
migrated, as ``migrate --database`` names it.

Reverse: a no-op. The schema is unchanged, so migrating back needs no data restored.
"""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from taxomesh.domain.constants import ROOT_CATEGORY_NAME

APP_LABEL = "taxomesh_contrib_django"


def _normalise_root_links(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Delete the root links and placements the invariant forbids, and add the root links it needs.

    Every query goes to the database being migrated, the schema editor's connection.
    """
    alias = schema_editor.connection.alias
    category_model = apps.get_model(APP_LABEL, "CategoryModel")
    link_model = apps.get_model(APP_LABEL, "CategoryParentLinkModel")
    placement_model = apps.get_model(APP_LABEL, "ItemParentLinkModel")
    root = category_model.objects.using(alias).filter(name=ROOT_CATEGORY_NAME).order_by("pk").first()
    if root is None:
        return
    parented = link_model.objects.using(alias).exclude(parent_category=root).values("category_id")
    link_model.objects.using(alias).filter(parent_category=root, category_id__in=parented).delete()
    linked = link_model.objects.using(alias).values("category_id")
    unlinked = category_model.objects.using(alias).exclude(pk=root.pk).exclude(pk__in=linked)
    link_model.objects.using(alias).bulk_create(
        [link_model(category=category, parent_category=root, sort_index=0) for category in unlinked]
    )
    placement_model.objects.using(alias).filter(category=root).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0010_item_relation_link_target_type_idx"),
    ]

    operations = [
        migrations.RunPython(_normalise_root_links, reverse_code=migrations.RunPython.noop),
    ]
