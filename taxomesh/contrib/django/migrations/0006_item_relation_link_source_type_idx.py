from django.db import migrations, models


class Migration(migrations.Migration):
    """Add a composite index on (source_item_id, relation_type, sort_index, target_item_id).

    The index serves:
    - Outgoing queries filtered by both source_item_id and relation_type. The unique_together
      index cannot serve them, because target_item_id is between the two columns.
    - Batch outgoing queries (list_item_relation_links_batch, direction="outgoing") with an
      optional relation_type__in filter.
    - The full ORDER BY (source_item_id, relation_type, sort_index, target_item_id) of that
      read: an index scan replaces the filesort.
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
