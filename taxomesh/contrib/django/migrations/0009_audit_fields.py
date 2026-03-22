"""Migration 0009: Add created_at, updated_at, version audit columns to Category and Item."""

import datetime

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("taxomesh_contrib_django", "0008_unique_external_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="categorymodel",
            name="created_at",
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)),
        ),
        migrations.AddField(
            model_name="categorymodel",
            name="updated_at",
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)),
        ),
        migrations.AddField(
            model_name="categorymodel",
            name="version",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="itemmodel",
            name="created_at",
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)),
        ),
        migrations.AddField(
            model_name="itemmodel",
            name="updated_at",
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC)),
        ),
        migrations.AddField(
            model_name="itemmodel",
            name="version",
            field=models.IntegerField(default=0),
        ),
    ]
