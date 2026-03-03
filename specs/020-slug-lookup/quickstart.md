# Quickstart: Service Slug Lookup Methods (020-slug-lookup)

## Usage

```python
from taxomesh import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError

service = TaxomeshService()

# Create entities with slugs
cat = service.create_category(name="Electronics", slug="electronics")
item = service.create_item(name="Widget", external_id="w-001", slug="widget")

# Look up by slug — returns the domain object directly
category = service.get_category_by_slug("electronics")
item_obj = service.get_item_by_slug("widget")

# Not-found raises a typed exception — never returns None
try:
    service.get_category_by_slug("missing")
except TaxomeshCategoryNotFoundError:
    print("Category not found")

try:
    service.get_item_by_slug("missing")
except TaxomeshItemNotFoundError:
    print("Item not found")
```

## Notes

- Both methods are **read-only** — they do not modify any stored data.
- Results are **cached** with the same TTL as `get_category` / `get_item` and are
  invalidated automatically whenever any write operation occurs.
- Slug matching is **exact and case-sensitive**.
- Passing an empty string always raises the not-found exception (no entity is stored
  with an empty slug).
