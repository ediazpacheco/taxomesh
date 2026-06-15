# taxomesh

**A reusable taxonomy engine for entities you already have — multi-parent category DAGs, ordered placements, tags, typed relations, and fuzzy search, behind one typed service API with pluggable storage.**

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Typed](https://img.shields.io/badge/types-mypy--strict-blue.svg)](https://github.com/ediazpacheco/taxomesh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE)

`taxomesh` adds a serious taxonomy layer on top of business objects that already
live elsewhere — products, articles, tracks, assets. Your entities stay in your
system and are referenced by a unique `external_id`; `taxomesh` owns the structure
around them: category graphs, placement, ordering, tags, relations, and traversal.
The same rules and errors apply whether you reach it from Python, the CLI, the
Django admin, or your own HTTP API.

## Highlights

- **Multi-parent category DAGs** — categories form a directed acyclic graph, not a strict tree; cycle creation is rejected with a typed error
- **Per-parent ordering** — every category-to-parent and item-to-category link carries its own `sort_index`; reorder and reparent operations are first-class
- **External-ID binding** — link records 1:1 to your existing entities; point and bulk lookups; uniqueness enforced across all backends
- **Tags and typed item relations** — free-form tags plus directed, typed item-to-item links (`covers`, `version_of`, …) with incoming/outgoing traversal
- **Fuzzy search** — typo-tolerant, accent-insensitive, ranked search over names, slugs, and external IDs; no extra infrastructure
- **Graph snapshots** — `get_graph()` returns an immutable, ordered view of the whole taxonomy for rendering and traversal
- **Pluggable storage** — YAML, JSON, and Django ORM backends behind one repository interface; bring your own by implementing the same port
- **Batteries-included integrations** — `taxomesh` CLI, Django admin (interactive graph view, drag-and-drop ordering), and framework-agnostic HTTP handlers/schemas
- **Typed everywhere** — Pydantic v2 domain models, a complete exception hierarchy rooted at `TaxomeshError`, `mypy --strict` clean, `py.typed` shipped

## Installation

Requires **Python 3.11+**.

```bash
pip install taxomesh
```

With the optional Django integration (ORM backend + admin):

```bash
pip install "taxomesh[django]"
```

## Quick start

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()  # auto-discovers taxomesh.toml; defaults to a YAML file backend

# Build a category DAG — "Jazz" sits under both "Music" and "Genres"
music = svc.create_category(name="Music")
genres = svc.create_category(name="Genres")
jazz = svc.create_category(name="Jazz")
svc.add_category_parent(jazz.category_id, music.category_id, sort_index=10)
svc.add_category_parent(jazz.category_id, genres.category_id, sort_index=5)

# Reference an entity that lives in your own system
album = svc.create_item(name="Kind of Blue", external_id="catalog:42", slug="kind-of-blue")
svc.place_item_in_category(album.item_id, jazz.category_id, sort_index=1)

# Tag it
featured = svc.create_tag(name="featured")
svc.assign_tag(featured.tag_id, album.item_id)

# Traverse
print([node.category.name for node in svc.get_graph().roots])
# ['Music', 'Genres']
print([c.name for c in svc.list_categories_by_item(album.item_id)])
# ['Jazz']
```

Your entity remains the source of truth in your application. `taxomesh` manages
the taxonomy around it and hands it back to you by `external_id`.

## Capabilities

### Multi-parent categories with per-parent ordering

A category may have any number of parents, and its position is independent per
parent. Cycles are rejected at write time.

```python
from taxomesh import TaxomeshCyclicDependencyError

svc.add_category_parent(jazz.category_id, music.category_id, sort_index=10)

try:
    svc.add_category_parent(music.category_id, jazz.category_id)
except TaxomeshCyclicDependencyError:
    ...  # the DAG invariant is enforced, not assumed
```

Ordering is mutable after the fact:

```python
svc.reorder_subcategories(music.category_id, [jazz.category_id, blues.category_id])
svc.reorder_items_in_category(jazz.category_id, [album_b.item_id, album_a.item_id])
```

### Binding to your entities via `external_id`

`external_id` is unique per record (`str | None`); it is the bridge between a
taxomesh record and the entity it represents in your system.

```python
item = svc.get_item_by_external_id("catalog:42")          # Item | None
found = svc.get_items_by_external_ids(["catalog:42", "catalog:7"])
# {'catalog:42': Item(...), 'catalog:7': Item(...)} — missing IDs are simply absent
```

Conflicts are typed errors, not silent overwrites:

```python
from taxomesh import TaxomeshExternalIdConflictError

try:
    svc.create_item(name="Duplicate", external_id="catalog:42")
except TaxomeshExternalIdConflictError:
    ...
```

### Typed item-to-item relations

Directed, typed links between items, traversable in both directions:

```python
svc.relate_items(cover.item_id, original.item_id, relation_type="covers")

svc.list_related_items(cover.item_id, relation_type="covers")
# [Item(name='Original', ...)]                      — outgoing by default
svc.list_related_items(original.item_id, direction="incoming")
# [Item(name='Cover', ...)]                          — who points at me?
svc.list_related_items(original.item_id, direction="both")
# [Item(name='Cover', ...), ...]                     — every item linked in either direction
```

Use `direction="both"` when an item can sit on *either* end of its links — i.e. it
is the **source** of some relations but the **target** of others. `"outgoing"`
(the default) would miss the incoming links entirely. `list_item_relations(...,
direction="both")` returns each link at most once; a bidirectional relation stored
as two rows (`A→B` and `B→A`) still yields two distinct links, one per direction.
Relation type values (`covers`, `version_of`, …) are opaque to taxomesh — the
consuming application defines its own vocabulary.

### Fuzzy search

Typo-tolerant, accent-insensitive, ranked (exact > prefix > substring > fuzzy).
Optimized for per-keystroke autocomplete usage out of the box.

```python
svc.search_items("piazola")                    # finds "Piazzolla"
svc.search_items("agustin magaldi")            # finds "Agustín Magaldi"
svc.search_items("tango", category_id=cat.category_id, recursive=True)  # subtree-scoped
svc.search_categories("orquesta", parent_id=parent.category_id)         # children of one parent
```

Pass `fuzzy=False` for exact/prefix/substring only. See
[Python API — Fuzzy Search](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md#fuzzy-search)
for the full parameter reference and caching behavior.

### Graph snapshots

`get_graph()` returns a `TaxomeshGraph` — an ordered, read-only view of the
entire taxonomy, ready for rendering or serialization:

```python
graph = svc.get_graph()           # enabled records only; pass enabled=None for all
for root in graph.roots:          # roots and children are sorted by sort_index
    print(root.category.name, [child.category.name for child in root.children])
```

### Pluggable storage

All backends implement the same repository port; service behavior, validation,
and errors are identical across them.

```python
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.adapters.repositories.json_repository import JsonRepository

svc = TaxomeshService(YAMLRepository("data/catalog.yaml"))   # single YAML file, atomic writes
svc = TaxomeshService(JsonRepository("data/catalog.json"))   # single JSON file, atomic writes
```

With the `django` extra, `DjangoRepository` stores everything in the Django ORM
(SQLite/PostgreSQL). Custom backends implement `TaxomeshRepositoryBase`. Backend
selection can also be driven by a `taxomesh.toml` file — see
[Configuration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/configuration.md).

### Command-line interface

The `taxomesh` CLI exposes the same service against the configured backend:

```bash
taxomesh category add "Music"
taxomesh item add "Kind of Blue" --external-id catalog:42
taxomesh item add-to-category <item-uuid> <category-uuid>
taxomesh item relation add <source-uuid> <target-uuid> covers
taxomesh graph        # Rich-rendered taxonomy tree
```

See the [CLI reference](https://github.com/ediazpacheco/taxomesh/blob/main/docs/cli.md).

### Django admin

The optional Django integration ships a full admin: category/item/tag management,
an interactive graph view with drag-and-drop reordering and reparenting, lazy
child loading, pluggable sort modes, autocomplete foreign keys, and a JSON editor
for metadata fields.

See [Django integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/django-integration.md).

### HTTP API building blocks

`taxomesh.contrib.api` provides framework-agnostic request schemas (Pydantic),
handler functions, serializers, and error-to-status mapping, so the taxonomy can
be exposed from FastAPI, Django views, or any other stack without re-implementing
validation:

```python
from taxomesh.contrib.api import handlers, schemas, serializers

body = schemas.CreateCategoryRequest(name="Music")
category = handlers.create_category(svc, body)
payload = serializers.categories_to_list([category])
```

See [HTTP API integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md).

### Typed errors

Every failure mode is a typed exception rooted at `TaxomeshError`, importable
from the package root:

```python
from taxomesh import (
    TaxomeshError,                    # root
    TaxomeshNotFoundError,            #   ├─ Category / Item / Tag NotFound variants
    TaxomeshValidationError,          #   ├─ DuplicateSlug, ExternalIdConflict, CyclicDependency
    TaxomeshRelationError,            #   ├─ invalid item relations
    TaxomeshRepositoryError,          #   ├─ storage-level failures
    TaxomeshConfigError,              #   └─ configuration problems
)
```

### Logging

Standard library `logging` under the `"taxomesh"` logger with a `NullHandler`
registered at import — silent by default, fully controllable by the host
application:

```python
import logging
logging.getLogger("taxomesh").setLevel(logging.WARNING)
logging.getLogger("taxomesh").addHandler(logging.StreamHandler())
```

## Core concepts

| Concept | Description |
|---|---|
| **Item** | A taxonomy entity, usually bound to a business object via unique `external_id` |
| **Category** | A taxonomy node — `name`, unique `slug`, `description`, `metadata`, `external_id`, `enabled` |
| **Tag** | A free-form label assignable to items |
| **CategoryParentLink** | A category-to-parent edge carrying `sort_index` |
| **ItemParentLink** | An item-to-category placement carrying `sort_index` |
| **ItemRelationLink** | A directed, typed item-to-item edge (e.g. `covers`, `version_of`) |
| **TaxomeshGraph** | An ordered, read-only snapshot returned by `get_graph()` |
| **Repository** | The storage backend behind `TaxomeshService` (YAML, JSON, Django, or custom) |

## Architecture

```
your application ──┐
       CLI ────────┤
  Django admin ────┼──▶  TaxomeshService  ──▶  domain rules  ──▶  Repository port
  HTTP handlers ───┘     (single entry      (DAG constraints,     ├─ YAMLRepository
                          point, typed)      typed errors)        ├─ JsonRepository
                                                                  ├─ DjangoRepository
                                                                  └─ your backend
```

- **Service layer** — `TaxomeshService` is the only entry point application code needs
- **Domain rules** — validation, DAG constraints, and the typed error hierarchy live in one place
- **Repositories** — storage varies behind a stable port; behavior does not
- **Adapters** — CLI, Django admin/ORM, and HTTP helpers are optional and additive

## Stability and versioning

`taxomesh` follows [Semantic Versioning](https://semver.org/). As of **1.0.0**:

- The public API — everything importable from `taxomesh`, `taxomesh.contrib.api`,
  and `taxomesh.contrib.django`, plus the repository port — is stable; breaking
  changes only occur in major releases.
- Deprecations are announced at least one minor release before removal, with
  runtime `DeprecationWarning`s.
- Supported Python versions: 3.11, 3.12, 3.13. Django integration supports
  Django ≥ 4.2.
- Every release passes `ruff`, `mypy --strict`, and the full test suite with
  ≥ 80% coverage.

## Documentation

| Topic | Description |
|-------|-------------|
| [What Taxomesh Solves](https://github.com/ediazpacheco/taxomesh/blob/main/docs/what-is-taxomesh.md) | Product overview, use cases, and why taxonomy gets complex |
| [Python API](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md) | Categories, items, tags, relations, graph, lookups, search |
| [Repositories](https://github.com/ediazpacheco/taxomesh/blob/main/docs/repositories.md) | YAML, JSON, and Django backends; writing custom backends |
| [Configuration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/configuration.md) | `taxomesh.toml` reference |
| [CLI reference](https://github.com/ediazpacheco/taxomesh/blob/main/docs/cli.md) | Command-line interface |
| [Django integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/django-integration.md) | ORM backend, admin setup, model bridging |
| [HTTP API integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md) | Request schemas, handlers, serializers, error mapping |
| [Changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md) | Release history |

## Development

```bash
uv sync --extra dev --extra django
uv run pytest
uv run ruff check .
uv run mypy --strict .
```

## Contributing

Contributions are welcome. The project follows a spec-first workflow — please
align implementation PRs with the `specs/` directory.

## License

[MIT](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE)
