# Quickstart: Graph Enhancements

**Feature**: `024-graph-enhancements`

## CLI: Show Item Relations

```bash
# Default — no relations
taxomesh graph

# With outgoing item-to-item relations
taxomesh graph --show-relations
```

## Django Admin Graph

Navigate to `/admin/taxomesh_contrib_django/categorymodel/graph/`.

- Click `[-]` next to a category to collapse it; click `[+]` to expand.
- Check "Show item relations" at the top of the page to reveal outgoing item relations inline.

## Django Admin: Link Items/Categories to a Django Model

Add to your Django `settings.py`:

```python
# Must be "app_label.ModelName" format
TAXOMESH_LINKED_MODEL = "myapp.Content"
```

Any item or category whose `external_id` matches the primary key of a `myapp.Content` instance
will display a `↗` icon-link to that instance's admin change page.
Items/categories with no `external_id` show no icon.
If the model or instance cannot be resolved, the icon is silently omitted (no errors).
