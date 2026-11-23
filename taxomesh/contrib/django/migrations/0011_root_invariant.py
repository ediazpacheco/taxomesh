"""Migration 0011: bring every category to the top-level invariant.

The invariant has two parts. A category holds a link to the implicit root, a root link, exactly when
it holds no other parent link. No item is placed in the implicit root.

The migration deletes a root link that a category holds beside another parent link. It gives a
category that holds no parent link a root link at sort index 0. It deletes every placement of an item
in the implicit root. It changes nothing in a database that already holds the invariant. It changes
the database being migrated, as ``migrate --database`` names it.

The reverse migration does nothing. This migration does not change the schema, so the reverse
migration does not need to restore data.
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
