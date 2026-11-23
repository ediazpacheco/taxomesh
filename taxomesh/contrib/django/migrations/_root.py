"""What the data migrations of the implicit root share: bringing a database to the top-level invariant.

Django's migration loader skips a module whose name starts with ``_``, so this module is no migration.
Migrations ``0011`` and ``0012`` call :func:`normalise_root_links`. A change here changes what both do
on a database that has not run them yet.
"""

from typing import Final

from django.apps.registry import Apps
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from taxomesh.domain.constants import ROOT_CATEGORY_NAME

APP_LABEL: Final[str] = "taxomesh_contrib_django"


def normalise_root_links(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Delete the root links and placements the invariant forbids, and add the root links it needs.

    The invariant has two parts. A category holds a link to the implicit root, a root link, exactly
    when it holds no other parent link. No item is placed in the implicit root.

    The function deletes a root link that a category holds beside another parent link. It gives a
    category that holds no parent link a root link at sort index 0. It deletes every placement of
    an item in the implicit root. It leaves a database with no implicit root as it is. Every query
    goes to the database being migrated, the schema editor's connection.
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
