# taxomesh

> Flexible taxonomy management for generic items — categories, tags, and multi-parent hierarchies with pluggable storage.

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## What is taxomesh?

**taxomesh** is a Python library for organizing arbitrary items into flexible taxonomies. An "item" is any entity identified by a UUID, integer, or string — a product, a document, a user, a media file — anything. taxomesh doesn't care what your items *are*; it just manages how they are **categorized and tagged**.

### Key concepts

| Concept | Description |
|---|---|
| **Item** | A generic reference (UUID / int / str) to any external entity |
| **Category** | A named node in a taxonomy graph |
| **Tag** | A free-form label attached to an item |
| **Multi-parent hierarchy** | A category can belong to *multiple* parent categories simultaneously |
| **Sort index** | A category's position within each parent is independent — "Tango" can be rank 1 under "Argentina" and rank 5 under "World Music Genres" |
| **Repository** | A pluggable backend that stores all of the above |

### Multi-parent categories with per-parent sort index

Unlike traditional single-parent trees, taxomesh models categories as a **directed acyclic graph (DAG)**. The relationship between a category and each of its parents carries an independent `sort_index`, stored in a dedicated junction record:

```
(category_id, parent_category_id, sort_index)
```

This lets the same category appear at different positions depending on which parent context is being browsed. Cyclic dependencies are detected and rejected at write time.

---

## Features

- [x] Generic item references (UUID, int, or str)
- [x] Categories organized as a DAG (directed acyclic graph)
- [x] Per-parent sort index for categories
- [x] Cycle detection in category hierarchies
- [x] Free-form tags on items with idempotent assign/remove
- [x] Pluggable repository interface (`TaxomeshRepositoryBase`) — no inheritance required
- [x] Built-in JSON repository backend with atomic writes
- [x] Typed exception hierarchy for precise error handling
- [ ] YAML file backend *(planned)*
- [ ] SQLite3 backend *(planned)*
- [ ] Query/search capabilities *(planned)*

---

## Installation

```bash
pip install taxomesh
```

Requires Python 3.11 or later. No extra dependencies needed for the default JSON backend.

---

## Quick start

### Default storage (JSON file in current directory)

```python
from taxomesh import TaxomeshService

service = TaxomeshService()  # persists to taxomesh.json
```

### Custom storage path

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

service = TaxomeshService(repository=JsonRepository(Path("/data/my_taxonomy.json")))
```

### Managing categories

```python
from taxomesh import TaxomeshService, TaxomeshCategoryNotFoundError

service = TaxomeshService()

# Create
music = service.create_category(name="Music")
jazz  = service.create_category(name="Jazz", description="Improvisational genre.")
print(music.category_id)   # UUID assigned by the library

# Retrieve
same = service.get_category(music.category_id)
assert same.name == "Music"

# List
all_cats = service.list_categories()

# Delete
service.delete_category(jazz.category_id)

# Missing entity raises a typed error — never returns None
try:
    service.get_category(jazz.category_id)
except TaxomeshCategoryNotFoundError as e:
    print(e)
```

### Category parent relationships (DAG)

```python
animals  = service.create_category(name="Animals")
mammals  = service.create_category(name="Mammals")
dogs     = service.create_category(name="Dogs")

service.add_category_parent(mammals.category_id, animals.category_id)
service.add_category_parent(dogs.category_id,    mammals.category_id)

# Cycle detection — raises TaxomeshCyclicDependencyError
from taxomesh import TaxomeshCyclicDependencyError
try:
    service.add_category_parent(animals.category_id, dogs.category_id)
except TaxomeshCyclicDependencyError:
    print("cycle rejected")
```

### Managing items

```python
from uuid import uuid4
from taxomesh import TaxomeshService

service = TaxomeshService()

# External ID can be UUID, int, or string slug
song    = service.create_item(external_id=42)
article = service.create_item(external_id="how-to-brew-coffee")
product = service.create_item(external_id=uuid4())

print(song.item_id)      # library-assigned internal UUID
print(song.external_id)  # 42

# Retrieve by internal UUID
same = service.get_item(song.item_id)
all_items = service.list_items()
service.delete_item(song.item_id)
```

### Managing tags

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

live_tag = service.create_tag(name="live")
song     = service.create_item(external_id=99)

# Assign — idempotent, safe to call multiple times
service.assign_tag(tag_id=live_tag.tag_id, item_id=song.item_id)
service.assign_tag(tag_id=live_tag.tag_id, item_id=song.item_id)  # no-op

# Remove — no-op if association already absent
service.remove_tag(tag_id=live_tag.tag_id, item_id=song.item_id)
```

### Persistence across restarts

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

DB = Path("my_taxonomy.json")

# First run — write data
s1 = TaxomeshService(repository=JsonRepository(DB))
cat = s1.create_category(name="Electronic")

# Later run — data survives process restart
s2 = TaxomeshService(repository=JsonRepository(DB))
same = s2.get_category(cat.category_id)
assert same.name == "Electronic"
```

---

## Architecture overview

```
┌─────────────────────────────────────────────────────┐
│  Public import surface  (taxomesh)                  │
│  TaxomeshService · exception classes                │
└───────────────────┬─────────────────────────────────┘
                    │ delegates all I/O
┌───────────────────▼─────────────────────────────────┐
│  Ports  (taxomesh.ports.repository)                 │
│  TaxomeshRepositoryBase  ← typing.Protocol          │
└───────────────────┬─────────────────────────────────┘
                    │ satisfied by
┌───────────────────▼─────────────────────────────────┐
│  Adapters  (taxomesh.adapters.repositories)         │
│  JsonRepository  (default, atomic writes)           │
│  … future: YamlRepository, SqliteRepository …      │
└─────────────────────────────────────────────────────┘
```

`TaxomeshService` is the **sole public entry point**. It holds no storage logic and delegates every read and write to the repository backend. Any object that structurally satisfies `TaxomeshRepositoryBase` can be used — no inheritance required.

### Repository interface

`TaxomeshRepositoryBase` is a `typing.Protocol` with 15 methods:

| Group | Methods |
|---|---|
| Category CRUD | `save_category`, `get_category`, `list_categories`, `delete_category` |
| Item CRUD | `save_item`, `get_item`, `list_items`, `delete_item` |
| Tag CRUD | `save_tag`, `get_tag`, `list_tags` |
| Tag ↔ Item association | `assign_tag`, `remove_tag` |
| Category parent links | `save_category_parent_link`, `list_category_parent_links` |

Import path for advanced use (e.g., type annotations on a custom backend):

```python
from taxomesh.ports.repository import TaxomeshRepositoryBase
```

### Plugging in a custom backend

No inheritance from `TaxomeshRepositoryBase` is required. Implement all 15 methods and pass the instance at construction time:

```python
from taxomesh import TaxomeshService

service = TaxomeshService(repository=MyCustomBackend())
```

---

## Domain models

taxomesh defines its domain model classes in `taxomesh/domain/models.py`:

| Class | Description |
|---|---|
| **`Item`** | A generic reference to any external entity, identified by an auto-generated UUID (`item_id`) and a user-supplied `external_id` (UUID, str, or int) |
| **`Category`** | A named node in the taxonomy DAG, with an optional description and metadata |
| **`Tag`** | A short free-form label (max 25 chars) that can be attached to items |
| **`CategoryParentLink`** | Junction record linking a category to one of its parent categories, with an independent `sort_index` |
| **`ItemParentLink`** | Junction record placing an item under a category, with a sort index |
| **`ItemTagLink`** | Junction record associating a tag with an item |

All models are `pydantic.BaseModel` subclasses with `populate_by_name=True` and `validate_assignment=True`. Every direct `str` field carries an explicit `max_length` constraint.

---

## Error handling

All errors raised by taxomesh inherit from `TaxomeshError`:

```
TaxomeshError                          ← catch-all for any taxomesh error
├── TaxomeshNotFoundError              ← any entity not found
│   ├── TaxomeshCategoryNotFoundError
│   ├── TaxomeshItemNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError            ← domain constraint violation
│   └── TaxomeshCyclicDependencyError  ← DAG cycle in add_category_parent
└── TaxomeshRepositoryError            ← storage I/O / parse failure
```

All names are importable from the top-level `taxomesh` package:

```python
from taxomesh import (
    TaxomeshService,
    TaxomeshError,
    TaxomeshNotFoundError,
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
    TaxomeshCyclicDependencyError,
    TaxomeshRepositoryError,
)
```

The service never returns `None` for a missing entity. Every not-found condition raises a specific, catchable typed error.

---

## Roadmap

- **v0.1** — Core models, service facade, `TaxomeshRepositoryBase`, JSON backend, DAG cycle detection *(in progress)*
- **v0.2** — YAML and SQLite3 backends, bulk operations, filtering and querying
- **v0.3** — Async repository interface, additional backends (PostgreSQL, MongoDB)
- **v1.0** — Stable API, full test coverage, documentation site

---

## Spec-driven development

This project is built using **spec-driven development**. Every feature begins as a written specification before any code is touched. See [`specs/`](specs/) for published specifications.

---

## Contributing

Contributions are welcome. Please open an issue to discuss any change before submitting a pull request. This project follows a spec-first workflow — implementation PRs without a corresponding spec will not be merged.

---

## License

MIT — see [LICENSE](LICENSE).
