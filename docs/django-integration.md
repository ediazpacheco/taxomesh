# Django Integration

Use this when taxomesh should run inside a Django project database and admin.

## Enable admin-backed Django models

1. Install the Django extra (if not already installed):

```bash
pip install "taxomesh[django]"
```

2. Add the contrib app:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "taxomesh.contrib.django",
]
```

3. Run migrations:

```bash
python manage.py migrate
```

After migrating, Django admin exposes taxomesh models out of the box:
`CategoryModel`, `ItemModel`, and `TagModel`.

## Integrate with your app models

Example: mirror a Django model into taxomesh by `external_id`.

```python
# content_catalog/taxomesh_bridge.py
from taxomesh.contrib.django import get_taxomesh_service_with_django


def ensure_item_for_external_id(external_id: str) -> None:
    svc = get_taxomesh_service_with_django()
    if not svc.get_items_by_external_id(external_id):
        svc.create_item(external_id=external_id)


def delete_items_for_external_id(external_id: str) -> None:
    svc = get_taxomesh_service_with_django()
    for item in svc.get_items_by_external_id(external_id):
        svc.delete_item(item.item_id)
```

```python
# content_catalog/models.py
from uuid import uuid4
from django.db import models

from content_catalog.taxomesh_bridge import (
    delete_items_for_external_id,
    ensure_item_for_external_id,
)


class Content(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ensure_item_for_external_id(str(self.id))

    def delete(self, *args, **kwargs):
        delete_items_for_external_id(str(self.id))
        return super().delete(*args, **kwargs)
```

If you need lower-level control, use `DjangoRepository` directly (see
the [Repositories](repositories.md) reference).

← [Back to README](../README.md)
