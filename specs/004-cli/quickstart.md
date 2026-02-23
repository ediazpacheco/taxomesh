# Quick Start: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)

Shell examples for all CLI commands. Each example assumes `taxomesh.json` exists in CWD
(created automatically on first use).

---

## Configuration

```toml
# taxomesh.toml (optional — place in project root)
[repository]
type = "json"
path = "data/taxonomy.json"
```

Override path per-invocation:

```sh
taxomesh --config /etc/taxomesh.toml category list
```

---

## Category commands

```sh
# Create a root category
taxomesh category add --name "Music"

# Create a category with description
taxomesh category add --name "Jazz" --description "Jazz music sub-genre"

# Create a child category (sets parent relationship atomically)
taxomesh category add --name "Bebop" --parent-id <jazz-uuid> --sort-index 1

# List all categories
taxomesh category list

# List children of a specific parent, ordered by sort_index
taxomesh category list --parent-id <music-uuid>

# Update name and/or description
taxomesh category update <uuid> --name "Modern Jazz" --description "Post-1940 jazz"

# Add a parent link to an existing category
taxomesh category update <uuid> --parent-id <music-uuid> --sort-index 2

# Delete a category
taxomesh category delete <uuid>
```

---

## Item commands

Items represent references to external entities. The `external_id` uniquely identifies
the item in the external system (integer ID, string slug, or UUID).

```sh
# Register an item by integer ID
taxomesh item add --external-id 42

# Register an item by string slug
taxomesh item add --external-id "my-article-slug"

# Register an item by UUID
taxomesh item add --external-id "550e8400-e29b-41d4-a716-446655440000"

# Register and immediately place in a category
taxomesh item add --external-id 42 --category-id <cat-uuid> --sort-index 3

# Register and immediately assign a tag
taxomesh item add --external-id 42 --tag-id <tag-uuid>

# Register with both category placement and tag assignment
taxomesh item add --external-id 42 --category-id <cat-uuid> --sort-index 1 --tag-id <tag-uuid>

# List all items
taxomesh item list

# List items in a specific category, ordered by sort_index
taxomesh item list --category-id <cat-uuid>

# Enable / disable an existing item
taxomesh item update <uuid> --enable
taxomesh item update <uuid> --disable

# Place an existing item in a category (idempotent — updates sort_index if already placed)
taxomesh item add-to-category <item-uuid> --category-id <cat-uuid> --sort-index 5

# Assign an existing tag to an existing item (idempotent)
taxomesh item add-to-tag <item-uuid> --tag-id <tag-uuid>

# Delete an item
taxomesh item delete <uuid>
```

---

## Tag commands

```sh
# Create a tag
taxomesh tag add --name "live"

# List all tags
taxomesh tag list

# Rename a tag
taxomesh tag update <uuid> --name "studio"

# Delete a tag
taxomesh tag delete <uuid>
```

---

## Error examples

```sh
# Not-found error — exits 1, message on stderr
taxomesh category delete 00000000-0000-0000-0000-000000000000
# stderr: Category not found: 00000000-0000-0000-0000-000000000000

# Validation error — exits 1
taxomesh tag add --name "this-name-is-way-too-long-for-a-tag"
# stderr: validation error ...

# Config parse error — exits 1
# (taxomesh.toml contains invalid TOML)
taxomesh category list
# stderr: Error: could not parse config file taxomesh.toml: ...
```

---

## Python API (for reference)

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

# Categories
cat = svc.create_category(name="Music", description="All music")
svc.update_category(cat.category_id, name="Music Library")

# List all categories
all_cats = svc.list_categories()

# List children of a parent, ordered by sort_index
children = svc.list_categories(parent_id=cat.category_id)

# Items
item = svc.create_item(external_id=42)
svc.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
svc.update_item(item.item_id, enabled=False)

# List items in a category, ordered by sort_index
items_in_cat = svc.list_items(category_id=cat.category_id)

# Tags
tag = svc.create_tag(name="live")
svc.assign_tag(tag.tag_id, item.item_id)
svc.update_tag(tag.tag_id, name="studio")
svc.delete_tag(tag.tag_id)
```
