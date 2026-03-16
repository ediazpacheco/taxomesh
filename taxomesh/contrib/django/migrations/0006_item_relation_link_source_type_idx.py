from django.db import migrations, models


class Migration(migrations.Migration):
    """Add composite index on (source_item_id, relation_type, sort_index, target_item_id).

    Covers:
    - Outgoing queries filtered by both source_item_id and relation_type
      (the unique_together index cannot serve this: target_item_id sits between them)
    - Batch outgoing queries (list_item_relation_links_for_sources) with optional
      relation_type__in filter
    - Full ORDER BY (source_item_id, relation_type, sort_index, target_item_id) used by
      the batch method — index scan replaces filesort
    """

    dependencies = [
        ("taxomesh_contrib_django", "0005_ordering_indexes"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="itemrelationlinkmodel",
            index=models.Index(
                fields=["source_item_id", "relation_type", "sort_index", "target_item_id"],
                name="taxomesh_rl_src_type_sort_idx",
            ),
        ),
    ]
