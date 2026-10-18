# Django Integration

Use this to keep taxonomy data in a Django project's database, or to manage it in the Django admin.
Your models stay as they are, with no taxonomy logic: they reach taxomesh through `external_id`.

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
and `TagModel`), with autocomplete foreign keys and a JSON editor for `metadata`, which loads Ace
from the jsDelivr CDN: without access to it, as under a strict Content Security Policy, the admin
shows no editor. The admin also adds:

- **A graph view** of the whole taxonomy: drag and drop reorders the categories and items under a
  parent and moves them to another, and children load as a branch is opened. To add a sort mode,
  subclass `CategoryModelAdmin` and extend its `sort_modes`, a list of `(key, label, function)`. The
  function takes a list of `GraphEntry` (`taxomesh.contrib.django.graph_types`) and returns it in
  the order to show. taxomesh registers `CategoryModelAdmin`, which serves the graph view, so call
  `admin.site.unregister(CategoryModel)`, then `admin.site.register(CategoryModel, YourAdmin)`.
- **A debug page** of taxomesh's diagnostic information.
- **Two mixins for your own `ModelAdmin`s**, in `taxomesh.contrib.django.admin`:
  `TaxomeshLinkedFKMixin` renders every foreign key to `ItemModel` or `CategoryModel` as an
  autocomplete with a link to its taxomesh page. `ItemCategoryAssignmentMixin` adds a *categories*
  field, which offers the enabled categories, to a model whose primary key is an item's external id.
  The page shows the field last, or where your `fields` or `fieldsets` name it. A save changes
  placements only when the page shows the field, and never in a category that the field does not
  offer, such as a disabled one.

**Permissions and URLs.** The app label is `taxomesh_contrib_django`. Under the admin's URL, the
graph is at `taxomesh_contrib_django/categorymodel/graph/` and the debug page at
`taxomesh_contrib_django/taxomeshdebugproxy/`. Every staff user can view both. A move on the graph
needs `taxomesh_contrib_django.change_categorymodel` for a category, and
`taxomesh_contrib_django.change_itemmodel` for an item. The admin index shows the app, and its graph
link, to a staff user who has a permission of the app.

**Settings.** `TAXOMESH_LINKED_MODEL` names the model of your records, as `"app_label.ModelName"`,
and the admin must register that model. A page then links a category or an item to the admin page of
the record whose primary key is its external id. `TAXOMESH_CATEGORY_LINKED_MODEL` names a model for
categories; while it is not set, categories use `TAXOMESH_LINKED_MODEL`. A page shows no link while
no setting applies to its rows.

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
decides that. Each taxomesh operation that writes runs in one transaction on the repository's
database alias, and the transaction first locks the implicit root's row, so two such operations in
two workers run one after the other. Inside a transaction that you open, the lock is held until
yours ends, and taxomesh writes in other workers wait. On SQLite, give the database `"OPTIONS":
{"transaction_mode": "IMMEDIATE"}`: in Django's default mode, a taxomesh write inside your
transaction that has read already fails at once while another worker writes.

`get_taxomesh_service_with_django(using="default")` builds a `TaxomeshService` over
`DjangoRepository` on that alias. Building a service reads every category once, to find the implicit
root, so the bridge builds one service for each process, at its first call, and shares it. Its
cache serves no read made inside a transaction, yours or its own, so with `ATOMIC_REQUESTS` every
read of a view reaches the database.

## Logging

The [HTTP error mapping](http-api-integration.md#error-mapping) logs each 500 as an `ERROR` record
with its traceback, which this setting mails to the `ADMINS`. An outage emits one for each request.

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
