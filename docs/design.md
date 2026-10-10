# Design

How taxomesh is built, and why its public surface looks the way it does.

This page is the reference for the architecture and the API design of taxomesh. Each rule says
what it protects and which test enforces it. When the code or a test disagrees with this page, the
disagreement is a defect to fix, not a new rule. A rule changes on this page, in the same change as
the code.

Other rules have their own pages:

- the code conventions, the checks and what a contribution needs: [CONTRIBUTING.md](../CONTRIBUTING.md);
- each member, its arguments and its errors: the [Python API](python-api.md);
- the tools and the dependencies: `pyproject.toml`.

To learn how to use the library, read the [README](../README.md) first.

The code blocks below run top to bottom as one script, and the documentation tests execute them.

## Architecture

Dependencies point inward: `adapters → application → domain`.

| Module | Holds |
|---|---|
| `domain/` | The models (`Category`, `Item`, `Tag` and the four links), the graph read model, cycle detection (`dag.py`), and the public types (`refs.py`, `types.py`) |
| `ports/repository.py` | `TaxomeshRepositoryBase`, the storage port, a `typing.Protocol` |
| `application/` | `TaxomeshService`, the three collections under `collections/`, and search |
| `adapters/repositories/` | `YamlRepository`, `JsonRepository` and `DjangoRepository` |
| `adapters/cli/` | The `taxomesh` command (Typer), installed with the `cli` extra |
| `contrib/api/` | Framework-agnostic HTTP handlers, request schemas and error mapping |
| `contrib/django/` | The ORM models, migrations and admin behind `DjangoRepository` |
| `_config.py` | The composition root: reads `taxomesh.toml` and builds the adapter it names |
| `repositories.py` | Re-exports the three adapters |
| `utils/memoize.py` | The read cache |

No module under `application/` imports an adapter or an integration, lazily or not, and
`tests/test_architecture.py` asserts it. `TaxomeshService.__init__` reaches `_config.py`, lazily,
only when it is given no repository.

**One entry point.** `TaxomeshService(repository=None, *, config_path=None, cache_ttl=5.0)` is the
only class a caller builds. Given no repository, the service reads `taxomesh.toml`
([Configuration](configuration.md)). Without that file, it uses a YAML file at the YAML adapter's
default path. The members for categories, items and tags are on `svc.categories`, `svc.items` and
`svc.tags`, and the graph snapshot is `svc.graph()`.

**An adapter keeps its own defaults.** Only `yaml_repository.py` and `json_repository.py` define a
default file path (`DEFAULT_YAML_PATH`, `DEFAULT_JSON_PATH`). When `taxomesh.toml` names a file
backend and no path, `_config.py` builds the backend with no path argument, so the adapter applies
its own default. `_config.py` imports the two constants only to report which path a configuration
resolves to. It never repeats their values.

**The port reports absence and the service raises.** The port, `TaxomeshRepositoryBase`, is a
`typing.Protocol`: a backend inherits nothing, and mypy checks that it has the port's members
([Custom backends](repositories.md#custom-backends)). A port lookup is `find_*` and returns `None`
on a miss, a keyed batch read is `map_*`, and a listing is `list_*`. No name means one thing on the
port and another on the service. The port's `save_category` and `save_item` return the stored
row, and `atomic()` groups writes that belong together: on Django they roll back together, while a
file backend writes each one to disk on its own. Cascades on delete are part of the port
contract, and one suite, `tests/adapters/repositories/test_repository_contract.py`, holds all four
implementations to it.

## Names

A type's name says what kind of thing it is:

| Kind | Name | Example |
|---|---|---|
| A public `Protocol` or `ABC` | ends in `Base` | `TaxomeshRepositoryBase` |
| A domain model | the noun, with no suffix | `Category`, `Item`, `Tag` |
| A link between two entities | ends in `Link` | `CategoryParentLink` |
| The collection of one kind of entity | ends in `Collection` | `CategoryCollection` |
| A storage adapter | ends in `Repository`; an acronym is written as a word | `YamlRepository`, `JsonRepository` |
| The service | ends in `Service` | `TaxomeshService` |
| An error | `Taxomesh`, what failed, then `Error` | `TaxomeshCyclicDependencyError` |
| An HTTP request schema | ends in `Request` | `CreateCategoryRequest` |
| An HTTP handler | `<namespace>_<member>`, after the member it calls | `categories_get_by_slug` |

`tests/test_architecture.py` asserts the `Base` suffix. `tests/test_packaging.py` asserts that
`YamlRepository` has no alias spelled `YAMLRepository`. The handler names are asserted with the
handlers ([HTTP handlers](#http-handlers)).

Two more rules apply to a member's name:

- No public name contains `_for_`.
- `_by_` names a unique key that a lookup addresses rows by: `_by_id`, `_by_slug` or
  `_by_external_id`. It never names a filter over a relation: the categories an item is placed in
  are `categories.list(item=…)`.

`tests/surface/test_api_law.py` asserts both rules.

## The law: subscript raises, `get*` never does

A member's name predicts what it returns, what it does when the thing is absent, and what its
arguments mean. The three collections and the graph are containers, and
[The container law](python-api.md#the-container-law) lists every form a collection supports:

```python
from uuid import uuid4

from taxomesh import TaxomeshService

svc = TaxomeshService()
music = svc.categories.create("Music")
missing = uuid4()

assert svc.categories[music.category_id] == music
assert svc.categories.get(missing) is None
assert missing not in svc.categories
try:
    svc.categories[missing]
except KeyError:  # TaxomeshCategoryNotFoundError is a KeyError
    pass
else:
    raise AssertionError("subscript must raise")
```

- **The law is about absence.** A `get*` member never raises for the key it was asked about. A
  miss is `None`, the supplied default, or a key left out of the returned dict. That answer is
  documented, so it is not a hidden failure. A listing that matches nothing returns an empty tuple.
- A subject or a filter that names an entity that is not stored is a wrong address, not a miss.
  Every member that takes one raises the not-found error of that entity.
- `list*` returns a tuple and `get_many*` a new dict, so a name never hides the container type.
  `get_by_<key>` names a unique key and returns the row or `None`.
- **Filters are keyword-only.** The subject is the only positional parameter.
- **The member is on the collection of the entity it changes.** An operation that joins two
  entities is a member of the collection of the entity that it changes, and that entity comes
  first: `items.tag(item, tag)`.
- `enabled` is one filter with one meaning on every member that takes it.
  [The enabled filter](python-api.md#the-enabled-filter) says what each value selects and which
  default each member has.
- Every not-found error is a `KeyError` and every validation error a `ValueError`, so a caller who
  knows only the standard library catches them. No `pydantic.ValidationError` leaves a member. An
  argument of the wrong type raises `TypeError`, as `int(None)` does, and is no `TaxomeshError`: it
  is a mistake to fix, not a failure to handle. A value of the right type that is refused raises
  `TaxomeshValidationError`, as `int("sarasa")` raises `ValueError`.
- A collection does not iterate, and is not a `collections.abc.Mapping`, which builds `keys()`,
  `values()` and `==` on iteration. Iterating a collection would read every row in a loop that does
  not show that cost, and would have to choose a meaning for `enabled` without telling the caller.
  So `iter()` and `reversed()` raise `TypeError`, `list()` enumerates instead, and `len()` is the
  one form that reads every row.

## Errors

Every error class of the library inherits `TaxomeshError`, so one `except` clause catches every
failure the library reports. No member hides a failure: a failure that the caller is not told
about is a defect. The one standard exception that a member raises on purpose is `TypeError`, for
an argument of the wrong type.

Every error class is importable from `taxomesh`, except `TaxomeshGraphTooLargeError`. Only the HTTP
serializer raises that error, so `taxomesh.contrib.api.errors` defines it, beside the serializer.
[Errors](python-api.md#errors) shows the tree. `tests/test_exceptions.py` asserts the bases, and
`tests/test_packaging.py` asserts where each class is importable from.

## The public surface

`taxomesh/__init__.py` exports the whole public surface, in six groups:

- the service, `TaxomeshService`;
- the errors;
- the seven models: `Category`, `Item`, `Tag` and the four links;
- the read models: `TaxomeshGraph`, `CategoryNode`, `RelatedItems`, `TaxomeshInfo` and
  `RepositoryInfo`;
- the storage port, `TaxomeshRepositoryBase`;
- the public types: `ExternalId`, `UnsetType`, `UNSET`, `CategoryRef`, `ItemRef`, `TagRef` and
  `Direction`.

A type that a public signature uses is exported, so a caller can write the same annotation:
`external_id: ExternalId | UnsetType = UNSET` needs all three names. `ModelBase`, the models'
shared base, and `normalise_external_id`, the conversion behind `ExternalId`, are in no public
signature, so they are not exported.

The storage adapters are imported from `taxomesh.repositories`, and importing that module imports
no Django. The HTTP modules are imported from `taxomesh.contrib.api`. `taxomesh` itself re-exports
neither. [`llms.txt`](../llms.txt) names every export, and `tests/test_packaging.py` asserts the
list and each import.

## Frozen rows

A row never changes in place. The models are frozen, `metadata` is frozen all the way down
(`FrozenDict` and `FrozenList` in `domain/types.py`), and `update` builds a new, validated row:

```python
from taxomesh import TaxomeshVersionConflictError

renamed = svc.categories.update(music, name="Recorded music", expected_version=music.version)
assert music.name == "Music" and renamed.name == "Recorded music"
try:
    music.name = "Sound"
except ValueError:
    pass
else:
    raise AssertionError("a row refuses assignment")
try:
    svc.categories.update(music, name="Again", expected_version=music.version)
except TaxomeshVersionConflictError:
    pass
else:
    raise AssertionError("a stale version is refused")
```

**Why:** a memoized read returns the same object to every caller within the cache's lifetime. If
rows were mutable, one caller's edit would change what the next caller reads, and change the
cache with it. With frozen rows, the mistake raises an error where it is made. Sequences come back
as tuples and mappings as a new dict on every call for the same reason, and a graph is a snapshot
on every backend. A row carrying a `metadata` dict is not hashable.

`expected_version` is optimistic concurrency. The repository compares the stored version and writes
`version + 1` in one step. When the stored row is at another version, or is no longer stored, the
update raises `TaxomeshVersionConflictError`, which the HTTP edge maps to 409. Of two writers that
pass the same version, the second is refused that way: through one repository on a YAML or JSON
file, whose lock makes each call one step for every thread, or across processes on Django. Every
write reads what it changes from storage, never from the cache: `update` builds on the stored row,
so without `expected_version` it replaces only the fields it is given, and a write that names an
entity that another service deleted raises its not-found error.

`metadata` is plain JSON, checked where a caller's value comes in rather than on the model: every
backend then stores the same thing, and a store already holding another value still loads.
[Writing](python-api.md#writing) says what plain JSON accepts.

Every `str` field of a model declares a `max_length`, as `Annotated[str, Field(max_length=N)]`, and
`domain/constants.py` names each limit. A model therefore refuses an oversized value when it is
built, whichever backend stores it. The text inside `metadata` has no such limit.
`tests/domain/test_models.py` and `tests/domain/test_constants.py` assert the limits field by
field. No test checks that a new field declares one.

## The root invariant

Storage keeps the implicit root, a category that no member returns. A category is at the top level
exactly when it has no other parent, and the top level is stored as a parent link to the implicit
root:

```python
jazz = svc.categories.create("Jazz")
assert {c.name for c in svc.categories.roots()} == {"Recorded music", "Jazz"}

svc.categories.add_parent(jazz, renamed)
assert [c.name for c in svc.categories.roots()] == ["Recorded music"]
assert [node.category.name for node in svc.graph().roots] == ["Recorded music"]

svc.categories.remove_parent(jazz, renamed)
assert {c.name for c in svc.categories.roots()} == {"Recorded music", "Jazz"}
```

- `add_parent` deletes the link to the implicit root inside the same `atomic()` block, which on
  Django is one transaction. When a category loses its last parent, through `remove_parent`, `move`
  or the deletion of the parent, the link to the implicit root is stored again.
- `roots()` and `graph().roots` read the same links, so they agree on any stored data.
- No signature names the implicit root: `None` stands for the top level in `move` and `reorder`.
  Every member treats the identifier of the implicit root as that of a category that is not
  stored: `get` answers `None`, and subscript or a filter raises not-found.
- A store that breaks the invariant is repaired: the file adapters normalise it on load, and Django
  migration `0011_root_invariant` does it once.

**Why:** "top level" has one meaning, which every read agrees on. To list the top level, a member
reads the links to the implicit root and then the rows they name, rather than the parents of every
category.

## The per-service cache

Each `TaxomeshService` owns one `ReadCache` (`utils/memoize.py`) and gives it to the three
collections it builds. A `@memoize` method reaches its owner's cache at call time.

- `cache_ttl` (5 seconds by default) is how long an entry is served, measured from the read that
  made it; an expired entry is dropped when its member stores the next one. `0` stores nothing,
  and a negative or NaN lifetime is refused.
- A write through a service clears that service's entries, and no other service's. Each search
  corpus is held for the same lifetime.
- There is no module-level cache registry. Nothing outside the objects that hold a cache keeps an
  entry alive.
- A read may be stale within `cache_ttl`; a write is not, since it reads what it changes from
  storage. On that basis, threads may share a service.
- A collection is never constructed directly: built any other way, it would hold a cache of its
  own and miss every entry the service's collections primed.

**Why:** a cache shared across services would let one service's write clear another's entries,
and would make staleness depend on who else is running. Owned by one service, `cache_ttl` is the
only bound on staleness a caller has to reason about: another process writing to the same Django
database is seen once the entry expires. A YAML or JSON file is read when its repository is built
and written whole, so a file has one writer, and a repository refuses to write over a change another
writer made before it writes, rather than lose it.

### Why category listings prime the cache and item listings do not

A category listing *primes* the per-row cache: it puts each row it reads into the cache that
subscript, `get` and `in` read. A filtered listing first takes the rows that this cache holds, and
reads the rest in one batch. A tree walk passes each child it receives as the `parent` of its next
call, so each level finds its parent in the cache. `tests/service/test_memoize_priming.py` asserts
the result: a cold walk reads one category through `find_category`, the category it starts at.

A listing primes each row before it applies the `enabled` filter, so the cached row is the stored
row. A category that a filtered listing leaves out is still served by its identifier, with its
stored `enabled` value. An entry's lifetime starts at the read that fetched the row, and a later
cache hit does not extend it.

Item listings do neither. The cache has no size bound and item rows are large, so a listing does not
keep every item it reads. The same test file measures the cost. An item fetched after a listing
costs one read. A pattern that lists items and then reads each one costs at most one read more than
reading each item by its identifier, for each `items.list(category=…)` call in the pattern.

## Entity or identifier

Every parameter that names a category, an item or a tag takes a row or its `UUID`, container keys
included. The aliases are `CategoryRef`, `ItemRef` and `TagRef`, and the parameter is a noun
(`category`, `parent`, `item`), never `…_id`:

```python
assert svc.categories[jazz] == svc.categories[jazz.category_id]

kind_of_blue = svc.items.create("Kind of Blue")
for wrong in ("Jazz", kind_of_blue):
    try:
        svc.categories[wrong]
    except TypeError:
        pass
    else:
        raise AssertionError("only a Category or a UUID names a category")
```

- Anything that is neither a row of that kind nor a `UUID`, a row of another kind included, raises
  `TypeError` before storage is read, as `os.fspath` does for a path.
- The conversion happens once, at the collection boundary (`category_id_of` and its siblings in
  `domain/refs.py`), so a memoized read is keyed by the `UUID` whichever form was passed.
- A batch lookup takes one key or a collection of them, as `str.startswith` takes one prefix or a
  tuple, and so does `relation_types`. The port takes a collection. `reorder` takes a sequence,
  because one row is not an order.
- The port and the HTTP request schemas keep `UUID` and `…_id`.

**Why:** callers hold rows. A caller passes the row it holds, and does not take out its identifier
at every call site. The one conversion point keeps the cache from seeing two keys for one row.

## HTTP handlers

taxomesh ships no HTTP server. `taxomesh.contrib.api` gives an application that has one the request
schemas, the handlers and the error mapping, so an endpoint is short: in the
[HTTP guide](http-api-integration.md), the body of each FastAPI endpoint is one to four lines.

- A handler takes the `TaxomeshService` as its first positional argument and calls one member of
  the service. The handler holds no logic of its own.
- A handler is named `<namespace>_<member>` after the member it calls, or `graph` for
  `svc.graph()`. It keeps that member's contract: a lookup returns `None` on a miss, and the
  application turns that `None` into its 404.
- A handler returns what its member returns: domain models, not serialized data or a response.
  `serializers` turns rows and graphs into JSON-ready values, apart from the handlers.
- `errors.to_tuple(exc)` is the one error mapping. The application wraps its result in its own
  response.
- No module of `taxomesh.contrib.api` imports a web framework. pydantic is the one HTTP-related
  dependency, and it is a core dependency.

`tests/contrib/test_api_handlers.py` asserts the names, the set of handlers, that a lookup's return
type admits `None`, and each handler's answer. `tests/contrib/test_api_schema_service_parity.py`
asserts that each request schema carries the arguments of its member. No test checks the
service-first signature, the absence of logic in a handler, or the imports of `contrib/api`.

## Other rules

- **`update` keeps a field by default.** Every `update` field defaults to `UNSET`, which keeps the
  stored value. `None` clears a nullable field.
- **Removing an absent link is a no-op**, as `set.discard` is. Deleting an absent row raises.
- **Cycles are refused in the domain.** `domain/dag.py` checks every new parent link before it is
  written, and no adapter repeats the check.
- **A parent link carries its own order.** A parent link is `(category_id, parent_category_id,
  sort_index)`, so a category under several parents has a position under each one.
- **No process in the product.** `taxomesh/` and `tests/` contain no task, specification,
  requirement or review-finding identifier, no account of how the code changed, and no citation of
  a planning document. The code states what is true now, and `CHANGELOG.md` holds the history.

## Where the rules are enforced

| Rule | Test |
|---|---|
| The layers, and the `Base` suffix | `tests/test_architecture.py` |
| Member names, and no collection is a `Mapping` | `tests/surface/test_api_law.py` |
| Every public signature, keyword-only filters included | `tests/surface/public_surface.txt`, a ledger edited only on purpose |
| The `enabled` defaults | `tests/service/test_enabled_defaults.py` |
| Stdlib error bases, and the wrong type's `TypeError` | `tests/test_exceptions.py`, `tests/service/test_stdlib_errors.py` |
| The exports | `tests/test_packaging.py` |
| Frozen rows and tuples | `tests/domain/test_frozen_models.py`, `tests/service/test_immutable_rows.py`, `tests/surface/test_sequence_returns.py` |
| Plain-JSON metadata | `tests/service/test_metadata_json.py` |
| `UNSET` defaults | `tests/service/test_update_unset.py` |
| String lengths | `tests/domain/test_models.py`, `tests/domain/test_constants.py` |
| Entity or identifier | `tests/service/test_entity_or_id.py` |
| One value where a lookup takes several | `tests/service/test_single_values.py` |
| Idempotent removal, and unstored subjects | `tests/service/test_removal_idempotent.py`, `tests/service/test_unknown_subjects.py` |
| A listing's wrong address | `tests/service/test_batch_placement_reads.py` |
| The root invariant | `tests/service/test_root_invariant.py`, `tests/service/test_root_invisible.py` |
| The per-service cache | `tests/service/test_service_cache.py`, `tests/utils/test_memoize.py` |
| Category listings prime the cache, item listings do not | `tests/service/test_memoize_priming.py` |
| The port contract | `tests/adapters/repositories/test_repository_contract.py` |
| The handlers' names and contracts | `tests/contrib/test_api_handlers.py` |
| No process in the product | `tests/test_no_process_ids.py` |

Tests enforce these rules, so a change that breaks one fails the build; no rule depends on a
reviewer noticing. The behavior behind the names is asserted on every backend: the port's `None` on
a miss, each `get*` member's answer to an absent key, and what each `enabled` value selects. The
port contract suite runs on all four implementations, and so does each service test that uses the
shared `service` fixture.
