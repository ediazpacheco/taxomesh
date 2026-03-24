# Changelog

All notable changes to taxomesh will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0a40] — 2026-03-24

### Added

#### `get_items_by_external_ids()` and `get_categories_by_external_ids()` — bulk external ID lookup

`TaxomeshService` now exposes two bulk resolution methods:

```python
service.get_items_by_external_ids(
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Item]

service.get_categories_by_external_ids(
    external_ids: Iterable[str],
    *,
    enabled: bool | None = None,
) -> dict[str, Category]
```

Both methods resolve multiple domain objects by `external_id` in a **single bulk
operation**, replacing the N+1 pattern that resulted from looping over
`get_item_by_external_id` / `get_category_by_external_id`.

**Input handling**:
- Each value is normalised with `str(value).strip()`.
- Blank / whitespace-only values are silently ignored.
- Duplicate IDs are deduplicated before the query.
- Missing IDs are silently omitted from the result — no exception is raised.

**`enabled` filter** (`bool | None`, default `None`):
- `True` — return only enabled items/categories.
- `False` — return only disabled items/categories.
- `None` (default) — return all matching regardless of enabled state.

A disabled item/category whose ID is supplied is included when `enabled=None`,
and excluded (silently omitted, not an error) when `enabled=True`.

**`get_categories_by_external_ids` note**: the root category is always excluded from
results, consistent with `get_category_by_external_id`.

**Adapter support**: all three repository backends implement the bulk query natively —
`JsonRepository` and `YAMLRepository` scan their in-memory store once per call;
`DjangoRepository` issues a single `WHERE external_id IN (...)` SQL query.

**Caching**: both methods are TTL-cached via the same `@memoize` mechanism used by
all other service read methods.

---

## [0.1.0a39] — 2026-03-23

### Added

#### Public-library logging best practices

- `taxomesh` root logger now registers a `NullHandler` at import time, following
  Python public-library conventions and preventing "No handlers could be found"
  warnings in applications that do not configure logging.
- Dangling-link warning in `list_related_items_for_sources()` now includes the
  method name, `str(source_item_id)`, and an "orphaned" label for easier
  debugging.
- Warning log in `list_related_items_for_sources()` is guarded with
  `isEnabledFor(WARNING)` to avoid unnecessary string interpolation when the
  `WARNING` level is suppressed.
- `_resolve_linked_url` calls in the Django admin module upgraded from `DEBUG`
  to `WARNING` level so misconfigured URL lookups surface in standard production
  log configurations.

---

## [0.1.0a38] — 2026-03-23

### Added

#### `list_related_items_for_sources()` — `skip_on_error` parameter

`TaxomeshService.list_related_items_for_sources()` now accepts a keyword-only
`skip_on_error: bool = True` parameter.

When `True` (default), dangling links — where a `target_item_id` no longer exists
in the repository — are **skipped** instead of raising an exception. Each skipped
link emits a `WARNING`-level log message via the `taxomesh.application.service`
logger, including `source_item_id`, `target_item_id`, and `relation_type` to aid
database-level debugging.

When `False`, the original `TaxomeshItemNotFoundError` is raised immediately
(existing strict behaviour, preserved for callers that rely on it).

The change is fully backwards-compatible: existing call sites require no modification.

---

## [0.1.0a34] — 2026-03-21

### ⚠ BREAKING CHANGES

#### Repository-level `enabled` filtering — default behaviour changed

All listing and search methods now return only **enabled** records by default.
Previously, disabled records were included silently and callers were responsible
for filtering. The `enabled_only` parameter name on search methods has been
removed and replaced by `enabled`.

##### Migration

| Before | After |
|--------|-------|
| `svc.list_categories()` — returned all categories | `svc.list_categories()` — returns only enabled; pass `enabled=None` for all |
| `svc.list_items()` — returned all items | `svc.list_items()` — returns only enabled; pass `enabled=None` for all |
| `svc.list_categories_by_item(id)` — included disabled categories | `svc.list_categories_by_item(id)` — returns only enabled; pass `enabled=None` for all |
| `svc.get_graph()` — included disabled nodes | `svc.get_graph()` — excludes disabled; pass `enabled=None` for all |
| `svc.search_items("q", enabled_only=True)` | `svc.search_items("q", enabled=True)` |
| `svc.search_categories("q", enabled_only=False)` | `svc.search_categories("q", enabled=False)` |
| CLI `taxomesh category list` — returned all | `taxomesh category list` — returns only enabled; add `--include-disabled` for all |
| CLI `taxomesh item list` — returned all | `taxomesh item list` — returns only enabled; add `--include-disabled` for all |
| CLI `taxomesh graph` — showed all nodes | `taxomesh graph` — shows only enabled; add `--include-disabled` for all |
| API `list_categories` — returned all | API `list_categories` — returns only enabled; pass `include_disabled=true` for all |
| API `list_items` — returned all | API `list_items` — returns only enabled; pass `include_disabled=true` for all |
| API `get_graph` — returned all nodes | API `get_graph` — returns only enabled; pass `include_disabled=true` for all |
| `SearchItemsRequest(enabled_only=True)` | `SearchItemsRequest(enabled=True)` |
| `SearchCategoriesRequest(enabled_only=True)` | `SearchCategoriesRequest(enabled=True)` |

##### Repository port

`TaxomeshRepositoryBase.list_categories` and `list_categories` gain a keyword-only
`enabled: bool | None = True` parameter with three-way semantics:
- `True` (default) — only enabled records
- `False` — only disabled records
- `None` — all records regardless of state

All adapter implementations (JSON, YAML, Django ORM, InMemory) implement this parameter.
The Django adapter applies the filter at ORM level (`WHERE enabled = <value>`); no
full-table fetch occurs for enabled-filtered calls.

### Added

#### `TaxomeshService.update_category` — `enabled` parameter

`update_category()` now accepts `enabled: bool | None = None`, consistent with `update_item()`.

---

## [0.1.0a33] — 2026-03-21

### Added

#### `TaxomeshService.list_categories_by_item`

New public method `list_categories_by_item(item_id: UUID) -> list[Category]` exposes the
item→categories traversal direction.

- Returns only enabled categories by default; pass `enabled=None` to include disabled ones.
- Raises `TaxomeshItemNotFoundError` if the item does not exist.
- Returns `[]` if the item has no placements.
- Result memoized at `DEFAULT_CACHE_TTL`; automatically invalidated by `place_item_in_category`, `remove_item_from_category`, and `reorder_items_in_category`.

---

## [0.1.0a30] — 2026-03-21

### ⚠ BREAKING CHANGES

#### `external_id` is now a 1:1 unique identifier — migration required

`external_id` on `Item` and `Category` has changed from a duplicate-tolerant
lookup key to a **true unique identifier**.  Every layer of the library has been
updated accordingly.  Consumer apps that link their own records to taxomesh
Items or Categories via `external_id` **must** migrate before upgrading.

---

##### What changed

| Layer | Before | After |
|---|---|---|
| Domain model type | `str` (default `""`) | `str \| None` (default `None`) |
| Duplicate external\_ids | allowed | **forbidden** — raises `TaxomeshExternalIdConflictError` |
| Service lookup | `get_items_by_external_id(…) → list[Item]` | `get_item_by_external_id(…) → Item \| None` |
| Service lookup | `get_categories_by_external_id(…) → list[Category]` | `get_category_by_external_id(…) → Category \| None` |
| Repository protocol | `list_items_by_external_id(str) → list[Item]` | `get_item_by_external_id(str) → Item \| None` |
| Repository protocol | `list_categories_by_external_id(str) → list[Category]` | `get_category_by_external_id(str) → Category \| None` |
| "No match" signal | empty list (`[]`) | `None` |
| "Absent" value | empty string (`""`) | `None` |
| Django ORM | `CharField(db_index=True)` | `CharField(null=True, unique=True)` |
| Django migration | — | `0008_unique_external_id` converts `""` → `NULL`, adds `UNIQUE` constraint |

---

##### New exception

```python
TaxomeshExternalIdConflictError(TaxomeshValidationError)
```

Raised by `save_item` / `save_category` (all three repository backends) when a
non-`None` `external_id` is already held by a **different** record of the same
type.  Re-saving a record with its own existing `external_id` (same primary key)
never raises.

```python
from taxomesh import TaxomeshExternalIdConflictError

try:
    service.update_item(item_id, external_id="ext-123")
except TaxomeshExternalIdConflictError as exc:
    # "external_id 'ext-123' is already assigned to another item."
    print(exc)
```

---

##### Updated service API

```python
# Look up an Item by its external identifier
item: Item | None = service.get_item_by_external_id("ext-123")
item: Item | None = service.get_item_by_external_id(some_uuid)   # coerced to str
item: Item | None = service.get_item_by_external_id(None)        # returns None immediately

# Look up a Category by its external identifier (root category never returned)
cat: Category | None = service.get_category_by_external_id("ext-456")
```

Both methods accept `str | int | UUID | None`.  `None` input short-circuits
immediately without touching the repository.  Results are memoized for
`DEFAULT_CACHE_TTL` seconds.

---

##### Consumer app migration checklist

1. **Remove** all calls to `get_items_by_external_id` — replace with
   `get_item_by_external_id` and handle `Item | None` instead of `list[Item]`.

2. **Remove** all calls to `get_categories_by_external_id` — replace with
   `get_category_by_external_id` and handle `Category | None`.

3. **Replace** the "empty list = orphan" pattern with a `None` check:

   ```python
   # Before
   results = service.get_items_by_external_id(ext_id)
   if not results:
       # orphan — external record has no taxomesh Item
       ...
   item = results[0]

   # After
   item = service.get_item_by_external_id(ext_id)
   if item is None:
       # no taxomesh Item for this external_id
       ...
   ```

4. **Audit** your data for duplicate `external_id` values before running the
   Django migration.  The migration converts `""` → `NULL` automatically, but
   two records sharing the same non-empty `external_id` string will **block**
   the `UNIQUE` constraint from being applied.  Resolve duplicates manually
   (set one of them to `None`) before migrating:

   ```python
   # Find conflicts before migrating
   from collections import Counter
   counts = Counter(
       item.external_id
       for item in service.list_items()
       if item.external_id  # skip empty/None
   )
   duplicates = [eid for eid, n in counts.items() if n > 1]
   ```

5. **Run the Django migration** (if using `DjangoRepository`):

   ```bash
   python manage.py migrate taxomesh
   ```

   Migration `0008_unique_external_id` converts all `external_id = ""` rows to
   `NULL` and then adds the `UNIQUE` constraint on both `taxomesh_item` and
   `taxomesh_category`.

6. **Update `external_id` defaults** — any code that creates Items or Categories
   with `external_id=""` as an explicit "no reference" sentinel should be
   updated to pass `external_id=None` (or omit the argument, since `None` is
   now the default).

7. **Catch `TaxomeshExternalIdConflictError`** wherever your app assigns
   `external_id` values at write time, so accidental duplicates surface
   immediately instead of silently creating data inconsistencies.

---

##### Unchanged behaviours

- Multiple `NULL` / `None` external IDs **do not conflict** — a taxonomy where
  most Items have no external reference is fully supported.
- `external_id` remains optional on both `Item` and `Category`.
- UUID and `int` inputs are still coerced to `str` before storage.
- The `search_items()` and `search_categories()` methods continue to score
  against `external_id` as a search field.
- `list_categories(external_id=…)` still works; it now returns a list of at
  most one element (and is not sorted, since there can be only one match).

---

## [0.1.0a29] — 2026-03-17

### Performance

- `search_items()` and `search_categories()` now pre-normalize each candidate's
  name, slug, and external\_id exactly once per call (via an internal
  `SearchCandidate` object), eliminating the previous double-normalization of
  names and reducing per-call work for large catalogs.
- When `limit` is smaller than the number of scoring matches, a heap-based
  top-k selection (O(N log k)) replaces a full sort (O(N log N)), reducing
  per-keystroke cost for autocomplete workloads. Public API and result ordering
  are unchanged.
- Unfiltered `search_items()` and `search_categories()` now maintain an
  internal pre-normalized candidate corpus (`_item_corpus`, `_category_corpus`)
  that is built once on the first call and reused across repeated searches on
  the same service instance. Candidate normalization (name, slug, external\_id)
  is performed exactly once per corpus lifetime instead of on every search call.
  The corpus is automatically invalidated by any item or category write
  operation (`create_*`, `update_*`, `delete_*`). Category-filtered and
  recursive searches are unaffected and continue to load candidates directly.
- Unfiltered `search_items()` now routes candidate loading through the
  memoized `list_items()` service path instead of calling the repository
  directly, eliminating redundant I/O when the service-level cache is warm.

### Changed (internal)

- `TaxomeshService.get_debug()` now returns two additional keys:
  `item_corpus_size` (integer count of pre-normalized item candidates when the
  corpus is warm, `None` when cold or invalidated) and `category_corpus_size`
  (same for categories).

---

## [0.1.0a27] — 2026-03-16

### Added

#### `TaxomeshService.list_related_items_for_sources` *(new)*

```python
service.list_related_items_for_sources(
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> dict[UUID, dict[str, list[Item]]]
```

Batch counterpart to `list_related_items`.  Resolves all outgoing relations for
every item in `source_item_ids` in **two repository calls** — one batch link
query and one `list_items` — eliminating the N+1 pattern that arises when
calling `list_related_items` in a loop.

- Relation types are normalised to lower-case before filtering; `"COVERS"` and
  `"covers"` are equivalent.
- Duplicate source IDs are deduplicated automatically.
- Source items with no matching outgoing links are **absent** from the result
  (not represented as empty dicts).
- Raises `TaxomeshItemNotFoundError` if a target referenced by a matched link
  does not exist.

**Example:**

```python
result = service.list_related_items_for_sources(
    [song_a.item_id, song_b.item_id],
    relation_types=["performed_by"],
)
# {
#     song_a.item_id: {"performed_by": [artist]},
#     song_b.item_id: {"performed_by": [artist]},
# }
```

#### `TaxomeshRepository.list_item_relation_links_for_sources` *(new protocol method)*

```python
repo.list_item_relation_links_for_sources(
    source_item_ids: Collection[UUID],
    *,
    relation_types: Collection[str] | None = None,
) -> list[ItemRelationLink]
```

Low-level batch method on the repository protocol.  Returns raw
`ItemRelationLink` objects for many source items in a single storage
operation, ordered by
`(source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC)`.

- An empty `source_item_ids` collection returns `[]` immediately without
  hitting storage.
- `relation_types=None` or `relation_types=[]` means no filter.
- Implemented by all three built-in backends: `JsonRepository`,
  `YAMLRepository`, and `DjangoRepository`.  The Django backend issues a
  **single ORM query** with `source_item_id__in`.

**Example:**

```python
links = repo.list_item_relation_links_for_sources(
    [song_a_id, song_b_id],
    relation_types=["performed_by"],
)
# [
#     ItemRelationLink(source=song_a_id, target=artist_x_id, relation_type="performed_by"),
#     ItemRelationLink(source=song_b_id, target=artist_x_id, relation_type="performed_by"),
# ]
```

### Changed

- **Django migration `0006`**: added composite index
  `(source_item_id, relation_type, sort_index, target_item_id)` on
  `taxomesh_item_relation_link`.  This index covers:
  - Outgoing queries filtered by both `source_item_id` and `relation_type`
    (the existing unique-together index could not serve this because
    `target_item_id` sits between the two columns).
  - The full `ORDER BY` emitted by `list_item_relation_links_for_sources`,
    allowing the DB to use an index scan instead of a filesort.

---

## [0.1.0a26] — 2026-03-15

### Added

#### `TaxomeshService.search_items` / `TaxomeshService.search_categories` *(contrib.api — spec 037)*

HTTP-level search handlers added to `taxomesh.contrib.api`:

- `GET /items/search?q=<query>&limit=<n>` — fuzzy item search via
  `TaxomeshService.fuzzy_search_items`.
- `GET /categories/search?q=<query>&limit=<n>` — fuzzy category search via
  `TaxomeshService.fuzzy_search_categories`.

Response schema: `SearchResultsSchema` with a `results` list of
`ItemSchema` / `CategorySchema`.

#### Service read cache *(spec 028)*

`TaxomeshService` read methods decorated with `@memoize(DEFAULT_CACHE_TTL)`
(TTL: 5 s).  Cached methods: `get_item`, `get_category`, `list_items`,
`list_categories`, `list_related_items`, `fuzzy_search_items`,
`fuzzy_search_categories`.  Cache is invalidated automatically on any write
that touches the affected data.

---

## [0.1.0a25] — 2026-03-10

### Added

- **spec 036 — service/repo parity**: parametrized test suite covering all
  three backends (`JsonRepository`, `YAMLRepository`, `DjangoRepository`)
  for every public service method.
- **spec 035 — Django ordering indexes**: `name` indexes on `CategoryModel`
  and `ItemModel`; composite `(parent_category_id, sort_index)` on
  `CategoryParentLinkModel`; composite `(category_id, sort_index)` on
  `ItemParentLinkModel`.
- **spec 034 — default sort_index**: `CategoryParentLink` and
  `ItemParentLink` now auto-assign `sort_index` as `max(existing) + 1` when
  not explicitly provided.

---

## [0.1.0a24] — 2026-03-05

### Added

- **spec 033 — fuzzy search**: `TaxomeshService.fuzzy_search_items` and
  `fuzzy_search_categories` using `rapidfuzz` for token-set-ratio scoring
  with Unicode normalisation.
- **spec 032 — external_id indexes**: B-tree indexes on
  `taxomesh_item.external_id` and `taxomesh_category.external_id`.
- **spec 031 — metadata JSON editor**: Ace Editor widget in Django admin for
  `metadata` JSONField on `ItemModel` and `CategoryModel`.

---

## [0.1.0a23] — 2026-02-28

### Added

- **spec 030 — graph drag-and-drop**: HTML5 drag-and-drop reordering of
  category and item parent links in the Django admin graph view; persists
  `sort_index` changes via AJAX endpoint.
- **spec 029 — graph serializer**: `GraphSerializer` that turns the full
  category/item DAG into a JSON-serialisable dict; used by the admin graph
  view and the contrib.api graph endpoint.
- **spec 028 — contrib.api**: `taxomesh.contrib.api` package — thin
  Pydantic-based request/response schemas and handler functions for HTTP
  adapters (FastAPI, Django views, etc.).

---

## [0.1.0a22] — 2026-02-20

### Added

- **spec 027 — autocomplete FK widget**: Django admin foreign-key fields on
  `ItemRelationLinkModel` now use `AutocompleteSelect` widget.
- **spec 026 — admin service debug**: debug panel in Django admin surfacing
  service version, repository type, and live config values.
- **spec 025 — graph admin UX**: visual graph panel in Django admin with
  collapsible category tree and item assignments.
- **spec 024 — graph enhancements**: `TaxomeshService.get_category_subtree`
  and `get_item_ancestors` CLI commands + Django admin actions.

---

## [0.1.0a21] — 2026-02-10

### Added

- **spec 023 — item relations**: `ItemRelationLink` domain model; repository
  methods `save_item_relation_link`, `list_item_relation_links`,
  `delete_item_relation_link`; service methods `relate_items`,
  `list_item_relations`, `list_related_items`, `remove_item_relation`.
  Django backend: `ItemRelationLinkModel` with migration `0003`.
- **spec 022 — unified `__str__` / admin links**: consistent `__str__`
  representations for all domain models; clickable object links in all
  Django admin list views.
- **spec 021 — optional external_id**: `Item.external_id` is now
  `str | None` (was required); Django migration `0002` relaxes the column
  constraint.

---

## [0.1.0a1] — 2026-01-01

### Added

- Initial library skeleton: `Item`, `Category`, `Tag`, `CategoryParentLink`,
  `ItemParentLink`, `ItemTagLink` domain models (Pydantic v2).
- `TaxomeshRepositoryBase` protocol with `JsonRepository` and
  `YAMLRepository` built-in backends.
- `TaxomeshService` facade exposing item CRUD, category CRUD, tag CRUD,
  parent-link management, slug lookup, external-id lookup, and fuzzy search.
- Typer CLI with `graph`, `config dump`, and item/category subcommands.
- Optional Django contrib package (`taxomesh.contrib.django`) with ORM
  models, admin views, and `DjangoRepository`.
- Optional contrib.api package (`taxomesh.contrib.api`) with Pydantic
  schemas and handler functions for HTTP adapters.
