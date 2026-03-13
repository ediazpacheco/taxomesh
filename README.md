# taxomesh

Reusable taxonomy engine for products, content, media, or any domain object you
already have.

`taxomesh` lets you attach categories, tags, and item relationships to existing
entities without baking taxonomy logic into your core models or re-implementing
the same validation, admin, and API workflows in every project.

Use it when "we just need categories" stops being simple:

- categories can have more than one parent
- the same item must appear in multiple branches
- ordering depends on the parent category
- your real entities already live in another system or model
- the same taxonomy rules must work from Python, CLI, Django admin, or your own API

What you get:

- multi-parent category DAGs
- per-parent sort ordering
- free-form item tags
- typed item-to-item relations
- pluggable storage backends (YAML, JSON, Django)
- one service layer with optional CLI, HTTP, and Django integrations

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status: Pre-Alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)

## What Taxomesh Does

At a high level, `taxomesh` is a reusable taxonomy layer.

It stores and validates the structure around your entities:

- categories and subcategories
- item placement inside one or more categories
- tags
- typed relations between items
- slugs, metadata, and external IDs for integration

Your actual business objects can stay where they already are. In many projects,
`taxomesh` is the missing layer between "our app already has products/articles/assets"
and "we need a serious taxonomy on top of them."

## Typical Use Cases

- Ecommerce catalogs where a product appears in several navigation paths
- Editorial or CMS systems with sections, topics, and reusable tagging
- Media catalogs with genre, format, collection, and related-item links
- Internal content or knowledge systems that need taxonomy without custom admin work

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

## Quick Start

Example: your application already has a product, track, or article identified by
an external ID, and you want to place it in a reusable taxonomy.

With no explicit repository configured, `TaxomeshService()` auto-discovers
`taxomesh.toml`; otherwise it falls back to the default YAML backend.

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

music = svc.create_category(name="Music")
jazz = svc.create_category(name="Jazz")
formats = svc.create_category(name="Formats")
vinyl = svc.create_category(name="Vinyl")

svc.add_category_parent(jazz.category_id, music.category_id, sort_index=10)
svc.add_category_parent(vinyl.category_id, formats.category_id, sort_index=20)

album = svc.create_item(
    external_id="catalog:42",
    name="Kind of Blue",
    slug="kind-of-blue",
)

svc.place_item_in_category(album.item_id, jazz.category_id, sort_index=1)
svc.place_item_in_category(album.item_id, vinyl.category_id, sort_index=3)

featured = svc.create_tag(name="featured")
svc.assign_tag(featured.tag_id, album.item_id)

print(album.external_id)  # "catalog:42"
print([node.category.name for node in svc.get_graph().roots])  # ["Music", "Formats"]
```

The item still belongs to your application. `taxomesh` manages the taxonomy layer
around it: placement, ordering, tags, relations, slugs, and traversal.

## Why This Exists

Taxonomy work is usually underestimated. A simple category table becomes more complex
once you need:

- multiple parents instead of a strict tree
- branch-specific ordering
- items linked to existing models by external ID
- reusable validation and errors across app code, CLI, admin, and APIs
- storage that fits both local development and production integration

`taxomesh` packages those concerns into a single component so they do not have to be
re-solved in each codebase.

## Core Concepts

- **Item**: an entity in your taxonomy, usually linked to a business object through `external_id`
- **Category**: a taxonomy node with optional `name`, `description`, `metadata`, `external_id`, `enabled`, and unique `slug`
- **Tag**: a free-form label assigned to items
- **ItemRelationLink**: a directed, typed relation between two items such as `covers`, `version_of`, or `performed_by`
- **CategoryParentLink**: the link from a category to one of its parents, including `sort_index`
- **ItemParentLink**: the link from an item to a category, including `sort_index`
- **TaxomeshGraph**: a read snapshot returned by `get_graph()` for traversal
- **Repository**: the storage backend used by `TaxomeshService`

## Documentation

| Topic | Description |
|-------|-------------|
| [What Taxomesh Solves](https://github.com/ediazpacheco/taxomesh/blob/main/docs/what-is-taxomesh.md) | Product overview, common use cases, and why taxonomy gets complex |
| [Python API](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md) | Categories, Items, Tags, Graph, slug and external-ID lookups |
| [Django integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/django-integration.md) | Django ORM + admin setup, model bridging |
| [HTTP API integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md) | Reuse request models, handlers, and error mapping in your existing web app |
| [Repositories](https://github.com/ediazpacheco/taxomesh/blob/main/docs/repositories.md) | YAML, JSON, and Django storage backends; custom backends |
| [Configuration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/configuration.md) | `taxomesh.toml` reference |
| [CLI reference](https://github.com/ediazpacheco/taxomesh/blob/main/docs/cli.md) | Command-line interface for categories, items, tags, and graph |

## Design

`taxomesh` keeps a stable application-facing shape while letting storage and integration
details vary:

- **Service layer**: `TaxomeshService` is the main entry point for application code
- **Domain rules**: taxonomy validation, including DAG constraints and typed errors
- **Repositories**: YAML, JSON, Django, or a custom backend behind the same service API
- **Optional integrations**: CLI, Django admin + ORM, and framework-agnostic HTTP helpers

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

MIT.
