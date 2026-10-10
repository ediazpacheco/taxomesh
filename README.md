# taxomesh

taxomesh stores a graph of categories in a YAML file, a JSON file or the Django ORM, and a category can have more than one parent. In Python, you read and delete categories, items and tags with five forms that a `dict` also has: subscript, `get`, `in`, `len` and `del`.

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Typed](https://img.shields.io/badge/types-mypy--strict-blue.svg)](https://github.com/ediazpacheco/taxomesh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE)

## What it is

taxomesh stores a taxonomy for records that your own system keeps, such as products, articles or
tracks. It is not a database for the records: each record stays in your system, and an item or a
category can stand for it through its `external_id`. taxomesh stores categories with any number of
parents, items placed in any number of categories, an order under each parent, tags, and typed
relations between items. It also searches items and categories. The `taxomesh` command, the Django
admin with its graph view, and the HTTP handlers, which need no web framework, call `TaxomeshService`.

Use it when the taxonomy needs its own component, for example for navigation that is not a strict
tree, one item in several places, an order that depends on the place, or one set of rules for
scripts, admin tools and APIs. It is not needed for a flat list of choices, a tree in which each
category has one parent, a small fixed part of one screen, or a taxonomy with no need for reusable
validation, traversal or integrations.

## Installation

Requires **Python 3.13+**.

```bash
pip install taxomesh             # the library
pip install "taxomesh[cli]"      # with the taxomesh command (typer, rich)
pip install "taxomesh[django]"   # with the Django ORM backend and admin
```

## Quick start

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()  # the taxomesh.toml in the working directory, else a YAML file in ./data/

# Categories form a graph: Jazz has two parents, Music and Genres.
music = svc.categories.create(name="Music")
genres = svc.categories.create(name="Genres")
jazz = svc.categories.create(name="Jazz")
svc.categories.add_parent(jazz, music)
svc.categories.add_parent(jazz, genres)

# An item stands for a record of yours, and is found again by its external id.
album = svc.items.create(name="Kind of Blue", external_id="catalog:42")
svc.items.place_in(album, jazz)
featured = svc.tags.create(name="featured")
svc.items.tag(album, featured)

# Read it with the forms a dict has: a row, or its UUID, is the key.
assert svc.items.get_by_external_id("catalog:42").item_id == album.item_id
assert svc.items[album.item_id].name == "Kind of Blue"  # subscript raises when absent
assert svc.items.get_by_slug("no-such-slug") is None  # get* never raises
assert jazz in svc.categories and len(svc.categories) == 3
assert [c.name for c in svc.categories.list(item=album)] == ["Jazz"]
assert [i.name for i in svc.items.list(tag=featured)] == ["Kind of Blue"]
assert sorted(c.name for c in svc.categories.roots()) == ["Genres", "Music"]

node = svc.graph()[jazz]  # a read-only snapshot of the whole taxonomy
assert sorted(parent.category.name for parent in node.parents) == ["Genres", "Music"]
```

## The forms

`coll` is `svc.categories`, `svc.items` or `svc.tags`, and a key is a row or its `UUID`. Tags have
no slug, external id or search:

| Form | Returns | On a miss |
|---|---|---|
| `coll[key]` | the row | raises `Taxomesh<X>NotFoundError`, a `KeyError` |
| `coll.get(key, default=None)` | the row | `default` |
| `key in coll` | `bool` | `False` |
| `len(coll)` | `int` | `0` |
| `del coll[key]` | `None` | raises |
| `coll.get_by_slug(s)`, `coll.get_by_external_id(x)` | the row | `None` |
| `coll.get_many(keys)` | a new `dict` | the key is left out |
| `coll.list(...)`, `coll.search(...)` | a `tuple` | `()`; a filter naming an entity that is not stored raises |

The collections do not iterate ([why](https://github.com/ediazpacheco/taxomesh/blob/main/docs/design.md#the-law-subscript-raises-get-never-does)):
`coll.list(...)` enumerates, and `len()` is the one form that reads every row.

## What it does

- **Multi-parent categories**: a category has any number of parents, and a cycle raises
  `TaxomeshCyclicDependencyError`.
- **An order under each parent**: every parent link and placement carries its own `sort_index`,
  which `reorder` and `move` change.
- **External ids**: `str`, `int` or `UUID`, stored as text and unique within its kind, and looked
  up one at a time or in bulk.
- **Tags and typed relations**: free-form tags, and directed item-to-item relations (`covers`,
  `version_of`) read in either direction, for many items at once in two storage reads.
- **Fuzzy search**: ranked, typo-tolerant and accent-insensitive, on names and slugs; an external id
  matches as a substring only. It runs in the process, with rapidfuzz, and needs no search server.
- **Graph snapshots**: `svc.graph()` holds one node per category, however many paths reach it.
- **Frozen rows**: `update` returns a new row, and `expected_version` makes it conditional.
- **A cache per service**: reads are cached for `cache_ttl` seconds, 5 by default, and a write
  clears its own service's cache only.
- **Storage**: YAML (the default), JSON or the Django ORM, chosen in code or in a `taxomesh.toml`,
  or your own backend implementing `TaxomeshRepositoryBase`. One contract suite holds every shipped
  backend to that port.
- **Errors**: a member raises a `TaxomeshError`, a not-found one also a `KeyError` and a validation
  one also a `ValueError`, or a `TypeError` for an argument of the wrong type. Log records go to the
  `taxomesh` logger, which has only a `NullHandler` of its own.

## Documentation

The whole Python API is on one page ([`llms.txt`](https://github.com/ediazpacheco/taxomesh/blob/main/llms.txt)), so an AI coding agent can use taxomesh without reading its source.

| Page | Covers |
|---|---|
| [Python API](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md) | Every member, with runnable examples |
| [Repositories](https://github.com/ediazpacheco/taxomesh/blob/main/docs/repositories.md) | The three backends, and writing your own |
| [Configuration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/configuration.md) | `taxomesh.toml` |
| [CLI reference](https://github.com/ediazpacheco/taxomesh/blob/main/docs/cli.md) | Every command and global option |
| [Django integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/django-integration.md) | The app, the admin, and bridging your models |
| [HTTP API integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md) | Request schemas, handlers, serializers and error mapping |
| [Design](https://github.com/ediazpacheco/taxomesh/blob/main/docs/design.md) | The architecture and the decisions behind the surface, for contributors |
| [Changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md) | What each release changed |

## Stability and versioning

`taxomesh` is pre-1.0. It uses [Semantic Versioning](https://semver.org/), but **the guarantees
below take effect at 1.0.0 and do not apply yet**: the API may change between pre-1.0 releases,
and the [changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md) calls out
every breaking change.

Planned from 1.0.0:

- The public API, everything importable from `taxomesh`, `taxomesh.contrib.api` and
  `taxomesh.contrib.django` plus the repository port, becomes stable; breaking changes only occur
  in major releases.
- Deprecations are announced at least one minor release before removal, with runtime
  `DeprecationWarning`s.

True of the current pre-1.0 releases:

- Supported Python versions: 3.13, 3.14. The Django integration supports Django 6.0 or later.
- Every release passes `ruff`, `mypy --strict` over the package and its tests, the Django
  integration included, and the full test suite with at least 80% line coverage; the Django
  integration, which its own tests exercise, is left out of that measure.

## Used in production

`taxomesh` was extracted from, and is used in production by,
[LetrasTango](https://letrastango.com/), a **personal, non-commercial side project** cataloguing
tango lyrics, artists and works. It shares an author with `taxomesh` and is the **only known
production consumer**: one deep, owner-operated integration rather than independent external
validation. Over the Django backend it exercises external-id binding and bulk lookup, multi-parent
categories with ordered placements, typed directed item relations with batched traversal, and fuzzy
search. Tags, the HTTP handlers, the JSON and YAML backends and the CLI are tested in the library
but not proven by this use. Its public artist graph is derived by LetrasTango from its own domain
logic: `taxomesh` supplies the categories and relations, and does not render or own that view.

## Development

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run mypy --strict .
```

Contributions are welcome: see [CONTRIBUTING.md](https://github.com/ediazpacheco/taxomesh/blob/main/CONTRIBUTING.md) for the setup and the quality gates.
Licensed under [MIT](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE).
