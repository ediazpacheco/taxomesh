# Python API Reference

Use this reference when you are integrating `taxomesh` directly in Python code.

`TaxomeshService` is the main application-facing entry point. It lets you create and
query taxonomy data while keeping your own business entities linked through `external_id`
when needed.

## Categories

```python
from taxomesh import TaxomeshService

svc = TaxomeshService()

root = svc.create_category(name="Root Topic")
child = svc.create_category(name="Child Topic", slug="child-topic")
svc.add_category_parent(child.category_id, root.category_id, sort_index=10)

children = svc.list_categories(parent_id=root.category_id)
updated = svc.update_category(child.category_id, description="Updated")

# Delete a category (shown on a throwaway so "child-topic" stays available below)
scratch = svc.create_category(name="Scratch Topic")
svc.delete_category(scratch.category_id)

# Look up by slug
cat = svc.get_category_by_slug("child-topic")  # raises TaxomeshCategoryNotFoundError if missing
```

## Items

```python
from uuid import uuid4

item_a = svc.create_item(name="Article", external_id=123, slug="article-123")
item_b = svc.create_item(name="Track", external_id=uuid4())
item_c = svc.create_item(name="Post", external_id="article-abc")

svc.update_item(item_a.item_id, enabled=False)
all_items = svc.list_items()

# Look up by slug
item = svc.get_item_by_slug("article-123")  # raises TaxomeshItemNotFoundError if missing
```

## Tags

```python
tag = svc.create_tag(name="featured")
svc.assign_tag(tag.tag_id, item_c.item_id)    # idempotent
svc.remove_tag(tag.tag_id, item_c.item_id)    # no-op if already removed
svc.delete_tag(tag.tag_id)
```

## Graph snapshot

```python
graph = svc.get_graph()
for node in graph.roots:
    print(node.category.name)
```

## Slug lookup

```python
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError

cat = svc.get_category_by_slug("child-topic")   # returns Category or raises TaxomeshCategoryNotFoundError
item = svc.get_item_by_slug("article-123")       # returns Item or raises TaxomeshItemNotFoundError
```

Slugs are optional URL-friendly identifiers. They must be unique within their namespace
(categories or items). Both methods raise a typed not-found exception — they never return `None`.

## External ID lookup

`external_id` is a 1:1 unique identifier — each Item or Category owns at most one `external_id`, and each `external_id` value is held by at most one record of its type.

```python
from taxomesh.domain.models import Category, Item

item: Item | None = svc.get_item_by_external_id("article-abc")
category: Category | None = svc.get_category_by_external_id("legacy-category-id")
```

Both methods return `None` when no match is found, and also return `None` immediately when called with `external_id=None` (no repository call). UUID and `int` inputs are coerced to `str` automatically.

```python
from taxomesh import TaxomeshExternalIdConflictError

try:
    item = svc.create_item(name="Article", external_id="article-abc")
except TaxomeshExternalIdConflictError:
    # another Item already owns "article-abc"
    ...
```

## Fuzzy Search

`search_items()` and `search_categories()` search by name, slug, and external ID with
typo tolerance, accent-insensitivity, and ranked results. Powered by
[rapidfuzz](https://github.com/maxbachmann/RapidFuzz).

### search_items

```python
# Basic search — returns up to 20 items, enabled only, fuzzy on
results = svc.search_items("piazola")           # finds "Piazzolla" via typo tolerance
results = svc.search_items("agustin magaldi")   # finds "Agustín Magaldi" (accent-stripped)
results = svc.search_items("d arienzo")         # finds "D'Arienzo" (punctuation-insensitive)

# Limit results
results = svc.search_items("tango", limit=5)

# Include disabled items
results = svc.search_items("tango", enabled=False)

# Restrict to direct members of a category
results = svc.search_items("tango", category_id=cat.category_id)

# Restrict to a full category subtree (category + all descendants)
results = svc.search_items("tango", category_id=cat.category_id, recursive=True)

# Exact/prefix/substring only — no fuzzy scoring
results = svc.search_items("tango", fuzzy=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Search text; whitespace-only returns `[]` immediately |
| `limit` | `int` | `20` | Maximum results; raises `ValueError` if `<= 0` |
| `category_id` | `UUID \| None` | `None` | Restrict candidates to this category |
| `recursive` | `bool` | `False` | When `True` and `category_id` is set, includes all descendant categories |
| `enabled` | `bool` | `True` | Exclude disabled items when `True` |
| `fuzzy` | `bool` | `True` | Include fuzzy (typo-tolerant) scoring |

Returns `list[Item]`, sorted by descending match score. Ties broken alphabetically by
normalised name. Raises `TaxomeshCategoryNotFoundError` if `category_id` does not exist.

### search_categories

```python notest
# Basic category search
results = svc.search_categories("orkesta tipika")   # finds "Orquesta Típica"
results = svc.search_categories("tango romantico")  # finds "Tango Romántico"

# Direct children of a specific parent only
results = svc.search_categories("tango", parent_id=parent.category_id)

# Include disabled categories
results = svc.search_categories("tango", enabled=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Search text; whitespace-only returns `[]` immediately |
| `limit` | `int` | `20` | Maximum results; raises `ValueError` if `<= 0` |
| `parent_id` | `UUID \| None` | `None` | Restrict candidates to direct children of this category |
| `enabled` | `bool` | `True` | Exclude disabled categories when `True` |
| `fuzzy` | `bool` | `True` | Include fuzzy (typo-tolerant) scoring |

Returns `list[Category]`, sorted by descending match score. The internal root category
is always excluded. Raises `TaxomeshCategoryNotFoundError` if `parent_id` does not exist.

### Ranking and normalization

Before any matching, both query and candidate fields are normalized:
- Diacritics and accents stripped (NFD decomposition)
- Punctuation characters (`'`, `-`, `.`, `_`, `\`) converted to spaces
- Lowercased and whitespace collapsed

Match quality tiers, from highest to lowest:

| Tier | Example |
|------|---------|
| Exact match on name or slug | query `"gallo ciego"` → name `"Gallo Ciego"` |
| Prefix of name | query `"tango"` → name `"Tango Style"` |
| Prefix of slug | query `"tango"` → slug `"tango-style"` |
| Word-prefix in name | query `"style"` → name `"Tango Style"` |
| Substring of name | query `"ango"` → name `"Tango"` |
| Substring of slug | query `"ango"` → slug `"el-tango"` |
| Substring of `external_id` | query `"sku"` → `external_id="SKU-001"` |
| Fuzzy (rapidfuzz ≥ 70/100) | query `"piazola"` → name `"Piazzolla"` |

The `external_id` field is only matched when it is non-empty. Pass `fuzzy=False` to
restrict to the deterministic tiers only (no rapidfuzz scoring).

## Read caching

`TaxomeshService` caches its read methods in memory for **5 seconds**
(`DEFAULT_CACHE_TTL`). The cache is per-process — under a multi-worker server each
worker holds its own — and **every write clears every cache**, so creating, updating or
deleting anything invalidates the lot at once. There is no per-key invalidation.

### Batch reads prime the per-row cache

Listing categories leaves those categories cached, so a later lookup of one of them is
served from memory:

| Read | Primes |
|---|---|
| `list_categories(parent_id=…)` | `get_category`, for every category returned |
| `list_categories_by_item(item_id)` | `get_category`, for every category returned |
| `list_items(category_id=…)` | **nothing** — see below |

This matters most when walking a tree, because each child becomes the next call's
`parent_id` and `list_categories` validates its parent through `get_category`:

```python notest
def walk(service, parent_id):
    for child in service.list_categories(parent_id=parent_id):
        yield child
        yield from walk(service, child.category_id)   # `child` is not re-read
```

Such a walk pays exactly **one** category lookup — its own root, which nothing returned
as a child — regardless of how many nodes it visits. On a measured 75-node, 3-level tree
that is 102 storage reads against 177 without priming.

A row is cached with the value storage returned, *before* any `enabled` filter is
applied, so a category omitted from a filtered result is still cached with its true
value and a later `get_category` on it returns the row rather than raising.

### Why listing items does not prime

`list_items(category_id=…)` deliberately leaves `get_item`'s cache alone. The cache has
no eviction — an entry lives until the next write — and items are large. Measured on a
real corpus, priming one big item listing costs **98 MB** and the whole item corpus
**108 MB** (≈14 KB per row, driven by `metadata`), against **0.17 MB** for every
category in the same corpus.

If your application exposes an endpoint that lists a large category's items, priming it
would let one request pin that much memory until the next write. On a read-mostly
deployment, where writes are rare, that is effectively for the life of the process. If
you want item priming for a small corpus, the prerequisite is an eviction policy in the
cache rather than a flag.

## Error model

All library exceptions inherit from `TaxomeshError`.

- `TaxomeshNotFoundError`
  - `TaxomeshCategoryNotFoundError`
  - `TaxomeshItemNotFoundError`
  - `TaxomeshTagNotFoundError`
- `TaxomeshValidationError`
  - `TaxomeshCyclicDependencyError`
  - `TaxomeshDuplicateSlugError`
- `TaxomeshRepositoryError`
- `TaxomeshConfigError`
- `TaxomeshRootCategoryError`

← [Back to README](../README.md)
