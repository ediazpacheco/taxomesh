# taxomesh

> Flexible taxonomy management for generic items — multi-parent DAG hierarchies,
> per-parent sort indexes, free-form tags, and pluggable storage.

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

---

## What is taxomesh?

Most taxonomy libraries force your categories into a single tree. Real-world content doesn't fit a tree — a song can belong to both *Jazz* and *Argentina*, a product to both *Electronics* and *Sale Items*, a document to both *Legal* and *HR*. **taxomesh** models categories as a full **directed acyclic graph (DAG)**, so the same item or category can live in multiple places simultaneously — with an independent ordering in each context.

taxomesh is **storage-agnostic by design**. It defines a clean structural interface (`TaxomeshRepositoryBase`) that any backend can satisfy without inheriting from anything — just implement the methods and plug it in. Switch from a JSON file to SQLite to a remote database without touching a single line of your application code.

Under the hood, every write to the category graph is protected by **cycle detection at the domain layer** — a separate concern from storage, impossible to bypass, and tested independently from any backend.

---

## Key concepts

| Concept | Description                                                                                                                                                                                            |
|---|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Item** | A generic reference to any external entity. The `external_id` can be a UUID, integer, or string — taxomesh does not care what your items *are*.                                                        |
| **Category** | A named node in the taxonomy DAG. Can have zero or many parents.                                                                                                                                       |
| **Tag** | A free-form label (max 25 chars) attached to an item.                                                                                                                                                  |
| **Per-parent sort index** | Each category–parent and item–category relationship carries its own `sort_index`. *Tango* can be rank 1 under *Argentina* and rank 5 under *World Music Genres* — independently.                       |
| **Multi-parent hierarchy** | A category or item appears in every parent it is linked to. No deduplication.                                                                                                                          |
| **Taxonomy graph** | A read-only snapshot of the full taxonomy — all categories with their items and children, ready for display or processing.                                                                             |
| **Repository** | A pluggable backend that stores everything. The CLI defaults to an atomic YAML file; `JsonRepository` is also available. Bring your own for anything else. |

---

## Features

- [x] Generic item references — UUID, int, or string external ID
- [x] Category hierarchies as a full DAG (not just a tree)
- [x] Per-parent sort index — independent ordering in each parent context
- [x] Multi-parent categories and items — appear under every parent they belong to
- [x] Cycle detection in category relationships, enforced at the domain layer
- [x] Free-form tags on items with idempotent assign/remove
- [x] `get_graph()` — full taxonomy snapshot as a traversable `TaxomeshGraph` object
- [x] Pluggable repository backend via `typing.Protocol` — no inheritance required
- [x] Built-in YAML backend with atomic writes — CLI default (`taxomesh.yaml`)
- [x] Built-in JSON backend with atomic writes
- [x] First-class CLI — `taxomesh category`, `item`, `tag`, `graph`
- [x] `--verbose` flag for diagnostics (repository type, config path)
- [x] Fully typed — passes `mypy --strict` with zero suppressions
- [x] 220+ tests, ≥ 80% coverage enforced in CI
- [x] Example taxonomy in `examples/taxomesh_example.yaml`
- [ ] SQLite3 backend *(planned)*
- [ ] Query / filter capabilities *(planned)*

---

## Installation

```bash
pip install taxomesh
```

Requires **Python 3.11+**. The YAML backend (CLI default) uses `pyyaml`, which is included as a required dependency — no extras needed.

---

## Python API

### Getting started

```python
from taxomesh import TaxomeshService

service = TaxomeshService()          # auto-discovers taxomesh.toml; falls back to data/taxomesh.yaml
```

Custom storage path:

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

service = TaxomeshService(repository=JsonRepository(Path("data/taxonomy.json")))
```

---

### Categories

```python
from taxomesh import TaxomeshService, TaxomeshCategoryNotFoundError

service = TaxomeshService()

# Create
music   = service.create_category(name="Music")
jazz    = service.create_category(name="Jazz",    description="Improvisational genre.")
bossanova = service.create_category(name="Bossa Nova")

print(music.category_id)   # UUID assigned by the library

# Retrieve
same = service.get_category(music.category_id)
assert same.name == "Music"

# List all top-level categories
all_top = service.list_categories()

# Update
service.update_category(jazz.category_id, description="Improvisational, rooted in blues.")

# Delete
service.delete_category(bossanova.category_id)

# Missing entity → typed error, never None
try:
    service.get_category(bossanova.category_id)
except TaxomeshCategoryNotFoundError:
    print("not found — as expected")
```

---

### Category hierarchies (DAG)

Categories form a **directed acyclic graph**. A category can belong to multiple parents, each with its own independent `sort_index`.

```python
service = TaxomeshService()

world_music = service.create_category(name="World Music")
argentina   = service.create_category(name="Argentina")
tango       = service.create_category(name="Tango")

# Tango belongs to both World Music and Argentina
# sort_index is independent per parent: rank 1 under Argentina, rank 3 under World Music
service.add_category_parent(tango.category_id, argentina.category_id,   sort_index=1)
service.add_category_parent(tango.category_id, world_music.category_id, sort_index=3)

# Children of Argentina are returned sorted by sort_index
children = service.list_categories(parent_id=argentina.category_id)
# → [Tango]  (rank 1)

# Cycle detection — raises TaxomeshCyclicDependencyError, enforced at the domain layer
from taxomesh import TaxomeshCyclicDependencyError
try:
    service.add_category_parent(argentina.category_id, tango.category_id)
except TaxomeshCyclicDependencyError:
    print("cycle rejected")
```

---

### Items

Items carry a library-assigned internal UUID (`item_id`) and a user-supplied `external_id` that can be a UUID, integer, or string slug.

```python
from uuid import uuid4
from taxomesh import TaxomeshService

service = TaxomeshService()

song    = service.create_item(external_id=42)
article = service.create_item(external_id="how-to-brew-coffee")
product = service.create_item(external_id=uuid4())

print(song.item_id)      # internal UUID (assigned by the library)
print(song.external_id)  # 42

# Enable / disable
service.update_item(song.item_id, enabled=False)

# Retrieve
same = service.get_item(song.item_id)

# List all items
all_items = service.list_items()
```

---

### Placing items in categories (with sort order)

Items can be placed in any category. `sort_index` controls the order within that category — independently from any other category the item belongs to.

```python
service = TaxomeshService()

jazz  = service.create_category(name="Jazz")
blues = service.create_category(name="Blues")

a_love_supreme = service.create_item(external_id="a-love-supreme")
kind_of_blue   = service.create_item(external_id="kind-of-blue")
blue_train     = service.create_item(external_id="blue-train")

# Under Jazz: Kind of Blue first, A Love Supreme second
service.place_item_in_category(kind_of_blue.item_id,   jazz.category_id, sort_index=1)
service.place_item_in_category(a_love_supreme.item_id, jazz.category_id, sort_index=2)

# Under Blues: Blue Train is the opener
service.place_item_in_category(blue_train.item_id,     blues.category_id, sort_index=1)
service.place_item_in_category(a_love_supreme.item_id, blues.category_id, sort_index=2)

# Retrieve in order — each category applies its own sort_index
jazz_items  = service.list_items(category_id=jazz.category_id)
blues_items = service.list_items(category_id=blues.category_id)

print([i.external_id for i in jazz_items])
# → ['kind-of-blue', 'a-love-supreme']

print([i.external_id for i in blues_items])
# → ['blue-train', 'a-love-supreme']
```

---

### Tags

```python
service = TaxomeshService()

live      = service.create_tag(name="live")
remastered = service.create_tag(name="remastered")
song      = service.create_item(external_id=99)

# Assign — idempotent, calling it twice has no effect
service.assign_tag(tag_id=live.tag_id, item_id=song.item_id)
service.assign_tag(tag_id=live.tag_id, item_id=song.item_id)  # no-op

# Remove — no-op if the association is already gone
service.remove_tag(tag_id=live.tag_id, item_id=song.item_id)
```

---

### Taxonomy graph snapshot

`get_graph()` returns a complete read-only snapshot of the taxonomy as a tree of `CategoryNode` objects, each carrying its items (ordered by `sort_index`) and children (also ordered by `sort_index`). The internal root category is excluded automatically.

```python
from taxomesh import TaxomeshService
from taxomesh.domain.graph import TaxomeshGraph, CategoryNode

service = TaxomeshService()

world_music = service.create_category(name="World Music")
argentina   = service.create_category(name="Argentina")
tango       = service.create_category(name="Tango")
service.add_category_parent(tango.category_id, argentina.category_id, sort_index=1)

piazzolla = service.create_item(external_id="piazzolla-libertango")
coltrane  = service.create_item(external_id="coltrane-a-love-supreme")
service.place_item_in_category(piazzolla.item_id, tango.category_id, sort_index=1)
service.place_item_in_category(coltrane.item_id,  world_music.category_id, sort_index=1)

graph: TaxomeshGraph = service.get_graph()

# Walk the top-level categories
for root_node in graph.roots:
    print(root_node.category.name)
    for item in root_node.items:
        print(f"  item: {item.external_id}  (enabled={item.enabled})")
    for child in root_node.children:
        print(f"  └─ {child.category.name}")
        for item in child.items:
            print(f"       item: {item.external_id}")

# Output:
# World Music
#   item: coltrane-a-love-supreme  (enabled=True)
# Argentina
#   └─ Tango
#        item: piazzolla-libertango
```

A category with multiple explicit parents appears as a separate `CategoryNode` under each parent — the graph faithfully represents the full DAG structure.

---

### YAML backend

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

service = TaxomeshService(repository=YAMLRepository(Path("my_taxonomy.yaml")))
```

A ready-to-use example taxonomy is included in the repository:

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

repo = YAMLRepository(Path("examples/taxomesh_example.yaml"))
svc = TaxomeshService(repository=repo)
graph = svc.get_graph()
print([n.category.name for n in graph.roots])
# ['Animals', 'Plants', 'Vehicles', 'Music', 'Literature']
```

---

## Configuration

`taxomesh.toml` is optional — all settings have built-in defaults and the library works out of the box with no configuration file.

### Python API

`TaxomeshService` auto-reads `taxomesh.toml` from the current working directory when one is present. Pass an explicit path to override:

```python
from taxomesh import TaxomeshService

# No config file → falls back to YAMLRepository (data/taxomesh.yaml)
svc = TaxomeshService()

# Auto-discovers taxomesh.toml in the current working directory if present
svc = TaxomeshService()

# Explicit config file
svc = TaxomeshService(config_path="path/to/taxomesh.toml")

# Bypass config entirely — supply your own repository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
svc = TaxomeshService(repository=YAMLRepository(Path("data/taxonomy.yaml")))
```

### Config file format

```toml
# taxomesh.toml — place in your project root

# YAML backend (default)
[repository]
type = "yaml"
path = "data/taxonomy.yaml"
```

```toml
# JSON backend (alternative option)
[repository]
type = "json"
path = "data/taxonomy.json"
```

For the full, authoritative setting reference — accepted values, defaults, and both backend examples — see [`taxomesh.toml.example`](./taxomesh.toml.example) at the repository root.

---

### YAML backend

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

service = TaxomeshService(repository=YAMLRepository(Path("my_taxonomy.yaml")))
```

A ready-to-use example taxonomy is included in the repository:

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository

repo = YAMLRepository(Path("examples/taxomesh_example.yaml"))
svc = TaxomeshService(repository=repo)
graph = svc.get_graph()
print([n.category.name for n in graph.roots])
# ['Animals', 'Plants', 'Vehicles', 'Music', 'Literature']
```

---

## CLI

taxomesh ships with a full command-line interface. After installation, the `taxomesh` command is available.

### Configuration (optional)

Without a config file the CLI writes to `taxomesh.yaml` in the current directory. Create `taxomesh.toml` to customise the backend:

```toml
# taxomesh.toml — place in your project root

# YAML backend (default)
[repository]
type = "yaml"
path = "data/taxonomy.yaml"
```

```toml
# JSON backend (backward-compatible)
[repository]
type = "json"
path = "data/taxonomy.json"
```

The CLI reads `taxomesh.toml` from the current working directory automatically. Override per-invocation with `--config`:

```sh
taxomesh --config /path/to/taxomesh.toml category list
```

See [Configuration](#configuration) above for the full file format and all supported options.

---

### Categories

```sh
# Add categories
taxomesh category add --name "Music"
taxomesh category add --name "Jazz" --description "Improvisational genre"

# Add a child category under a parent (use the UUID shown after add)
taxomesh category add --name "Bebop" --parent-id <jazz-uuid>

# List top-level categories
taxomesh category list

# List children of a specific category
taxomesh category list --parent-id <jazz-uuid>

# Rename
taxomesh category update <category-uuid> --name "Jazz & Blues"

# Delete
taxomesh category delete <category-uuid>
```

---

### Items

```sh
# Add items — external ID can be an integer, a string slug, or a UUID
taxomesh item add --external-id 42
taxomesh item add --external-id "kind-of-blue"
taxomesh item add --external-id "550e8400-e29b-41d4-a716-446655440000"

# Add an item and place it in a category immediately
taxomesh item add --external-id "my-article" --category-id <category-uuid>

# Place an existing item in a category
taxomesh item add-to-category <item-uuid> --category-id <category-uuid>

# List all items
taxomesh item list

# List items in a specific category (ordered by sort_index)
taxomesh item list --category-id <category-uuid>

# Disable an item
taxomesh item update <item-uuid> --disable

# Delete
taxomesh item delete <item-uuid>
```

---

### Tags

```sh
# Create a tag
taxomesh tag add --name "live"

# Assign to an item
taxomesh item add-to-tag <item-uuid> --tag-id <tag-uuid>

# List all tags
taxomesh tag list

# Rename
taxomesh tag update <tag-uuid> --name "live-recording"

# Delete
taxomesh tag delete <tag-uuid>
```

---

### Taxonomy graph

```sh
# Render the full taxonomy as a colour-coded tree
taxomesh graph
```

```
Taxonomy
├── Music
│   ├── Jazz
│   │   ├── kind-of-blue  3f2a1c…  enabled=True
│   │   └── a-love-supreme  7b9d4e…  enabled=True
│   └── Blues
│       └── blue-train  1a2b3c…  enabled=True
└── Argentina
    └── Tango
        └── piazzolla-libertango  9e8f7a…  enabled=False
```

Each item leaf shows its `external_id`, internal `item_id` (abbreviated), and enabled status — colour-coded green/red. Categories are bold cyan.

---

### Verbose output

Any command accepts `--verbose` to print the active repository backend and config file path before the command output:

```sh
taxomesh --verbose category list
# Repository  : YAMLRepository
# Config      : taxomesh.yaml
# Config file : /home/user/project/taxomesh.toml (not found — using defaults)
# --- Categories ---
# ...
```

---

## Architecture overview

taxomesh follows a **hexagonal architecture** (ports and adapters). Dependency direction always points inward: adapters → application → domain.

```
┌────────────────────────────────────────────────────┐
│  taxomesh (public surface)                         │
│  TaxomeshService  ·  exception hierarchy           │
│  CategoryNode  ·  TaxomeshGraph  (graph snapshot)  │
└────────────────────┬───────────────────────────────┘
                     │ delegates all I/O
┌────────────────────▼───────────────────────────────┐
│  Ports  (taxomesh.ports.repository)                │
│  TaxomeshRepositoryBase  ← typing.Protocol         │
└────────────────────┬───────────────────────────────┘
                     │ satisfied structurally by
┌────────────────────▼───────────────────────────────┐
│  Adapters  (taxomesh.adapters)                     │
│  YAMLRepository  (CLI default, atomic writes)      │
│  JsonRepository  (alternative option)              │
│  … future: SqliteRepository …                     │
│                                                    │
│  CLI  (taxomesh.adapters.cli)                      │
│  category · item · tag · graph                     │
└────────────────────────────────────────────────────┘
```

`TaxomeshService` is the **sole public entry point**. It holds no storage logic whatsoever — every read and write is delegated to the injected repository.

The domain layer (`taxomesh/domain/`) has zero dependencies on storage, frameworks, or I/O. Cycle detection in the category graph runs here, in pure Python, before any write reaches the repository.

---

### Plugging in a custom backend

`TaxomeshRepositoryBase` is a `typing.Protocol` — no inheritance required. Implement its methods and pass the instance at construction time:

```python
class MyDatabaseBackend:
    def save_category(self, category): ...
    def get_category(self, category_id): ...
    # ... implement all 18 protocol methods ...

service = TaxomeshService(repository=MyDatabaseBackend())
# Everything — categories, items, tags, graph — works identically.
```

The full protocol is importable for type annotations:

```python
from taxomesh.ports.repository import TaxomeshRepositoryBase
```

---

### Repository protocol — method reference

| Group | Methods |
|---|---|
| Category CRUD | `save_category`, `get_category`, `list_categories`, `delete_category` |
| Item CRUD | `save_item`, `get_item`, `list_items`, `delete_item` |
| Tag CRUD | `save_tag`, `get_tag`, `list_tags`, `delete_tag` |
| Tag ↔ Item | `assign_tag`, `remove_tag` |
| Category parent links | `save_category_parent_link`, `list_category_parent_links` |
| Item → Category placement | `save_item_parent_link`, `list_item_parent_links` |
| Diagnostics | `get_config_summary` |

---

## Domain models

| Class | Description |
|---|---|
| `Item` | External entity reference. `item_id` (internal UUID) + `external_id` (UUID / int / str) + `enabled` flag. |
| `Category` | Named DAG node. `category_id`, `name`, optional `description`, free-form `metadata`. |
| `Tag` | Short label (max 25 chars). `tag_id`, `name`, free-form `metadata`. |
| `CategoryParentLink` | Junction linking a category to one parent, with an independent `sort_index`. |
| `ItemParentLink` | Junction placing an item under a category, with a `sort_index`. |
| `ItemTagLink` | Junction associating a tag with an item. |
| `CategoryNode` | Read-model aggregate: one category + its ordered items + its ordered children. Produced by `get_graph()`. |
| `TaxomeshGraph` | Top-level graph snapshot: list of root `CategoryNode` objects. Produced by `get_graph()`. |

All domain entities are `pydantic.BaseModel` subclasses with `validate_assignment=True`. Every `str` field carries an explicit `max_length` constraint.

---

## Error handling

All errors raised by taxomesh inherit from `TaxomeshError`. The service never returns `None` for a missing entity — every not-found condition raises a typed, catchable error.

```
TaxomeshError                          ← catch any taxomesh error
├── TaxomeshNotFoundError              ← entity does not exist
│   ├── TaxomeshCategoryNotFoundError
│   ├── TaxomeshItemNotFoundError
│   └── TaxomeshTagNotFoundError
├── TaxomeshValidationError            ← domain constraint violated
│   └── TaxomeshCyclicDependencyError  ← DAG cycle detected in add_category_parent
└── TaxomeshRepositoryError            ← storage I/O or parse failure
```

All names are importable from the top-level package:

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

---

## Roadmap

| Version | Scope |
|---|---|
| **v0.1** *(in progress)* | Core models, service facade, JSON + YAML backends, DAG cycle detection, CLI, taxonomy graph |
| **v0.2** | SQLite3 backend, bulk operations, filtering and querying |
| **v0.3** | Async repository interface, additional backends (PostgreSQL, MongoDB) |
| **v1.0** | Stable public API, documentation site, migration tooling |

---

## Spec-driven development

Every feature in taxomesh begins as a written specification before any code is written. See [`specs/`](specs/) for published design documents, data models, and interface contracts.

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request. This project follows a spec-first workflow — implementation PRs without a corresponding spec in `specs/` will not be merged.

---

## License

MIT — see [LICENSE](LICENSE).
