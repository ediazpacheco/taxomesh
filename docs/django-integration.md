# Django Integration

Use this when taxonomy data should live in a Django project's database, or when you want it managed
in the Django admin. Your application models stay where they are, and connect to taxomesh through
`external_id` rather than by embedding taxonomy logic in them.

## Enable the app

Add the app to `INSTALLED_APPS`, then install the `django` extra and run the migrations:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "taxomesh.contrib.django",
]
```

```bash
pip install "taxomesh[django]"
python manage.py migrate
```

## The admin

After migrating, the Django admin manages categories, items and tags (`CategoryModel`, `ItemModel`
and `TagModel`), with autocomplete foreign keys and a JSON editor for `metadata`. The editor loads
Ace from the jsDelivr CDN: a Content Security Policy must allow that host, and an admin without
access to it shows no editor. The admin also adds:

- **A graph view** of the whole taxonomy, reached from the admin index: drag and drop reorders the
  categories and items under a parent and moves them to another, and children load as a branch is
  opened. To add a sort mode, subclass `CategoryModelAdmin` and extend its `sort_modes`, a list of
  `(key, label, function)`. The function takes a list of `GraphEntry`
  (`taxomesh.contrib.django.graph_types`) and returns it in the order to show. taxomesh registers
  `CategoryModelAdmin`, which serves the graph view, so call `admin.site.unregister(CategoryModel)`,
  then `admin.site.register(CategoryModel, YourAdmin)`.
- **A debug page** of taxomesh's diagnostic information.
- **Two mixins for your own `ModelAdmin`s**, in `taxomesh.contrib.django.admin`:
  `TaxomeshLinkedFKMixin` renders every foreign key to `ItemModel` or `CategoryModel` as an
  autocomplete with a link to its taxomesh page, and `ItemCategoryAssignmentMixin` adds a
  *categories* field to a model whose primary key is an item's external id.

## Integrate with your app models

Example: mirror a Django model into taxomesh by `external_id`.

```python
# content_catalog/taxomesh_bridge.py
from functools import cache

from taxomesh import ExternalId
from taxomesh.contrib.django import get_taxomesh_service_with_django

taxomesh_service = cache(get_taxomesh_service_with_django)  # one service, built at the first call


def ensure_item_for_external_id(external_id: ExternalId, name: str) -> None:
    svc = taxomesh_service()
    if svc.items.get_by_external_id(external_id) is None:
        svc.items.create(name=name, external_id=external_id)


def delete_item_for_external_id(external_id: ExternalId) -> None:
    svc = taxomesh_service()
    item = svc.items.get_by_external_id(external_id)
    if item is not None:
        del svc.items[item]
```

A Django primary key, an `AutoField` integer or a `UUIDField`, is a valid `ExternalId` as it is:
taxomesh stores its string form ([External ids](python-api.md#external-ids)).

```python notest
# content_catalog/models.py
from uuid import uuid4
from django.db import models

from content_catalog.taxomesh_bridge import delete_item_for_external_id, ensure_item_for_external_id


class Content(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ensure_item_for_external_id(self.id, self.title)

    def delete(self, *args, **kwargs):
        delete_item_for_external_id(self.id)
        return super().delete(*args, **kwargs)
```

taxomesh does not make your model's `save` and its own write atomic together: your application
decides that. A taxomesh operation that makes several writes runs them in one transaction on the
repository's database alias, and taxomesh makes no promise about a transaction that you open.

`get_taxomesh_service_with_django(using=None)` builds a `TaxomeshService` over `DjangoRepository`,
on the database alias given, `"default"` otherwise. To wire the repository yourself, see
[Repositories](repositories.md). Building a service reads every category once, to find the implicit
root, so the bridge builds one service for each process, at its first call, and shares it.

## Logging

The [HTTP error mapping](http-api-integration.md#error-mapping) logs each 500 as an `ERROR` log
record with its traceback. This setting mails those log records to the `ADMINS`, traceback
included. An outage emits one log record for each request, so limit the rate of the emails.

```python notest
# settings.py
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"taxomesh_mail": {"class": "django.utils.log.AdminEmailHandler", "level": "ERROR"}},
    "loggers": {"taxomesh": {"handlers": ["taxomesh_mail"]}},
}
```

← [Back to README](../README.md)
