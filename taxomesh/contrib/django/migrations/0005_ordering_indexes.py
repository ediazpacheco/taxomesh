from django.db import migrations, models


class Migration(migrations.Migration):
    """Add ordering indexes to support ORDER BY clauses introduced in spec 034."""

    dependencies = [
        ("taxomesh_contrib_django", "0004_external_id_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="categorymodel",
            index=models.Index(fields=["name"], name="taxomesh_category_name_idx"),
        ),
        migrations.AddIndex(
            model_name="itemmodel",
            index=models.Index(fields=["name"], name="taxomesh_item_name_idx"),
        ),
        migrations.AddIndex(
            model_name="categoryparentlinkmodel",
            index=models.Index(
                fields=["parent_category_id", "sort_index"],
                name="taxomesh_catlink_parent_sort_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="itemparentlinkmodel",
            index=models.Index(
                fields=["category_id", "sort_index"],
                name="taxomesh_itemlink_cat_sort_idx",
            ),
        ),
    ]
