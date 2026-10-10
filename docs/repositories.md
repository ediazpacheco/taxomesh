# Storage Backends (Repositories)

Choose a storage backend by where the taxonomy should live; the service's API is the same over each.
The classes of the three that taxomesh ships import from `taxomesh.repositories`, which imports no
Django: `DjangoRepository` needs the `django` extra only when it is constructed.

| Repository | Stores in | Notes |
|---|---|---|
| `YamlRepository(path="data/taxomesh.yaml")` | one YAML file | the default backend; writes atomically; for development and small deployments, and a diff of the file is easy to read |
| `JsonRepository(path="data/taxomesh.json")` | one JSON file | writes atomically; for when JSON suits your operations |
| `DjangoRepository(using="default")` | the Django ORM | for use inside a Django project, which it needs configured: [Django integration](django-integration.md) |

A YAML or JSON file is read once, when its repository is built, and written whole, atomically, on
every write. A file therefore has one writer. A repository whose file another writer changed, in
this process or another, refuses to write with a `TaxomeshRepositoryError` that says to build a new
repository, which reads the change. The check runs before each write, so two processes writing at
the same moment can still lose one write. One repository may be shared by threads: each call runs
whole, under the repository's lock. Only `DjangoRepository` rolls several writes back together, and
processes that share a taxonomy use it.

```python
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.repositories import JsonRepository, YamlRepository

svc = TaxomeshService(repository=YamlRepository(Path("data/taxomesh.yaml")))
svc = TaxomeshService(repository=JsonRepository("data/taxomesh.json"))  # a str path works too
```

```python notest
from taxomesh.repositories import DjangoRepository

svc = TaxomeshService(repository=DjangoRepository())  # Django settings must be configured
```

A [`taxomesh.toml`](configuration.md) can name the repository instead, so application code builds
`TaxomeshService()` and nothing else.

## Custom backends

A class implementing `TaxomeshRepositoryBase` is a backend: it can keep the taxonomy in a database,
behind a remote API or in memory, if it keeps the contract below. The port is a `typing.Protocol`,
declared in `taxomesh/ports/repository.py` and exported from `taxomesh`, so nothing is inherited.
Each of its 37 members states its contract in its docstring: its arguments, what it returns, and,
for a lookup or a delete, what absence looks like.

| Group | Members |
|---|---|
| Single-row lookups, `X \| None` | `find_category`, `find_category_by_slug`, `find_category_by_external_id`, `find_item`, `find_item_by_slug`, `find_item_by_external_id`, `find_tag` |
| Keyed batch lookups, `Mapping` | `map_categories_by_id`, `map_categories_by_external_id`, `map_items_by_id`, `map_items_by_external_id`, `map_tags_by_id` |
| Listings, `Sequence` | `list_categories`, `list_items`, `list_tags`, `list_category_parent_links`, `list_item_parent_links`, `list_item_tag_links`, `list_item_relation_links`, `list_item_relation_links_batch` |
| Writes | `save_category`, `save_item`, `save_tag`, `save_category_parent_link`, `save_item_parent_link`, `save_item_relation_link`, `add_item_tag_link` |
| Deletes, `bool` | `delete_category`, `delete_item`, `delete_tag`, `delete_category_parent_link`, `delete_item_parent_link`, `delete_item_relation_link`, `delete_item_tag_link` |
| Transactions and introspection | `atomic()`, `describe()`, `config_summary` |

What a backend must keep:

- **Absence is not an error.** A lookup that finds nothing returns `None`, a batch leaves the key
  out, and a delete returns `False`. The service raises where its own contract calls for it.
- **A delete cascades.** In the same write, it removes every link that names the entity: a
  category's parent links at either end and its item placements; an item's placements, tag links
  and relation links at either end; a tag's tag links.
- **Rows are frozen.** `save_category` and `save_item` return the row as stored, whose `version`
  storage assigns, on an update the replaced row's plus one. When `expected_version` is given and
  no stored row is at that version, the save raises `TaxomeshVersionConflictError` and writes
  nothing; the comparison and the write are one atomic step.
- **An external id is unique within its kind.** `save_category` and `save_item` raise
  `TaxomeshExternalIdConflictError` when another entity of that kind holds the external id.
- **A failed write raises `TaxomeshRepositoryError`** and writes nothing. The file backends put
  back what memory held before the write, so no later write carries the failed change to disk.
- **The port stores the links it is given.** The service keeps the root invariant: a category holds
  a link to the implicit root exactly when it holds no other parent link. A custom backend holding a
  store written without it brings the store to it; the shipped file backends do so as they load a
  file, and Django's migration `0011` does it once.

`tests/adapters/repositories/test_repository_contract.py` holds every shipped backend to this
contract.

← [Back to README](../README.md)
