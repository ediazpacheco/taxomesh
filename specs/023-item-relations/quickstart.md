# Quickstart: Item-to-Item Relations (023-item-relations)

**Date**: 2026-03-08

---

## What This Feature Adds

A directed, typed relation between any two items managed by taxomesh. Relations are
generic — `relation_type` is a free-form string; taxomesh enforces only that it is
non-empty. You define what the types mean in your domain.

---

## Python API

```python
from uuid import UUID
from taxomesh import TaxomeshService

service = TaxomeshService()

# Create two items
work = service.create_item(name="Symphony No. 5", slug="symphony-5")
artist = service.create_item(name="Beethoven", slug="beethoven")

# Relate them
service.relate_items(
    source_item_id=work.item_id,
    target_item_id=artist.item_id,
    relation_type="composed_by",
)

# Query outgoing relations from `work`
relations = service.list_item_relations(work.item_id)
# → [ItemRelationLink(source=work.item_id, target=artist.item_id, relation_type="composed_by")]

# Filter by relation type
relations = service.list_item_relations(work.item_id, relation_type="composed_by")

# Query incoming relations to `artist`
incoming = service.list_item_relations(artist.item_id, direction="incoming")

# Get related Item objects (not just links)
related = service.list_related_items(work.item_id)
# → [Item(name="Beethoven", ...)]

# Upsert — update sort_index for an existing relation
service.relate_items(
    source_item_id=work.item_id,
    target_item_id=artist.item_id,
    relation_type="composed_by",
    sort_index=1,
    metadata={"confidence": "high"},
)

# Remove a relation
service.remove_item_relation(
    source_item_id=work.item_id,
    target_item_id=artist.item_id,
    relation_type="composed_by",
)
```

---

## CLI

```bash
# Add a relation
taxomesh relation add <source-uuid> <target-uuid> composed_by

# List outgoing relations for an item
taxomesh relation list <item-uuid>

# List incoming relations
taxomesh relation list <item-uuid> --direction incoming

# Filter by type
taxomesh relation list <item-uuid> --type composed_by

# List related items (resolves to Item objects)
taxomesh relation related <item-uuid>
taxomesh relation related <item-uuid> --direction incoming --type performed_by

# Delete a specific relation
taxomesh relation delete <source-uuid> <target-uuid> composed_by
```

---

## Django Admin

Once the Django contrib app is installed (`taxomesh.contrib.django` in `INSTALLED_APPS`):

- **ItemRelationLinkModelAdmin** — registered at `/admin/taxomesh_contrib_django/itemrelationlinkmodel/`
  Browse, search, and filter all relations.
- **Item change page** — includes two inlines:
  - *Outgoing Relations* — editable; add/remove relations originating from this item.
  - *Incoming Relations* — read-only; shows which items point to this item.

All admin saves route through `TaxomeshService` — no direct ORM writes.
Self-relations are blocked with a clear validation error at the form level.

---

## When to Use Item Relations

| Use case | Recommended feature |
|----------|---------------------|
| Organize items into browsable groups | **Categories** (DAG hierarchy) |
| Place an item under one or more categories | **Item placement** (`place_item_in_category`) |
| Label items with keywords | **Tags** (`assign_tag`) |
| Express semantic links between items | **Item relations** (`relate_items`) ← this feature |

**Item relations** are the right choice when:
- The link carries semantic meaning beyond "belongs to group" (e.g. "composed by", "samples", "version of")
- Both ends of the link are domain items managed by taxomesh
- The direction matters (source → target)
- You want to filter or traverse by relation type

---

## Error Handling

```python
from taxomesh import TaxomeshRelationError, TaxomeshItemNotFoundError

try:
    service.relate_items(item_id, item_id, "self")  # self-relation
except TaxomeshRelationError as e:
    print(f"Relation error: {e}")

try:
    service.relate_items(item_id, missing_id, "covers")  # missing item
except TaxomeshItemNotFoundError as e:
    print(f"Item not found: {e}")
```
