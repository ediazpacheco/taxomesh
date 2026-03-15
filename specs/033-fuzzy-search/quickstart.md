# Quickstart: Fuzzy Search APIs (033-fuzzy-search)

## Adding the Dependency

Add `rapidfuzz>=3.0` to `[project] dependencies` in `pyproject.toml`:

```toml
dependencies = [
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
    "typer>=0.12",
    "rapidfuzz>=3.0",
]
```

Run `uv sync` (or `pip install -e .`) to install.

## Using the Search API

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Typo-tolerant item search
items = service.search_items("piazola")
# → returns items matching "Piazzolla" and similar

# Accent-insensitive category search
categories = service.search_categories("orquesta tipica")
# → returns categories matching "Orquesta Típica"

# Scoped item search (direct members of a category)
items = service.search_items("tango", category_id=my_category_id)

# Scoped with subtree traversal
items = service.search_items("tango", category_id=my_category_id, recursive=True)

# Include disabled items
items = service.search_items("piazola", enabled_only=False)

# Disable fuzzy (exact/prefix/substring only)
items = service.search_items("piazzolla", fuzzy=False)

# Limit results
items = service.search_items("tango", limit=5)
```

## Normalization Examples

The search normalizes both the query and candidate fields before comparing:

| Input | Normalized |
|-------|-----------|
| `"Agustín"` | `"agustin"` |
| `"D'Arienzo"` | `"d arienzo"` |
| `"gallo-ciego"` | `"gallo ciego"` |
| `"  Piazola  "` | `"piazola"` |
| `"Piazzolla"` | `"piazzolla"` |

## Ranking Behavior

Results are sorted by match quality (best first):
1. Exact normalized matches (highest rank)
2. Prefix matches
3. Substring matches
4. Fuzzy similarity matches (lowest rank, but still included)

## Error Handling

```python
from taxomesh.exceptions import TaxomeshCategoryNotFoundError

# Empty query returns [] (no error)
assert service.search_items("") == []

# Invalid limit raises ValueError
try:
    service.search_items("tango", limit=0)
except ValueError:
    pass  # expected

# Non-existent category_id raises TaxomeshCategoryNotFoundError
try:
    service.search_items("tango", category_id=uuid4())
except TaxomeshCategoryNotFoundError:
    pass  # expected
```
