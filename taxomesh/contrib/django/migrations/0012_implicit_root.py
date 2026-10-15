"""Migration 0012: store the implicit root once.

A database that holds no row named ``__root__`` gets one. A database that holds more than one, as two
services that started at the same moment could leave it, keeps the one with the lowest key, which
``0011`` and every service pick: each other root's child links move to it, a link that it already
holds or that would link it to itself is dropped, and the other root is deleted, its own links and
placements with it. Then the store
is brought to the top-level invariant, as ``0011`` brings it. A store that holds one root and the
invariant is not changed. It changes the database being migrated, as ``migrate --database`` names it.

With the root stored here, a service never has to store it on Django, so two services that start at
the same moment on a new database find the same root.

Reverse: a no-op. The schema is unchanged, and the root is a row that every store needs.
"""

from uuid import uuid4

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from taxomesh.contrib.django.migrations._root import APP_LABEL, normalise_root_links
from taxomesh.domain.constants import ROOT_CATEGORY_NAME


def _store_one_root(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Store the implicit root, or fold every other root into the first; then normalise the top level."""
    alias = schema_editor.connection.alias
    categories = apps.get_model(APP_LABEL, "CategoryModel").objects.using(alias)
    links = apps.get_model(APP_LABEL, "CategoryParentLinkModel").objects.using(alias)
    roots = list(categories.filter(name=ROOT_CATEGORY_NAME).order_by("pk"))
    if not roots:
        categories.create(category_id=uuid4(), name=ROOT_CATEGORY_NAME)
    for other in roots[1:]:
        held = links.filter(parent_category=roots[0]).values("category_id")
        moved = links.filter(parent_category=other).exclude(category_id__in=held).exclude(category=roots[0])
        moved.update(parent_category=roots[0])
        other.delete()
    normalise_root_links(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0011_root_invariant"),
    ]

    operations = [
        migrations.RunPython(_store_one_root, reverse_code=migrations.RunPython.noop),
    ]
