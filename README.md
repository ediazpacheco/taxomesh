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
- typo-tolerant fuzzy search over items and categories

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

### Resolving which categories an item belongs to

`list_categories_by_item()` is the inverse of `list_items(category_id=...)` — it answers
*"which categories does this item belong to?"*, ordered by sort position:

```python
cats = svc.list_categories_by_item(album.item_id)
# [Category(name="Jazz", ...), Category(name="Vinyl", ...)]
# — ordered by the sort_index set when the item was placed
```

If the item has no placements, an empty list is returned. Only enabled categories
are returned by default; pass `enabled=None` to include disabled ones.
Raises `TaxomeshItemNotFoundError` when the item does not exist.

### Resolving items and categories by external_id

`external_id` is a **unique** identifier (`str | None`). Each record can have at most
one `external_id`; the same value cannot be assigned to two items (or two categories)
simultaneously. `None` means no external reference — multiple records may have `None`.

Use the dedicated lookup methods for point lookups:

```python
item = svc.get_item_by_external_id("catalog:42")    # Item | None
cat  = svc.get_category_by_external_id("solo")      # Category | None
```

Both methods return `None` when no record matches or when `None` is passed as input.

Attempting to save two records with the same non-`None` `external_id` raises
`TaxomeshExternalIdConflictError` (a subclass of `TaxomeshValidationError`):

```python
from taxomesh import TaxomeshExternalIdConflictError

try:
    svc.create_item(name="B", external_id="catalog:42")
except TaxomeshExternalIdConflictError as exc:
    print(exc)  # external_id 'catalog:42' is already assigned to another item.
```

## Fuzzy Search

`search_items()` and `search_categories()` find matches by name, slug, and external ID
with typo tolerance, accent-insensitivity, and ranked results — no extra infrastructure
required.

```python
# Typo-tolerant: finds "Piazzolla" even with a misspelling
results = svc.search_items("piazola")

# Accent-insensitive: finds "Agustín Magaldi" without the accent
results = svc.search_items("agustin magaldi")

# Scoped to a subtree
results = svc.search_items("tango", category_id=cat.category_id, recursive=True)

# Category search, children of a specific parent only
results = svc.search_categories("orkesta tipika", parent_id=parent.category_id)
```

Results are sorted by match quality: exact matches first, then prefix, substring, and
fuzzy matches. Pass `fuzzy=False` to restrict to exact/prefix/substring matching only.
Pass `enabled=False` to include only disabled items and categories, or `enabled=None` for all.

Both methods are optimized for repeated and per-keystroke (autocomplete) usage:

- **Corpus cache**: on the first unfiltered search, all candidate fields (name, slug,
  external ID) are normalized and stored in an internal cache. Subsequent searches
  reuse the pre-normalized corpus — no repository reload, no re-normalization.
- **Automatic invalidation**: the cache is reset whenever an item or category write
  operation (`create_*`, `update_*`, `delete_*`) is performed, so results are always
  consistent with the current state of the catalog.
- **Heap-based top-k**: when `limit` is smaller than the number of matches,
  `heapq.nsmallest` is used instead of a full sort (O(N log k) vs O(N log N)).
- **Category-filtered and recursive searches** bypass the corpus and load candidates
  directly, so subtree scoping is always precise.

No configuration is required — the optimization is fully automatic and applies to
all repository backends (Django, YAML, JSON).

See [Python API — Fuzzy Search](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md#fuzzy-search) for the full parameter reference.

To expose search in an HTTP endpoint, use the ready-made `SearchItemsRequest` /
`SearchCategoriesRequest` schemas with `handlers.search_items` / `handlers.search_categories`
and the `items_to_list` / `categories_to_list` serializers from `taxomesh.contrib.api`.
See [HTTP API integration — Search endpoints](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md#search-endpoints) for examples.

## Django admin — graph sort modes

The admin graph view ships with a sort selector toolbar. Two built-in modes are provided:

| Key | Label | Behaviour |
|---|---|---|
| `sort_index_asc` | Sort index ↑ | Ascending by `sort_index` (default) |
| `sort_index_desc` | Sort index ↓ | Descending by `sort_index` |

### Registering a custom sort mode

Define a callable that receives and returns `list[GraphEntry]`, then append a
`(key, label, callable)` 3-tuple to `sort_modes` on your admin subclass:

```python
# myproject/admin.py
from taxomesh.contrib.django.admin import TaxomeshCategoryAdmin
from taxomesh.contrib.django.graph_sort import DEFAULT_SORT_MODES, SortMode
from taxomesh.contrib.django.graph_types import GraphEntry

def sort_by_relevance(entries: list[GraphEntry]) -> list[GraphEntry]:
    scores = fetch_my_relevance_scores([e["uuid"] for e in entries])
    return sorted(entries, key=lambda e: scores.get(e["uuid"], 0), reverse=True)

class MyCategoryAdmin(TaxomeshCategoryAdmin):
    sort_modes: list[SortMode] = [
        *DEFAULT_SORT_MODES,
        ("content_relevance", "Content relevance", sort_by_relevance),
    ]
```

The "Content relevance" option appears in the sort selector on the graph page.
The sort mode is preserved when expanding lazy-loaded children via the AJAX endpoint.

taxomesh is fully agnostic — it calls your function with the entries already built
for that view level and expects the sorted list in return. Any domain knowledge
(scores, external data, request context) lives entirely in your callable.

> **Note**: use `[*DEFAULT_SORT_MODES, ...]` rather than mutating the list in place
> to avoid sharing state between subclasses.

## Logging

taxomesh uses Python's standard `logging` module and follows the recommended practice
for public libraries: a `NullHandler` is registered on the `"taxomesh"` root logger at
import time. **No output is produced by default** — the consuming application decides
where logs go and at what level.

### Logger hierarchy

| Logger | Source |
|---|---|
| `taxomesh.application.service` | Service-layer warnings (e.g. dangling relation links) |
| `taxomesh.contrib.django.admin` | Django admin integration warnings |

### Capturing taxomesh logs

```python
import logging

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger("taxomesh").addHandler(handler)
logging.getLogger("taxomesh").setLevel(logging.WARNING)
```

Timestamps are not embedded in message text — use `%(asctime)s` in your formatter.

### Notable warnings

**`taxomesh.application.service`** — emitted by `list_related_items_for_sources()` when
`skip_on_error=True` and a relation link points to a target item that no longer exists:

```
list_related_items_for_sources: dangling relation skipped — source: 🏷️ "Track A" (id: fea7bd50-...), target: <orphaned item 6a273a4c-...>, relation_type: 'music_by'
```

**`taxomesh.contrib.django.admin`** — emitted when a required Django settings key is
missing or URL resolution for a linked model fails.

### Suppressing taxomesh logs

```python
logging.getLogger("taxomesh").setLevel(logging.ERROR)   # suppress WARNING; keep ERROR+
logging.getLogger("taxomesh").disabled = True            # suppress everything
```

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
| [Changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md) | Release history and new API methods |

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
