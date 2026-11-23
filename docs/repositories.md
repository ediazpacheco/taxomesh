# Storage Backends (Repositories)

This page helps you choose where taxomesh stores the taxonomy, and says how to write your own
backend. The service's API is the same on every backend.

Import the three shipped classes from `taxomesh.repositories`. That module imports no Django:
`DjangoRepository` needs the `django` extra only when you build it. A
[`taxomesh.toml`](configuration.md) can name the backend instead, so that the code builds
`TaxomeshService()` with no argument.

| Repository | Stores in | Notes |
|---|---|---|
| `YamlRepository(path="data/taxomesh.yaml")` | one YAML file | the default backend; writes atomically; for development and small deployments, and a diff of the file is easy to read |
| `JsonRepository(path="data/taxomesh.json")` | one JSON file | writes atomically; for when JSON suits your operations |
| `DjangoRepository(using="default")` | the Django ORM | for use inside a Django project, which it needs configured: [Django integration](django-integration.md) |

```python
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.repositories import JsonRepository, YamlRepository

svc = TaxomeshService(repository=YamlRepository(Path("data/taxomesh.yaml")))
svc = TaxomeshService(repository=JsonRepository("data/taxomesh.json"))  # a str path works too
```

## File backends

- A YAML or JSON repository reads its file once, when it is built. On every write, it writes the
  whole file atomically.
- So a file has one writer. When another writer changed the file, the repository refuses to write,
  with a `TaxomeshRepositoryError` that says to build a new repository, which reads the change.
- The check runs before each write. So two repositories that write at the same moment, in one
  process or in two, can still lose one write.
- Threads may share one repository: each call, and each `atomic()` block, runs whole under its lock.
- A write keeps the mode of the file, and a new file gets mode `0600`.
- With 10,000 items, one write took 0.3 s on YAML, with the libyaml of PyYAML's wheels, and 25 ms
  on JSON, on an Apple M5 Max.

Only `DjangoRepository` rolls back writes together. Processes that share a taxonomy use it.

## Write your own backend

A class that implements `TaxomeshRepositoryBase` is a backend. It can keep the taxonomy in a
database, behind a remote API or in memory, if it keeps the contract below. The port is a
`typing.Protocol`, declared in `taxomesh/ports/repository.py` and exported from `taxomesh`, so a
backend inherits nothing.

The docstring of each of the 38 members of the port states its contract. It gives the arguments,
what the member returns, and, for a lookup or a delete, what absence looks like. The service raises `TypeError` for a
repository that lacks a member. It checks with `isinstance`, which misses a member that
`__getattr__` gives: pass such a class to `TaxomeshRepositoryBase.register`.

| Group | Members |
|---|---|
| Single-row lookups, `X \| None` | `find_category`, `find_category_by_slug`, `find_category_by_external_id`, `find_item`, `find_item_by_slug`, `find_item_by_external_id`, `find_tag` |
| Keyed batch lookups, `Mapping` | `map_categories_by_id`, `map_categories_by_external_id`, `map_items_by_id`, `map_items_by_external_id`, `map_tags_by_id` |
| Listings, `Sequence` | `list_categories`, `list_items`, `list_tags`, `list_category_parent_links`, `list_item_parent_links`, `list_item_tag_links`, `list_item_relation_links`, `list_item_relation_links_batch` |
| Writes | `save_category`, `save_item`, `save_tag`, `save_category_parent_link`, `save_item_parent_link`, `save_item_relation_link`, `add_item_tag_link` |
| Deletes, `bool` | `delete_category`, `delete_item`, `delete_tag`, `delete_category_parent_link`, `delete_item_parent_link`, `delete_item_relation_link`, `delete_item_tag_link` |
| Transactions and introspection | `atomic()`, `in_transaction`, `describe()`, `config_summary` |

A backend must keep these rules. [Design](design.md#where-the-rules-are-enforced) names the tests
that check them on the shipped backends.

- **Absence is not an error.** A lookup that finds nothing returns `None`, a batch leaves the key
  out, and a delete returns `False`. The service raises where its own contract calls for it.
- **A delete cascades.** In the same write, it removes every link that names the entity:
  - for a category, its parent links at either end and its item placements;
  - for an item, its placements, its tag links and its relation links at either end;
  - for a tag, its tag links.
- **Rows are frozen.** `save_category` and `save_item` return the row as stored. On an update, its
  `version` is the replaced row's plus one. When `expected_version` is given and no stored row is at
  that version, the save raises `TaxomeshVersionConflictError` and writes nothing. The comparison
  and the write are one atomic step.
- **An external id is unique within its kind.** `save_category` and `save_item` raise
  `TaxomeshExternalIdConflictError` when another entity of that kind holds the external id.
- **A storage failure raises `TaxomeshRepositoryError`**, from a read or a write, and a failed write
  writes nothing. When a write of a file backend fails before its new file is in place, the backend
  restores what memory held before the write. So no later write carries that change to disk.
- **`atomic()` keeps every other block of the store out.** A block that another thread opens on the
  same repository, or another process on a shared database, waits until this one ends. On SQLite, a
  block inside a caller's transaction that has read already waits only with the setting that
  [Django integration](django-integration.md#get-the-service) gives. A backend that only one thread
  uses at a time may do nothing. Entering a block may wait, and raises only `TaxomeshRepositoryError`.
  `in_transaction` is `True` only while this thread is in a transaction.
- **`relation_types` is a collection.** The two relation listings raise `TypeError` for a `str`.
- **The port stores the links it is given.** The implicit root is a `Category` row named `__root__`,
  which the service stores when none is stored. A category holds a link to it exactly when it holds
  no other parent link. A category with no link is not at the top level, and nothing raises. So a
  custom backend that loads a store written without these links first stores the root, then links
  each such category to it. The file backends link them when they load a file that holds the root,
  or in the write that stores it, and Django's migrations `0011` and `0012` do it once.

← [Back to README](../README.md)
