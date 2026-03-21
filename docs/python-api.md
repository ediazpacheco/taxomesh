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
svc.delete_category(updated.category_id)

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
results = svc.search_items("tango", enabled_only=False)

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
| `enabled_only` | `bool` | `True` | Exclude disabled items when `True` |
| `fuzzy` | `bool` | `True` | Include fuzzy (typo-tolerant) scoring |

Returns `list[Item]`, sorted by descending match score. Ties broken alphabetically by
normalised name. Raises `TaxomeshCategoryNotFoundError` if `category_id` does not exist.

### search_categories

```python
# Basic category search
results = svc.search_categories("orkesta tipika")   # finds "Orquesta Típica"
results = svc.search_categories("tango romantico")  # finds "Tango Romántico"

# Direct children of a specific parent only
results = svc.search_categories("tango", parent_id=parent.category_id)

# Include disabled categories
results = svc.search_categories("tango", enabled_only=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Search text; whitespace-only returns `[]` immediately |
| `limit` | `int` | `20` | Maximum results; raises `ValueError` if `<= 0` |
| `parent_id` | `UUID \| None` | `None` | Restrict candidates to direct children of this category |
| `enabled_only` | `bool` | `True` | Exclude disabled categories when `True` |
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
