# Quickstart: External-ID Lookup & Assignable Categories (013)

## Look up items by external ID

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

# Create an item with a consumer-owned identifier
item = svc.create_item("order-uuid-abc123")

# Later: resolve by external ID
results = svc.get_items_by_external_id("order-uuid-abc123")

if len(results) == 0:
    print("Orphan — no item registered for this external_id")
elif len(results) == 1:
    print(f"Found: item_id={results[0].item_id}")
else:
    print(f"Duplicates detected: {len(results)} items share this external_id")
```

## Look up categories by external ID

```python
from uuid import UUID
from taxomesh import TaxomeshService
from taxomesh.domain.models import Category

svc = TaxomeshService()

# Save a category with a consumer-owned external ID directly (no service method yet)
ext = UUID("12345678-1234-5678-1234-567812345678")
cat = Category(category_id=..., name="Electronics", external_id=ext)
svc.repository.save_category(cat)

# Resolve by external ID
results = svc.get_categories_by_external_id(ext)
# results[0].category_id == cat.category_id
```

## Integer and string external IDs

```python
# Integer external_id
item_int = svc.create_item(42)
assert svc.get_items_by_external_id(42) == [item_int]
assert svc.get_items_by_external_id("42") == []  # type mismatch — no cross-match
```

## Assignable categories for Django admin autocomplete

```python
# In your Django admin.py
from taxomesh.adapters.repositories.django_repository import DjangoRepository

repo = DjangoRepository()

class ItemAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = repo.assignable_categories_qs().order_by("name")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
```

The returned queryset:
- Excludes all disabled categories
- Excludes the internal `__root__` category
- Is lazy and chainable (`.filter()`, `.order_by()`, `.values()`, etc.)

## Smoke test

```python
from taxomesh import TaxomeshService
svc = TaxomeshService()
item = svc.create_item("my-entity-uuid")
results = svc.get_items_by_external_id("my-entity-uuid")
assert len(results) == 1
print("OK")
```
