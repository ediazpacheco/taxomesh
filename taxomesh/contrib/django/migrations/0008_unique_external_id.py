"""Migration 0008: Enforce 1:1 unique constraint on external_id for Item and Category.

Operations:
1. AlterField CategoryModel.external_id and ItemModel.external_id — null=True, so the column takes NULL.
2. RunPython — convert external_id="" to NULL on both tables.
3. AlterField CategoryModel.external_id and ItemModel.external_id — unique=True, no db_index.

Reverse, in the opposite order:
1. AlterField operations drop the unique constraint.
2. RunPython — convert NULL back to "" (best-effort; data may differ from original).
3. AlterField operations revert to blank=True, not null, db_index=True.

The data steps run on the database being migrated, the schema editor's connection.
"""

from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def _empty_to_null(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Convert external_id='' to NULL on taxomesh_item and taxomesh_category."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("UPDATE taxomesh_item SET external_id = NULL WHERE external_id = ''")
        cursor.execute("UPDATE taxomesh_category SET external_id = NULL WHERE external_id = ''")


def _null_to_empty(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Reverse: convert NULL back to '' on taxomesh_item and taxomesh_category."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("UPDATE taxomesh_item SET external_id = '' WHERE external_id IS NULL")
        cursor.execute("UPDATE taxomesh_category SET external_id = '' WHERE external_id IS NULL")


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0007_taxomeshdebugproxy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="categorymodel",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=256, null=True),
        ),
        migrations.AlterField(
            model_name="itemmodel",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=256, null=True),
        ),
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
