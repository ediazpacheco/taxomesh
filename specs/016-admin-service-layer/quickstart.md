# Quickstart: 016-admin-service-layer

## What Changes

After this feature, the Django admin no longer talks directly to the ORM for any
mutation. Every create, update, delete, and bulk-delete goes through
`TaxomeshService`. Three new inlines appear on the admin detail pages:

- **Category detail**: `CategoryParentLink` inline — manage parent-category
  relationships with cycle detection enforced.
- **Item detail**: `ItemParentLink` inline — assign the item to categories.
- **Item detail**: `ItemTagLink` inline — assign tags to the item.

## Running Tests

```bash
# All admin-related tests
pytest tests/contrib/django/ -v

# New service-routing tests only
pytest tests/contrib/django/test_admin_service_routing.py -v

# Full quality gate
ruff check . && ruff format --check . && mypy --strict . && pytest --cov=taxomesh --cov-fail-under=80
```

## Mocking the Service in Tests

Tests that verify service routing should patch `TaxomeshService` at the import
site in the admin module:

```python
from unittest.mock import MagicMock, patch

with patch("taxomesh.contrib.django.admin.TaxomeshService") as MockService:
    mock_svc = MagicMock()
    MockService.return_value = mock_svc
    # ... perform admin request ...
    mock_svc.create_category.assert_called_once_with(name="Test", ...)
```

## Key Design Points for Implementers

1. **`_make_service()`** — each admin class (`CategoryModelAdmin`, `ItemModelAdmin`,
   `TagModelAdmin`) has a private `_make_service()` method that instantiates
   `TaxomeshService(repository=DjangoRepository())`. Called at the start of each
   mutating method.

2. **`save_model()` override** — do NOT call `super().save_model()`. Call the
   service instead. Catch `TaxomeshValidationError` and surface via
   `self.message_user(request, str(exc), level=messages.ERROR)`.

3. **`delete_model()` override** — do NOT call `obj.delete()`. Call the service
   instead. Catch `TaxomeshError` and surface via `self.message_user()`.

4. **`delete_queryset()` override** — iterate over the queryset, call service
   delete per object, collect errors, report all via `self.message_user()`.

5. **`CategoryParentLinkInline`** — uses a custom `ModelForm` whose `clean()`
   method calls `service.add_category_parent()` in a read-only probe to detect
   cycles before saving. The inline's `save_model()` then calls the service to
   actually persist.

6. **`ItemParentLinkInline` / `ItemTagLinkInline`** — validation-light inlines:
   `save_model()` calls `service.place_item_in_category()` / `service.assign_tag()`;
   `delete_model()` calls `service.remove_item_from_category()` /
   `service.remove_tag()`.
