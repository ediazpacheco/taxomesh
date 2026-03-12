# taxomesh

Flexible taxonomy management for generic items with:

- multi-parent category DAGs
- per-parent sort ordering
- free-form item tags
- pluggable storage backends (YAML, JSON, Django)
- CLI, API, and django admin interfaces
- pluggable with existing API

`taxomesh` is **storage-agnostic by design**.

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

- **Item**: the core catalogued object, identified by an internal `item_id`. The optional `external_id` field links to an entity outside taxomesh (e.g. a primary key from another system).
- **Category**: taxonomy node with optional `name`, `description`, `metadata`, `external_id`, `enabled`, and unique `slug`
- **Tag**: free-form item label
- **ItemRelationLink**: directed, typed relation between two items (e.g. `covers`, `version_of`, `performed_by`)
- **CategoryParentLink**: relation from category to parent category with `sort_index`
- **ItemParentLink**: relation from item to category with `sort_index`
- **TaxomeshGraph**: read snapshot returned by `get_graph()` for tree-like traversal
- **Repository protocol**: `TaxomeshRepositoryBase` (`typing.Protocol`) defines the storage contract

## Documentation

| Topic | Description |
|-------|-------------|
| [Python API](docs/python-api.md) | Categories, Items, Tags, Graph, slug and external-ID lookups |
| [HTTP API integration](docs/http-api-integration.md) | Framework-agnostic handlers — FastAPI, Django, Flask examples and error mapping |
| [Django integration](docs/django-integration.md) | Django ORM + admin setup, model bridging |
| [Repositories](docs/repositories.md) | YAML, JSON, and Django storage backends; custom backends |
| [Configuration](docs/configuration.md) | `taxomesh.toml` reference |
| [CLI reference](docs/cli.md) | Command-line interface for categories, items, tags, and graph |

## Architecture

`taxomesh` uses a ports-and-adapters (hexagonal) shape:

- **Domain**: pure models and DAG validation
- **Application**: `TaxomeshService` orchestration
- **Ports**: repository protocol (`TaxomeshRepositoryBase`)
- **Adapters**: YAML/JSON/Django repositories + CLI
- **Contrib**: optional extras — `contrib/django/` (Django admin + ORM), `contrib/api/` (framework-agnostic HTTP handlers)

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
