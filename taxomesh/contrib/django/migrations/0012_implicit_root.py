"""Migration 0012: store the implicit root once.

The migration stores a row named ``__root__`` in a database that holds none. A database can hold
more than one. Two services that started at the same moment could leave it in that state. In such a
database, the migration keeps the row with the lowest key, which ``0011`` and every service pick.
For each other root, the migration does three things:

- It moves the child links of that root to the kept root.
- It drops a link that the kept root already holds, or that would link the kept root to itself.
- It deletes that root, and its own links and placements with it.

Then the migration brings the database to the top-level invariant, as ``0011`` does. It changes
nothing in a database that holds one root and the invariant. It changes the database being migrated,
as ``migrate --database`` names it.

Because this migration stores the implicit root, a service never has to store it on Django. So two
services that start at the same moment on a new database find the same root.

The reverse migration does nothing. This migration does not change the schema, and every database
needs the row of the implicit root.
"""

from uuid import uuid4

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from taxomesh.contrib.django.migrations._root import APP_LABEL, normalise_root_links
from taxomesh.domain.constants import ROOT_CATEGORY_NAME


def _store_one_root(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Store the implicit root, or merge every other root into the first. Then normalize the top level."""
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
