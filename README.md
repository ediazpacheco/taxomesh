# taxomesh

taxomesh gives a multi-parent category graph a Python stdlib-style interface: categories, items and tags take subscript, `get`, `in`, `len` and `del` as a `dict` does. The graph is stored in a YAML file, a JSON file, the Django ORM or a backend of your own.

[![CI](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml/badge.svg)](https://github.com/ediazpacheco/taxomesh/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Python versions](https://img.shields.io/pypi/pyversions/taxomesh.svg)](https://pypi.org/project/taxomesh/)
[![Typed](https://img.shields.io/badge/types-mypy--strict-blue.svg)](https://github.com/ediazpacheco/taxomesh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE)

## What it is

taxomesh stores a taxonomy for records that your own system keeps, such as products, articles or
tracks. It does not store the records themselves: each record stays in your system, and an item or
a category stands for it through its `external_id`. [LetrasTango](https://letrastango.com/) uses
taxomesh in production to organize the categories and relations of its tango content.

Use it when a category has several parents, an item is in several categories, or the order of the
children depends on the parent. It also gives scripts, admin tools and APIs one set of rules. A flat
list of choices, or a tree in which each category has one parent, does not need it.

## Installation

Requires **Python 3.13+**.

```bash
pip install taxomesh             # the library
pip install "taxomesh[cli]"      # with the taxomesh command (typer, rich)
pip install "taxomesh[django]"   # with the Django ORM backend and admin
```

## Quick start

```python
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.repositories import YamlRepository

Path("quickstart.yaml").unlink(missing_ok=True)  # each run starts with an empty store
svc = TaxomeshService(YamlRepository("quickstart.yaml"))

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

# Read it back.
assert svc.items.get_by_external_id("catalog:42").item_id == album.item_id
assert svc.items[album.item_id].name == "Kind of Blue"  # subscript raises when absent
assert svc.items.get_by_slug("no-such-slug") is None  # get* returns None for a miss
assert jazz in svc.categories and len(svc.categories) == 3
assert [c.name for c in svc.categories.list(item=album)] == ["Jazz"]
assert [i.name for i in svc.items.list(tag=featured)] == ["Kind of Blue"]
assert [c.name for c in svc.categories.roots()] == ["Music", "Genres"]  # in the order they were made

node = svc.graph()[jazz]  # a read-only snapshot of the whole taxonomy
assert sorted(parent.category.name for parent in node.parents) == ["Genres", "Music"]
```

## The collection interface

`coll` is `svc.categories`, `svc.items` or `svc.tags`, and a key is a row or its `UUID`. Tags have
no slug, no external id and no search.

| Form | Returns | On a miss |
|---|---|---|
| `coll[key]` | the row | raises `Taxomesh<X>NotFoundError`, a `KeyError` |
| `coll.get(key, default=None, /)` | the row | `default` |
| `key in coll` | `bool` | `False` |
| `len(coll)` | `int` | `0` |
| `del coll[key]` | `None` | raises |
| `coll.get_by_slug(s)`, `coll.get_by_external_id(x)` | the row | `None` |
| `coll.get_many(keys)` | a new `dict` | the key is left out |
| `coll.list(...)`, `coll.search(...)` | a `tuple` | `()`; a filter naming an entity that is not stored raises |

The collections do not iterate ([why](https://github.com/ediazpacheco/taxomesh/blob/main/docs/design.md#the-law-subscript-raises-get-never-does)):
`coll.list(...)` lists the rows, and `len()` reads every row.

## What it does

- **Multi-parent categories**: a category has any number of parents, and a cycle raises
  `TaxomeshCyclicDependencyError`.
- **An order under each parent**: every parent link and placement carries its own `sort_index`,
  which `reorder` and `move` change.
- **External ids**: a `str`, an `int` or a `UUID`, stored as text and unique within its kind. You
  look them up one at a time or in bulk.
- **Tags and typed relations**: free-form tags, and directed item-to-item relations of types that
  you name, such as `covers` or `version_of`. `get_many_related` reads the relations of many items
  in two storage reads, in one direction or both.
- **Fuzzy search**: ranked, typo-tolerant and accent-insensitive, on names and slugs. An external id
  matches as a substring only. It uses rapidfuzz and needs no search server.
- **Graph snapshots**: `svc.graph()` holds one node per category, however many paths reach it.
- **Frozen rows**: `update` returns a new row. For a category or an item, `expected_version` makes
  it conditional.
- **A cache per service**: a service caches most reads for `cache_ttl` seconds, 5 by default, and a
  write clears the cache of its own service only.
- **Storage**: YAML, JSON or the Django ORM, chosen in code or in a `taxomesh.toml`, or your own
  backend implementing `TaxomeshRepositoryBase`. With no argument, `TaxomeshService()` takes its
  storage from `taxomesh.toml` in the working directory. The default store is `data/taxomesh.yaml`.
- **Integrations**: the `taxomesh` command, the Django admin with its graph view, and HTTP handlers
  that need no web framework. Each calls `TaxomeshService`.
- **Errors**: every error class inherits `TaxomeshError`. A not-found error is also a `KeyError`,
  and a validation error also a `ValueError`.

## Documentation

| Page | Covers |
|---|---|
| [Python API](https://github.com/ediazpacheco/taxomesh/blob/main/docs/python-api.md) | Every member, with runnable examples |
| [`llms.txt`](https://github.com/ediazpacheco/taxomesh/blob/main/llms.txt) | The whole Python API on one page, for an AI coding agent |
| [Repositories](https://github.com/ediazpacheco/taxomesh/blob/main/docs/repositories.md) | The three backends, and writing your own |
| [Configuration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/configuration.md) | `taxomesh.toml` |
| [CLI reference](https://github.com/ediazpacheco/taxomesh/blob/main/docs/cli.md) | Every command and global option |
| [Django integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/django-integration.md) | The app, the admin, and bridging your models |
| [HTTP API integration](https://github.com/ediazpacheco/taxomesh/blob/main/docs/http-api-integration.md) | Request schemas, handlers, serializers and error mapping |
| [Design](https://github.com/ediazpacheco/taxomesh/blob/main/docs/design.md) | The architecture and the decisions behind the surface, for contributors |
| [Changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md) | What each release changed |

## Stability and versioning

taxomesh uses [Semantic Versioning](https://semver.org/): what `taxomesh`, `taxomesh.repositories`,
`taxomesh.contrib.api` and `taxomesh.contrib.django` export, and the repository port, change
incompatibly only in a major release. The [changelog](https://github.com/ediazpacheco/taxomesh/blob/main/CHANGELOG.md)
names every breaking change.

taxomesh supports Python 3.13 and 3.14, and Django 6.x.

## Development

Contributions are welcome: see [CONTRIBUTING.md](https://github.com/ediazpacheco/taxomesh/blob/main/CONTRIBUTING.md) for the setup and the quality gates.
Licensed under [MIT](https://github.com/ediazpacheco/taxomesh/blob/main/LICENSE).
