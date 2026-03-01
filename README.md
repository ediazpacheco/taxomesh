# taxomesh

Flexible taxonomy management for generic items with:

- multi-parent category DAGs
- per-parent sort ordering
- free-form item tags
- pluggable storage backends (YAML, JSON, Django)

`taxomesh` is **storage-agnostic by design**.

Switch from a JSON file to Django-backed storage or a custom remote backend
without touching a single line of your application code.

The goal of this library is to avoid re-implementing common taxonomy workflows
and provide a plug-and-play component for your application.

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Pre-Alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)]()

## Status

`taxomesh` is currently **pre-alpha** (`0.1.x`).
API and behavior can still change between releases.

## Installation

Requires **Python 3.11+**.

```bash
pip install taxomesh
```

Optional Django integration:

```bash
pip install "taxomesh[django]"
```

## Quick start

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()  # auto-discovers taxomesh.toml, else defaults to YAMLRepository(data/taxomesh.yaml)

music = svc.create_category(name="Music")
jazz = svc.create_category(name="Jazz")
svc.add_category_parent(jazz.category_id, music.category_id, sort_index=1)

kind_of_blue = svc.create_item(external_id=42)
svc.place_item_in_category(kind_of_blue.item_id, jazz.category_id, sort_index=1)

print(kind_of_blue.external_id)  # "42" (normalized to str)
print([node.category.name for node in svc.get_graph().roots])
```

## Core concepts

- **Item**: external entity reference with internal `item_id` and normalized string `external_id`
- **Category**: taxonomy node with optional `description`, `metadata`, `external_id`, and `enabled`
- **Tag**: free-form item label
- **CategoryParentLink**: relation from category to parent category with `sort_index`
- **ItemParentLink**: relation from item to category with `sort_index`
- **TaxomeshGraph**: read snapshot returned by `get_graph()` for tree-like traversal
- **Repository protocol**: `TaxomeshRepositoryBase` (`typing.Protocol`) defines the storage contract

## Django integration

Use this when taxomesh should run inside a Django project database and admin.

### Enable admin-backed Django models

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

### Integrate with your app models

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
the **Repositories** section below).

## Python API

### Categories

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

root = svc.create_category(name="Root Topic")
child = svc.create_category(name="Child Topic")
svc.add_category_parent(child.category_id, root.category_id, sort_index=10)

children = svc.list_categories(parent_id=root.category_id)
updated = svc.update_category(child.category_id, description="Updated")
svc.delete_category(updated.category_id)
```

### Items

```python
from uuid import uuid4

item_a = svc.create_item(external_id=123)
item_b = svc.create_item(external_id=uuid4())
item_c = svc.create_item(external_id="article-abc")

svc.update_item(item_a.item_id, enabled=False)
all_items = svc.list_items()
```

### Tags

```python
tag = svc.create_tag(name="featured")
svc.assign_tag(tag.tag_id, item_c.item_id)    # idempotent
svc.remove_tag(tag.tag_id, item_c.item_id)    # no-op if already removed
svc.delete_tag(tag.tag_id)
```

### Graph snapshot

```python
graph = svc.get_graph()
for node in graph.roots:
    print(node.category.name)
```

### External ID lookup helpers

```python
items = svc.get_items_by_external_id("article-abc")
categories = svc.get_categories_by_external_id("legacy-category-id")
```

These methods are useful for integrations where domain entities live outside taxomesh.

## Repositories

Any class implementing `TaxomeshRepositoryBase` can be used.
`TaxomeshRepositoryBase` is defined as a `typing.Protocol`.
No inheritance is required (structural typing / protocol-based compatibility).

### YAMLRepository

Default backend when no repository is configured.
Uses atomic writes.

```python
from pathlib import Path
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

svc = TaxomeshService(repository=YAMLRepository(Path("data/taxomesh.yaml")))
```

### JsonRepository

File-backed JSON backend with atomic writes.

```python
from pathlib import Path
from taxomesh.adapters.repositories.json_repository import JsonRepository

svc = TaxomeshService(repository=JsonRepository(Path("data/taxomesh.json")))
```

### DjangoRepository

ORM-backed backend for Django projects.
If Django integration is already configured (see **Django integration** above),
use `DjangoRepository` directly when you want explicit repository wiring:

```python
from taxomesh.adapters.repositories.django_repository import DjangoRepository

svc = TaxomeshService(repository=DjangoRepository())
```

## Configuration (`taxomesh.toml`)

`taxomesh.toml` is optional.
If present, `TaxomeshService()` reads it from the current working directory.

YAML:

```toml
[repository]
type = "yaml"
path = "data/taxomesh.yaml"
```

JSON:

```toml
[repository]
type = "json"
path = "data/taxomesh.json"
```

Django:

```toml
[repository]
type = "django"
using = "default"
```

See also: [`taxomesh.toml.example`](./taxomesh.toml.example)

## CLI

After installation, the `taxomesh` command is available.

### Common commands

```bash
# Categories
taxomesh category add --name "Music"
taxomesh category list
taxomesh category update <category-uuid> --name "World Music"
taxomesh category delete <category-uuid>

# Items
taxomesh item add --external-id "kind-of-blue"
taxomesh item add-to-category <item-uuid> --category-id <category-uuid>
taxomesh item list --category-id <category-uuid>
taxomesh item update <item-uuid> --disable
taxomesh item delete <item-uuid>

# Tags
taxomesh tag add --name "classic"
taxomesh item add-to-tag <item-uuid> --tag-id <tag-uuid>
taxomesh tag list

# Graph
taxomesh graph
```

Example output:

```text
Taxonomy
└── Music  11111111-1111-1111-1111-111111111111  ✓
    └── Jazz  22222222-2222-2222-2222-222222222222  ✓
        └── kind-of-blue  33333333-3333-3333-3333-333333333333  ✓
```

Verbose diagnostics:

```bash
taxomesh --verbose category list
```

## Error model

All library exceptions inherit from `TaxomeshError`.

- `TaxomeshNotFoundError`
  - `TaxomeshCategoryNotFoundError`
  - `TaxomeshItemNotFoundError`
  - `TaxomeshTagNotFoundError`
- `TaxomeshValidationError`
  - `TaxomeshCyclicDependencyError`
- `TaxomeshRepositoryError`
- `TaxomeshConfigError`
- `TaxomeshRootCategoryError`

## Architecture

`taxomesh` uses a ports-and-adapters (hexagonal) shape:

- **Domain**: pure models and DAG validation
- **Application**: `TaxomeshService` orchestration
- **Ports**: repository protocol (`TaxomeshRepositoryBase`)
- **Adapters**: YAML/JSON/Django repositories + CLI

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy .
```

## Contributing

Contributions are welcome.
This project follows a spec-first workflow. Please align implementation PRs with the `specs/` directory.

## License

MIT. See [LICENSE](LICENSE).
