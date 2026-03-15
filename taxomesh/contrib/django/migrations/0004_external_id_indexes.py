from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0003_item_relation_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="categorymodel",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=256),
        ),
        migrations.AlterField(
            model_name="itemmodel",
            name="external_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=256),
        ),
    ]
