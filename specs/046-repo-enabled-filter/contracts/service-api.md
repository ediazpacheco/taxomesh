# Contract: TaxomeshService Public API Changes

**Feature**: `046-repo-enabled-filter`

## `list_categories`

```python
def list_categories(
    self,
    *,
    parent_id: UUID | None = None,
    external_id: str | None = None,
    enabled: bool | None = True,
) -> list[Category]:
```

- `enabled=True` (default): only enabled categories returned.
- `enabled=False`: only disabled categories returned.
- `enabled=None`: all categories regardless of enabled state.
- Other parameters (`parent_id`, `external_id`) behaviour unchanged.

## `list_items`

```python
def list_items(
    self,
    *,
    category_id: UUID | None = None,
    enabled: bool | None = True,
) -> list[Item]:
```

- `enabled=True` (default): only enabled items returned.
- `enabled=None`: all items (used by `--include-disabled` CLI path).

## `list_categories_by_item`

```python
def list_categories_by_item(
    self,
    item_id: UUID,
    *,
    enabled: bool | None = True,
) -> list[Category]:
```

- Filters returned categories by enabled state in Python (see research.md Decision 3).
- Default `enabled=True` changes behaviour from previous contract (previously returned all).

## `search_items`

```python
def search_items(
    self,
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    category_id: UUID | None = None,
    enabled: bool = True,      # renamed from enabled_only
    fuzzy: bool = True,
    recursive: bool = False,
) -> list[Item]:
```

- `enabled_only` parameter renamed to `enabled`. Default unchanged (`True`).
- Behaviour unchanged: corpus slice filtered by `enabled` value.

## `search_categories`

```python
def search_categories(
    self,
    query: str,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    parent_id: UUID | None = None,
    enabled: bool = True,      # renamed from enabled_only
    fuzzy: bool = True,
) -> list[Category]:
```

- `enabled_only` parameter renamed to `enabled`. Default unchanged (`True`).

## `get_graph`

```python
def get_graph(self, *, enabled: bool | None = True) -> TaxomeshGraph:
```

- `enabled=True` (default): disabled categories and their items excluded from graph.
- `enabled=False`: only disabled categories and their items shown (admin inspection).
- `enabled=None`: all categories and items included regardless of state.

---

## `contrib.api` Handler Changes

### `list_categories`

```python
def list_categories(
    service: TaxomeshService,
    parent_id: UUID | None = None,
    include_disabled: bool = False,
) -> list[Category]:
```

`include_disabled=True` → passes `enabled=None` to service.

### `list_items`

```python
def list_items(
    service: TaxomeshService,
    category_id: UUID | None = None,
    include_disabled: bool = False,
) -> list[Item]:
```

### `get_graph`

```python
def get_graph(
    service: TaxomeshService,
    include_disabled: bool = False,
) -> TaxomeshGraph:
```

### Schema: `SearchItemsRequest`

```python
class SearchItemsRequest(BaseModel):
    q: ...
    limit: int = DEFAULT_SEARCH_LIMIT
    category_id: UUID | None = None
    recursive: bool = False
    enabled: bool = True          # renamed from enabled_only
    fuzzy: bool = True
```

### Schema: `SearchCategoriesRequest`

```python
class SearchCategoriesRequest(BaseModel):
    q: ...
    limit: int = DEFAULT_SEARCH_LIMIT
    parent_id: UUID | None = None
    enabled: bool = True          # renamed from enabled_only
    fuzzy: bool = True
```

---

## CLI Changes

### `category list`

```
taxomesh category list [--parent-id UUID] [--include-disabled]
```

`--include-disabled`: when present, passes `enabled=None` to service (returns all).

### `item list`

```
taxomesh item list [--category-id UUID] [--include-disabled]
```

`--include-disabled`: when present, passes `enabled=None` to service.

### `graph`

```
taxomesh graph [--show-relations/--no-show-relations] [--max-depth N] [--include-disabled]
```

`--include-disabled`: when present, passes `enabled=None` to `service.get_graph(enabled=None)`
(returns all categories and items regardless of state).
