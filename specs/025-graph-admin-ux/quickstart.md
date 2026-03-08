# Quickstart: Graph & Admin UX Improvements

**Feature**: `025-graph-admin-ux`

## CLI: Depth-Limited Graph

```bash
# Default: show top 3 levels
taxomesh graph

# Show top 5 levels
taxomesh graph --max-depth 5

# Show the complete taxonomy
taxomesh graph --max-depth 0

# Show top 3 levels + outgoing relations
taxomesh graph --show-relations

# Show all levels + relations
taxomesh graph --max-depth 0 --show-relations
```

## Django Admin: Graph View

Navigate to `/admin/taxomesh_contrib_django/categorymodel/graph/`.

- Top 3 levels are shown by default.
- Items with outgoing relations show a `[+]` control — click to expand.
- No "Show item relations" toggle exists; relations are always available via `[+]`.

## Django Admin: Icon-Links in List & Detail

Add to your Django `settings.py`:

```python
TAXOMESH_LINKED_MODEL = "myapp.Content"
```

In the Item and Category admin list views, a `↗` column appears for items/categories with a
non-empty `external_id`. Clicking the icon navigates to the linked model instance's admin
change page. The same icon appears on the Item/Category detail (change) page.

## Django Admin: Version Widget

The Taxomesh section in the Django admin home automatically shows:
- The installed taxomesh version (e.g. "v0.1.0a12").
- The path to `taxomesh.toml` if found in `BASE_DIR`, or "Django ORM backend" otherwise.

No configuration needed — it's always displayed.
