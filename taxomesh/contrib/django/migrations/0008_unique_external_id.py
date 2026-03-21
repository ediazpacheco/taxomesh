"""Migration 0008: Enforce 1:1 unique constraint on external_id for Item and Category.

Operations:
1. RunPython — convert external_id="" to NULL on both tables (forward only).
2. AlterField CategoryModel.external_id — null=True, unique=True, no db_index.
3. AlterField ItemModel.external_id — null=True, unique=True, no db_index.

Reverse:
1. AlterField operations revert to blank=True, no unique, db_index=True.
2. RunPython — convert NULL back to "" (best-effort; data may differ from original).
"""

from django.db import migrations, models


def _empty_to_null(apps: object, schema_editor: object) -> None:
    """Convert external_id='' to NULL on taxomesh_item and taxomesh_category."""
    from django.db import connection  # noqa: PLC0415

    with connection.cursor() as cursor:
        cursor.execute("UPDATE taxomesh_item SET external_id = NULL WHERE external_id = ''")
        cursor.execute("UPDATE taxomesh_category SET external_id = NULL WHERE external_id = ''")


def _null_to_empty(apps: object, schema_editor: object) -> None:
    """Reverse: convert NULL back to '' on taxomesh_item and taxomesh_category."""
    from django.db import connection  # noqa: PLC0415

    with connection.cursor() as cursor:
        cursor.execute("UPDATE taxomesh_item SET external_id = '' WHERE external_id IS NULL")
        cursor.execute("UPDATE taxomesh_category SET external_id = '' WHERE external_id IS NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0007_taxomeshdebugproxy"),
    ]

    operations = [
        migrations.RunPython(_empty_to_null, reverse_code=_null_to_empty),
        migrations.AlterField(
            model_name="categorymodel",
            name="external_id",
            field=models.CharField(blank=True, default=None, max_length=256, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="itemmodel",
            name="external_id",
            field=models.CharField(blank=True, default=None, max_length=256, null=True, unique=True),
        ),
    ]
