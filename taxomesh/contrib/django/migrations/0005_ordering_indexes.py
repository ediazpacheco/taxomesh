from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the indexes the listings' ORDER BY clauses use: names, and links by sort index."""

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
                name="taxomesh_catlink_par_sort_idx",
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
