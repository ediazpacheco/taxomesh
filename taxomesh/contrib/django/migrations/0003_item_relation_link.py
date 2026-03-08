import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0002_alter_itemmodel_external_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemRelationLinkModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_item",
                    models.ForeignKey(
                        db_column="source_item_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_relation_links",
                        to="taxomesh_contrib_django.itemmodel",
                    ),
                ),
                (
                    "target_item",
                    models.ForeignKey(
                        db_column="target_item_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_relation_links",
                        to="taxomesh_contrib_django.itemmodel",
                    ),
                ),
                ("relation_type", models.CharField(max_length=256)),
                ("sort_index", models.IntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "db_table": "taxomesh_item_relation_link",
                "app_label": "taxomesh_contrib_django",
                "unique_together": {("source_item", "target_item", "relation_type")},
            },
        ),
    ]
