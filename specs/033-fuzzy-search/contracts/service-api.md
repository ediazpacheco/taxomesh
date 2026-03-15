# Service API Contract: Fuzzy Search (033-fuzzy-search)

## `TaxomeshService.search_items`

### Signature

```python
def search_items(
    self,
    query: str,
    *,
    limit: int = 20,
    category_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
    recursive: bool = False,
) -> list[Item]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Search text. Normalized before matching. |
| `limit` | `int` | `20` | Maximum number of results. Must be > 0. |
| `category_id` | `UUID \| None` | `None` | Restrict candidates to this category. `None` = all items. |
| `enabled_only` | `bool` | `True` | When `True`, disabled items are excluded. |
| `fuzzy` | `bool` | `True` | When `False`, fuzzy similarity scoring is skipped. |
| `recursive` | `bool` | `False` | When `True` and `category_id` is set, include items from all descendant categories. |

### Returns

`list[Item]` — ranked by match quality descending, truncated to `limit`.

### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | `limit <= 0` |
| `TaxomeshCategoryNotFoundError` | `category_id` is provided but no such category exists |

### Behavior

- Empty or whitespace-only `query` returns `[]` immediately.
- `recursive=True` without `category_id` is silently ignored (all items are already candidates).
- Results are deduplicated by `item_id` (an item in multiple categories appears once).
- Sorting: descending score, then ascending normalized name as tie-breaker.
- `external_id == ""` is silently skipped during matching.

---

## `TaxomeshService.search_categories`

### Signature

```python
def search_categories(
    self,
    query: str,
    *,
    limit: int = 20,
    parent_id: UUID | None = None,
    enabled_only: bool = True,
    fuzzy: bool = True,
) -> list[Category]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | — | Search text. Normalized before matching. |
| `limit` | `int` | `20` | Maximum number of results. Must be > 0. |
| `parent_id` | `UUID \| None` | `None` | Restrict candidates to direct children of this parent. `None` = all categories. |
| `enabled_only` | `bool` | `True` | When `True`, disabled categories are excluded. |
| `fuzzy` | `bool` | `True` | When `False`, fuzzy similarity scoring is skipped. |

### Returns

`list[Category]` — ranked by match quality descending, truncated to `limit`.

### Raises

| Exception | Condition |
|-----------|-----------|
| `ValueError` | `limit <= 0` |
| `TaxomeshCategoryNotFoundError` | `parent_id` is provided but no such category exists |

### Behavior

- Empty or whitespace-only `query` returns `[]` immediately.
- The internal root category (`__root__`) is always excluded from results.
- Sorting: descending score, then ascending normalized name as tie-breaker.
- `external_id == ""` is silently skipped during matching.

---

## `SearchEngine` (internal — `taxomesh/application/search.py`)

Not part of the public API. Internal to the `application/` layer.

### `SearchEngine.normalize(text: str) -> str` *(staticmethod)*

Returns the normalized form of any text string for comparison purposes.

### `SearchEngine.score_candidate(query: str, name: str, slug: str, external_id: str, *, fuzzy: bool = True) -> float | None`

Returns a float score (≥ 0) if the candidate should be included in results, or `None` if it should be excluded.

- `query` is already normalized (caller's responsibility).
- `name`, `slug`, `external_id` are raw values normalized internally.
- When `fuzzy=False`, RapidFuzz scoring is skipped entirely. Only boost signals contribute.
