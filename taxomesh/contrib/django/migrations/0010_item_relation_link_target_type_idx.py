from django.db import migrations, models


class Migration(migrations.Migration):
    """Add composite index on (target_item_id, relation_type, sort_index, source_item_id).

    Mirror of ``taxomesh_rl_src_type_sort_idx`` (migration 0006) for the incoming
    direction. Covers:
    - Incoming queries filtered by both target_item_id and relation_type
      (the unique_together index leads with source_item_id and cannot serve this;
      the foreign-key index on target_item_id alone serves the filter but not the
      ORDER BY)
    - Batch incoming queries (list_item_relation_links_for_targets) with optional
      relation_type__in filter
    - Full ORDER BY (target_item_id, relation_type, sort_index, source_item_id) used
      by the batch method — index scan replaces filesort
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
