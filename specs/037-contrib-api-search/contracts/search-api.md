# Contract: Search API — taxomesh.contrib.api

## Module: `taxomesh.contrib.api.schemas`

### SearchItemsRequest

```python
class SearchItemsRequest(BaseModel):
    q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT      # 20
    category_id: UUID | None = None
    recursive: bool = False
    enabled_only: bool = True
    fuzzy: bool = True
```

### SearchCategoriesRequest

```python
class SearchCategoriesRequest(BaseModel):
    q: Annotated[str, Field(max_length=MAX_SEARCH_QUERY_LENGTH)]
    limit: int = DEFAULT_SEARCH_LIMIT      # 20
    parent_id: UUID | None = None
    enabled_only: bool = True
    fuzzy: bool = True
```

---

## Module: `taxomesh.contrib.api.handlers`

### search_items

```python
def search_items(
    service: TaxomeshService,
    params: SearchItemsRequest,
) -> list[Item]:
    """Search items using all parameters from SearchItemsRequest.

    Delegates 1:1 to service.search_items(). Adds no business logic.

    Args:
        service: The TaxomeshService instance.
        params: Validated search parameters.

    Returns:
        Items ranked by relevance, trimmed to params.limit.

    Raises:
        ValueError: If params.limit <= 0 (raised by service).
        TaxomeshCategoryNotFoundError: If params.category_id does not exist.
    """
```

### search_categories

```python
def search_categories(
    service: TaxomeshService,
    params: SearchCategoriesRequest,
) -> list[Category]:
    """Search categories using all parameters from SearchCategoriesRequest.

    Delegates 1:1 to service.search_categories(). Adds no business logic.

    Args:
        service: The TaxomeshService instance.
        params: Validated search parameters.

    Returns:
        Categories ranked by relevance, trimmed to params.limit.

    Raises:
        ValueError: If params.limit <= 0 (raised by service).
        TaxomeshCategoryNotFoundError: If params.parent_id does not exist.
    """
```

---

## Module: `taxomesh.contrib.api.serializers`

### items_to_list

```python
def items_to_list(items: list[Item]) -> list[dict[str, Any]]:
    """Serialize a list of Item domain objects to JSON-compatible dicts.

    Args:
        items: List of Item instances (e.g. returned by search_items).

    Returns:
        List of plain dicts produced by Item.model_dump(mode="json").
        Empty list when items is empty.
    """
```

### categories_to_list

```python
def categories_to_list(categories: list[Category]) -> list[dict[str, Any]]:
    """Serialize a list of Category domain objects to JSON-compatible dicts.

    Args:
        categories: List of Category instances (e.g. returned by search_categories).

    Returns:
        List of plain dicts produced by Category.model_dump(mode="json").
        Empty list when categories is empty.
    """
```

---

## Usage Example (consumer integration)

```python
from taxomesh.contrib.api import handlers, schemas, serializers

# Parse params from HTTP query string (framework-specific — shown as FastAPI example)
@app.get("/search/items")
def search_items_endpoint(q: str, limit: int = 20, fuzzy: bool = True):
    params = schemas.SearchItemsRequest(q=q, limit=limit, fuzzy=fuzzy)
    items = handlers.search_items(service, params)
    return {"results": serializers.items_to_list(items)}
```
