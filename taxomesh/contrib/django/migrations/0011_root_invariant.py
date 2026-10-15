"""Migration 0011: bring every category to the top-level invariant.

A category holds a link to the implicit root exactly when it holds no other parent link, and no item
is placed in the root. This deletes a root link held beside another parent, gives a category holding
no parent link a root link at sort index 0, as ``create`` makes it, and deletes every item placement
in the root. A store that already holds the invariant is not changed. It changes the database being
migrated, as ``migrate --database`` names it.

Reverse: a no-op. The schema is unchanged, so migrating back needs no data restored.
"""

from django.db import migrations

from taxomesh.contrib.django.migrations._root import normalise_root_links


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0010_item_relation_link_target_type_idx"),
    ]

    operations = [
        migrations.RunPython(normalise_root_links, reverse_code=migrations.RunPython.noop),
    ]
