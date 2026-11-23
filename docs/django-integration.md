# Django Integration

This page says how to keep the taxonomy in the database of a Django project, and how to manage it
in the Django admin. Your models get no taxonomy fields or tables: they reach taxomesh through
`external_id`.

## Enable the app

1. Install the `django` extra. It needs Django 6.
2. Add the app to `INSTALLED_APPS`.
3. Run the migrations.

```bash
pip install "taxomesh[django]"
```

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "taxomesh.contrib.django",
]
```

```bash
python manage.py migrate
```

## Get the service

`get_taxomesh_service_with_django(using="default")`, from `taxomesh.contrib.django`, builds a
`TaxomeshService` over `DjangoRepository` on that database alias. Building a service reads every
category once, to find the [implicit root](python-api.md#the-top-level). So build one service for
each process, at its first use, and share it, as the bridge below does. The cache of a service
serves no read made inside a transaction, yours or its own. So with `ATOMIC_REQUESTS`, every read
of a view reaches the database.

Each taxomesh write runs in one transaction on the database alias of the repository. The transaction
first locks the implicit root's row, or on SQLite the whole database. So two taxomesh writes in two
workers run one after the other. Inside a transaction that you open, the lock is held until your
transaction ends, and taxomesh writes in other workers wait.

On SQLite, give the database `"OPTIONS": {"transaction_mode": "IMMEDIATE"}`. In Django's default
mode, a taxomesh write inside your transaction fails at once if your transaction has read already
and another worker writes.

## Use the admin

After the migrations, the Django admin manages categories, items and tags (`CategoryModel`,
`ItemModel` and `TagModel`), with autocomplete foreign keys. The category and item pages edit
`metadata` with a JSON editor, Ace, which loads from the jsDelivr CDN. Without access to it, as under
a strict Content Security Policy, those pages cannot edit `metadata`. The admin also adds:

- **A graph view** of the whole taxonomy. Drag and drop reorders the categories and items under a
  parent, or moves them to another parent. Children load when you open a branch.
- **A debug page** of taxomesh's diagnostic information.
- **Two mixins for your own `ModelAdmin`s**, in `taxomesh.contrib.django.admin`:
  - `TaxomeshLinkedFKMixin` shows every foreign key to `ItemModel` or `CategoryModel` as an
    autocomplete, with a link to its taxomesh page.
  - `ItemCategoryAssignmentMixin` adds a *categories* field, which offers the enabled categories, to
    a model whose primary key is the external id of an item. To use another attribute than the
    primary key, set `taxomesh_external_id_attr`. With `fields` or `fieldsets`, the page shows the
    field only where they name it. Without them, it shows the field last. A save changes placements
    only when the page shows the field. It changes no placement in a category that the field does
    not offer: a placement in a disabled category stays.

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

### Add a sort mode to the graph view

1. Subclass `CategoryModelAdmin`, and extend its `sort_modes`, a list of `(key, label, function)`.
   The function takes a list of `GraphEntry` (`taxomesh.contrib.django.graph_types`), and returns it
   in the order to show.
2. taxomesh registers `CategoryModelAdmin`, which serves the graph view. Unregister it with
   `admin.site.unregister(CategoryModel)`.
3. Register yours with `admin.site.register(CategoryModel, YourAdmin)`.

## Connect your models to items

This example keeps one item for each record of a Django model, connected by `external_id`.

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

taxomesh does not make the `save` of your model and its own write atomic together: your application
decides that. [Get the service](#get-the-service) says how a taxomesh write uses transactions.

## Send the server errors by email

The [HTTP error mapping](http-api-integration.md#error-mapping) logs each 500 as an `ERROR` log
record, with its traceback. This setting sends that log record by email to the `ADMINS`. An outage
emits one for each request.

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
