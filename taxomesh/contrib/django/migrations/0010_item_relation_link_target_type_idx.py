from django.db import migrations, models


class Migration(migrations.Migration):
    """Add a composite index on (target_item_id, relation_type, sort_index, source_item_id).

    It is the index ``taxomesh_rl_src_type_sort_idx`` (migration 0006) with the two item columns
    exchanged, for the incoming direction. The index serves:
    - Incoming queries filtered by both target_item_id and relation_type. The unique_together
      index starts with source_item_id and cannot serve them. The foreign-key index on
      target_item_id alone serves the filter but not the ORDER BY.
    - Batch incoming queries (list_item_relation_links_batch, direction="incoming") with an
      optional relation_type__in filter.
    - The full ORDER BY (target_item_id, relation_type, sort_index, source_item_id) of that
      read: an index scan replaces the filesort.
    """

    dependencies = [
        ("taxomesh_contrib_django", "0009_audit_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="itemrelationlinkmodel",
            index=models.Index(
                fields=["target_item_id", "relation_type", "sort_index", "source_item_id"],
                name="taxomesh_rl_tgt_type_sort_idx",
            ),
        ),
    ]
