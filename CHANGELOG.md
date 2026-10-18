# Changelog

All notable changes to taxomesh are documented here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

The alpha series before 1.0.0, `0.1.0a1` to `0.1.0a50`, is described on the
[GitHub releases page](https://github.com/ediazpacheco/taxomesh/releases), one release per git tag.
The full entries of that series are in
[`CHANGELOG.md` at the tag `v0.1.0a50`](https://github.com/ediazpacheco/taxomesh/blob/v0.1.0a50/CHANGELOG.md).
The changes of 1.0.0 were first dated as 0.2.0 in this file, on 2026-10-12; that version was never
tagged or published.

## [1.0.1] — 2026-10-18

1.0.1 fixes what a move or a reorder reads, the `before` of a move, the check of the service's
repository, six defects of the Django admin, the opening examples of three documentation pages, and
the statements of the documentation that a user of 1.0.0 found short. No public name or signature
changes.

### Fixed

- `items.move` and `items.reorder` read the placements of the one category that they order, and
  `categories.reorder` the parent links of one parent or of the top level, as `items.place_in` does.
  In 1.0.0 they read every link of the store: with 100,000 placements on SQLite, a move took 0.8 s;
  it now takes 3 ms.
- `items.move` and `categories.move` check `before` before they write. A `before` that names no
  stored row raises the not-found error of its kind, and a row that is not in the destination, the
  moving row included, raises `TaxomeshValidationError`. In 1.0.0 the move took the row from its old
  place and put it last.
- `TaxomeshService(repository)` raises `TypeError` for an object that does not implement
  `TaxomeshRepositoryBase`, such as a path. In 1.0.0 `TaxomeshService("x.yaml")` raised
  `AttributeError: 'str' object has no attribute 'list_categories'`. The port is runtime-checkable,
  so a class that gives the port's members through `__getattr__`, which `isinstance` does not see,
  calls `TaxomeshRepositoryBase.register` on itself.
- `ItemCategoryAssignmentMixin` shows its *categories* field on an admin that declares no `fields`
  or `fieldsets`. A save changes placements only when its page shows the field, and keeps each
  placement in a category that the field does not offer, such as a disabled one. In 1.0.0 the page
  showed no field, and a save of the other fields removed the item from every category.
- The admin's tag pages take no identifier: the service assigns it, as on the category and item
  pages. In 1.0.0 the add page required a UUID that the save replaced, and an edit of it answered 500.
- On the admin graph, opening a branch sets up the drag handles of its entries. In 1.0.0 it showed
  "Loading failed: initHandles is not defined", and the toggle went back to `[+]`.
- Every admin page links a category to the model that `TAXOMESH_CATEGORY_LINKED_MODEL` names, or
  `TAXOMESH_LINKED_MODEL` while that setting is not set; in 1.0.0 the category list and the graph
  read `TAXOMESH_LINKED_MODEL` alone. With neither setting, a change page shows no `↗` row, where it
  showed an empty one, and no page logs a warning for each row.
- The admin shows a tag as its name and identifier, and a link as its two ends and its
  `sort_index`. In 1.0.0 the tag autocomplete showed `TagModel object (…)`.
- In the admin graph's reorder and reparent views, an identifier that is not text, such as a
  number, answers 400 "Invalid UUID format" in JSON, as text that is not a UUID does. A storage
  failure before the move answers the JSON 500 with the generic text, as a failure of the move does.
  Both answered Django's HTML 500.
- The opening examples of `docs/python-api.md`, `docs/http-api-integration.md` and `docs/design.md`
  run again in the same folder: each first empties a store of its own, as the README's quick start
  does. With the default store, a second run raised.
- The documentation says that `node.ancestors()` takes the parents in identifier order; that
  `categories.list()` with no filter returns every enabled category, at every level, by name, then
  identifier; that `parent=None` is no filter there, while `roots()` lists the top level; that an
  unfiltered `tags.list()` has no promised order; that a model's field takes what pydantic's lax
  mode takes; and that a `config_path` naming no file gives the default store.
- The port no longer says that a batch read must not be split: a backend may read one over its
  storage's parameter limit in several queries, as `DjangoRepository` does. The port and
  `docs/repositories.md` state the implicit root's duty: it is a `Category` named `__root__`, and a
  backend that loads a store without it links each category that has no parent to it first.
- `docs/django-integration.md` names the two linked-model settings, the app label, the permissions
  that the graph's moves need, and the graph's and the debug page's URLs.

## [1.0.0] — 2026-10-15

1.0.0 gives taxomesh a Python stdlib-style interface: every operation is a member of
`svc.categories`, `svc.items` or `svc.tags`, or is `svc.graph()` or `svc.info`; rows are frozen; the
command line and the HTTP handlers are named after the member they call. It breaks nearly every
`0.1.0a50` call, with no alias: an old name fails at once with `AttributeError`, which
`mypy --strict` reports first. [`docs/python-api.md`](docs/python-api.md) states the new surface.
From this release, the README's Stability and versioning section is the rule.

### Silent changes

After each call is renamed, these three changes still give no error. The ⚠ entries below name the
other breaking changes.

- `categories.get_by_slug` and `items.get_by_slug` return `None` on a miss, where
  `get_category_by_slug` and `get_item_by_slug` raised not-found. A loop waiting for the raise never
  ends.
- `categories.list()` with no filter returns every enabled category, at every level.
  `list_categories()` returned the top level, which is `categories.roots()` now.
- `svc.categories`, `svc.items` and `svc.tags` are attributes, not methods. A lookup such as
  `getattr(svc, "get_category_by_slug", None)`, or a proxy that wraps only callables, finds nothing
  and raises no error.

### Changed

- ⚠ **The flat service methods are gone.** Each operation is a member of the collection it acts on:
  `svc.get_category(c)` is `svc.categories[c]`, `list_categories_by_item(i)` is
  `categories.list(item=i)`, `reparent_category` is `categories.move`, and
  `list_related_items_for_sources` is `items.get_many_related`, which returns a `RelatedItems` per
  item. `get_graph()` is `svc.graph()`, and `get_debug()` is the `svc.info` property, where
  `repository_type` and `working_path` are `repository.backend` and `.path`.
- ⚠ **One law over the collections.** On an absent key, subscript raises `Taxomesh<X>NotFoundError`,
  and `get(key, default=None, /)` and anything else named `get*` does not. `in`, `len` and `del`
  complete the forms, and a collection does not iterate: `list(...)` enumerates. A listing returns a
  tuple, a `get_many*` a new dict keyed by identifier or by stored external id.
- ⚠ **A parameter that names an entity takes a row or its `UUID`** (`CategoryRef`, `ItemRef`,
  `TagRef`) and is a noun: `parent`, `item`, `before`, `source`. Anything else, a `str` identifier
  included, raises `TypeError` before storage is read. Filters, `sort_index` and `metadata` are
  keyword-only.
- ⚠ **`items.tag(item, tag)` and `untag` take the item first**, where `assign_tag` took the tag
  first, and `tag` returns its `ItemTagLink`. Passed as two `UUID`s, a call left in the old order
  type-checks: edit each by hand.
- ⚠ **Rows are frozen.** Assigning to a field raises pydantic's `ValidationError`, a `ValueError`,
  and changing `metadata` in place `TypeError`. `update` returns a new row; each field defaults to
  `UNSET`, which leaves it, and `None` clears `external_id` and is a `TypeError` for any other.
  `str(row)` is a plain label, `Music (slug: music, id: …)`, and `Category.is_root` is gone.
- ⚠ **Errors are stdlib errors too:** not-found is a `KeyError`, a refused value a `ValueError`, and
  an argument of the wrong type a `TypeError` (`enabled="yes"` matched nothing, `using=None` opened
  `"default"`); the flags `recursive`, `fuzzy` and `include_items` are read as `if flag:`. No
  `pydantic.ValidationError` leaves a member, and on Django every database error, a commit's
  included, is `TaxomeshRepositoryError`: `except django.db.DatabaseError` no longer matches.
  `TaxomeshRootCategoryError`, a validation error, also refuses a rename to the reserved name.
- ⚠ **A category is at the top level exactly when it has no parent:** `add_parent` removes it from
  the top level, removing its last parent puts it back, and `roots()` and `graph().roots` agree.
  `None`, not the identifier of the implicit root, which is not-found everywhere, stands for the top
  level in `move` and `reorder`, and `move` returns `None`. File stores are normalised as they load,
  and on Django `migrate` runs `0011_root_invariant`; both drop an item's placement in the implicit
  root, so `categories.list(item=…)` never returns it. `0012_implicit_root` stores the implicit root,
  and folds a second one, which two services starting at once could store, into the first.
- ⚠ **A new link with no position goes after the last** (API change): `add_parent`, `place_in` and
  `relate` take `sort_index=None`, so a store lists links in the order they were made, where each
  was at 0 and ties fell to the identifier. A stored link keeps its position, a new category goes
  last, and the HTTP bodies and `--sort-index` do the same.
- ⚠ **Relations:** `unrelate` of an absent relation does nothing, and both relation listings raise
  for an item that is not stored. `list_related` and `get_many_related` keep `enabled` items by
  default and skip a relation to an absent item with one `WARNING` from
  `taxomesh.application.collections.items`. `relation_type="x"` is `relation_types="x"`;
  `skip_on_error` is gone.
- ⚠ **Each service caches its own reads** for `cache_ttl` seconds (5 by default; `0` caches
  nothing), `get_many` included, and a write clears only that service's entries; an expired entry
  is dropped when its member stores the next one; a read inside a transaction is neither cached nor
  served from the cache. A YAML or JSON file has one writer, and a repository whose file another
  writer changed refuses to write. `@memoize(ttl)` and `clear_all_caches()` are gone.
- ⚠ **`YAMLRepository` is `YamlRepository`**, and `taxomesh.repositories` holds the three repository
  classes. `Direction` replaces `DIRECTION_OUTGOING` and `DIRECTION_INCOMING`.
- ⚠ **The repository port**, for a custom backend: lookups are `find_*`, keyed batch reads `map_*`,
  `assign_tag` and `remove_tag` `add_item_tag_link` and `delete_item_tag_link`,
  `get_config_summary()` the `config_summary` property, `get_debug_info()` `describe()`, and
  `list_item_relation_links_for_items` `list_item_relation_links_batch`. `save_category` and
  `save_item` return the stored row and take `expected_version`, a delete removes its links,
  listings return `Sequence`, and `list_item_parent_links` takes `item_ids`,
  `list_category_parent_links` `category_ids` too. `atomic()` keeps every other block of the store
  out, the read-only property `in_transaction` (API change) says whether a transaction is open, and
  both relation listings raise `TypeError` for a bare `str` as `relation_types`.
- ⚠ **Each HTTP handler is `<namespace>_<member>`** (`get_category` is `categories_get`,
  `list_categories` `categories_roots`, `get_graph` `graph`) and returns what its member returns, so
  a lookup answers `None` and your application makes the 404. Arguments after the subject are
  keyword-only, `include_disabled` is `enabled`, `AddParentRequest` and `PlaceInCategoryRequest` are
  `AddCategoryParentRequest` and `PlaceItemRequest`, and the search schemas take `query`, not `q`.
- ⚠ **The command line is the `cli` extra** (`pip install "taxomesh[cli]"`), and each command is its
  member, hyphenated: `item add-to-category` is `item place-in`, `item relation add` is `item
  relate`. `category list` lists every category, `category roots` the top level. `create` and
  `update` take no link option; `--include-disabled` is `--state all`, `--type` a repeatable
  `--relation-type`, both updates take `--enable/--disable`, `tag update --name` is optional, and
  `item create` requires `--name`. `item create --external-id ""` stores `""`, where `item add`
  stored none.
- ⚠ **The Django admin is type-checked** against django-stubs, its mixins take Django's signatures,
  and `GraphEntry` and `RelationEntry` import from `taxomesh.contrib.django.graph_types`. Its graph
  skips relations to a disabled item, and a move on it needs the permission to change that kind; a
  category's page shows *At the top level* read-only and saves parents through the service. Its
  debug page names each row as `svc.info` names it. The `django` extra takes Django 6.x.
- ⚠ **`Item.name` is required.** It may be `""`, but a stored item without the key fails to load.
- ⚠ **The graph holds one node per category**, shared by every parent and compared by identity;
  `walk()` enumerates it, and its roots are ordered by sort index, then identifier. The HTTP
  serializer raises `TaxomeshGraphTooLargeError`, from `taxomesh.contrib.api.errors`, past 100,000
  emitted nodes.
- ⚠ **External ids are `ExternalId` everywhere** (`str | int | UUID | None`); a batch lookup drops a
  `None` and keeps surrounding spaces and `""`, as a write does. Another type, such as `bytes` or a
  `bool`, raises `TypeError` where it was stored as its `str()`. `get_by_external_id` replaces
  `list_categories(external_id=…)`.
- ⚠ **`metadata` is plain JSON:** dicts with text keys, lists or tuples, text, finite numbers,
  booleans and `None`; a tuple is taken as a list, and a `StrEnum` or `IntEnum` member as its value.
  A `datetime`, `UUID`, `Decimal` or `NaN` in it, which the file stores wrote as text, and a value
  that contains itself raise `TaxomeshValidationError`.

### Added

- **Tags read back:** `tags.list(item=…)`, `items.list(tag=…)`, and the port's `list_item_tag_links`
  and `map_tags_by_id`.
- **Optimistic concurrency:** `update(…, expected_version=…)` raises `TaxomeshVersionConflictError`,
  which the HTTP edge answers with 409, and a version below 0 `TaxomeshValidationError`.
- **A graph limited to one category and its descendants,** `svc.graph(root=…)`, and
  `include_items=False`, which reads no item rows; a graph has `len`, subscript, `get`, `in` and
  `node.parents`, and a node's `ancestors()` and `descendants()` reach every level up or down.
- **`items.list(category=…, recursive=True)`**, `tags.update(metadata=…)`, `search(enabled=None)`.
- **One value where a lookup takes several:** `get_many(row)`, `get_many_by_external_id("ab")`,
  `get_many_related(item)` and `relation_types="covers"`.
- **Commands:** `category roots`, `add-parent` and `remove-parent`; `item remove-from` and `untag`;
  and `--state` on `item list-related`.
- **`taxomesh` exports the whole surface**, the service, collections, graph and nodes have
  readable reprs, a link's `str()` is a sentence, and [`llms.txt`](llms.txt) states the surface.
- **`YamlRepository` uses libyaml** when PyYAML has it, as its wheels do: one write is about four
  times faster on a large store.

### Fixed

- On JSON and YAML too, a delete removes every link that names the entity, and a load drops a link
  that names an entity that is not stored.
- An update or a `move` refused by any check stores nothing, on every backend. Metadata that is not
  plain JSON is refused before the write.
- Listing a parent's children or an item's categories reads only the rows not already cached.
- `items.search(category=…, enabled=False)` returns the disabled items it asks for, and
  `get_by_slug("")` answers `None` instead of an unrelated row without a slug.
- Building the graph, serializing it and `taxomesh graph` end on a stored cycle and on any depth;
  `taxomesh graph` stops past 100,000 drawn categories and names `--max-depth`, and refuses a
  negative one. `--show-config` writes values that TOML reads back, refuses a repository type that
  every command refuses, a `type` that is not text included, and the command runs over Django.
- The admin's graph views cost a constant number of queries and answer a failure as the HTTP edge
  does, and its forms save every field they show, a tag without metadata and a top-level category.
  An inline saves each row on its own, the new link before the old one goes, so a refused row keeps
  the link it had.
- `--direction` refuses a value other than its three, which used to answer as `both`.
- A failed file write raises `TaxomeshRepositoryError` from every write, not an `OSError`, and no
  later write carries the failed change to disk, while a write stopped after its file is in place
  keeps it; an operation whose later write fails clears its service's cache, so the service reads
  what was stored. A file repository's lock stops two threads passing one `expected_version`, and a
  write keeps the file's mode.
- An update builds on the stored row, so it never undoes a change another service made within
  `cache_ttl`, and a write that names an entity that another service deleted raises its not-found
  error. Two writes at the same moment, through one repository or on Django, run one after the
  other, so neither loses a change or stores a cycle, a deleted row or link, or a slug that the other
  took. On Django, a slug that another row holds raises `TaxomeshDuplicateSlugError`, not
  `TaxomeshExternalIdConflictError`, and a read given more identifiers or external ids than the
  database accepts in one query runs in several queries: a category of 40,000 items lists on SQLite.
- Migrations `0008`, `0011` and `0012` change the database `migrate --database` names.
  `0008`, released in 0.1.0a30, no longer fails on a store holding a row without an external id.
- A category name the model reads as `__root__`, such as `b"__root__"`, is refused as reserved.
