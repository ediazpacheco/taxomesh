# Changelog

All notable changes to taxomesh will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Performance

- `search_items()` and `search_categories()` now pre-normalize each candidate's
  name, slug, and external\_id exactly once per call (via an internal
  `SearchCandidate` object), eliminating the previous double-normalization of
  names and reducing per-call work for large catalogs.
- When `limit` is smaller than the number of scoring matches, a heap-based
  top-k selection (O(N log k)) replaces a full sort (O(N log N)), reducing
  per-keystroke cost for autocomplete workloads. Public API and result ordering
  are unchanged.

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
