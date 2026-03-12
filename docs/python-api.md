# Python API Reference

Full reference for the `TaxomeshService` Python API — categories, items, tags, graph, and slug/external-ID lookups.

## Categories

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

root = svc.create_category(name="Root Topic")
child = svc.create_category(name="Child Topic", slug="child-topic")
svc.add_category_parent(child.category_id, root.category_id, sort_index=10)

children = svc.list_categories(parent_id=root.category_id)
updated = svc.update_category(child.category_id, description="Updated")
svc.delete_category(updated.category_id)

# Look up by slug
cat = svc.get_category_by_slug("child-topic")  # raises TaxomeshCategoryNotFoundError if missing
```

## Items

```python
from uuid import uuid4

item_a = svc.create_item(name="Article", external_id=123, slug="article-123")
item_b = svc.create_item(name="Track", external_id=uuid4())
item_c = svc.create_item(name="Post", external_id="article-abc")

svc.update_item(item_a.item_id, enabled=False)
all_items = svc.list_items()

# Look up by slug
item = svc.get_item_by_slug("article-123")  # raises TaxomeshItemNotFoundError if missing
```

## Tags

```python
tag = svc.create_tag(name="featured")
svc.assign_tag(tag.tag_id, item_c.item_id)    # idempotent
svc.remove_tag(tag.tag_id, item_c.item_id)    # no-op if already removed
svc.delete_tag(tag.tag_id)
```

## Graph snapshot

```python
graph = svc.get_graph()
for node in graph.roots:
    print(node.category.name)
```

## Slug lookup

```python
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError

cat = svc.get_category_by_slug("child-topic")   # returns Category or raises TaxomeshCategoryNotFoundError
item = svc.get_item_by_slug("article-123")       # returns Item or raises TaxomeshItemNotFoundError
```

Slugs are optional URL-friendly identifiers. They must be unique within their namespace
(categories or items). Both methods raise a typed not-found exception — they never return `None`.

## External ID lookup helpers

```python
items = svc.get_items_by_external_id("article-abc")
categories = svc.get_categories_by_external_id("legacy-category-id")
```

These methods are useful for integrations where domain entities live outside taxomesh.

## Error model

All library exceptions inherit from `TaxomeshError`.

- `TaxomeshNotFoundError`
  - `TaxomeshCategoryNotFoundError`
  - `TaxomeshItemNotFoundError`
  - `TaxomeshTagNotFoundError`
- `TaxomeshValidationError`
  - `TaxomeshCyclicDependencyError`
  - `TaxomeshDuplicateSlugError`
- `TaxomeshRepositoryError`
- `TaxomeshConfigError`
- `TaxomeshRootCategoryError`

← [Back to README](../README.md)
