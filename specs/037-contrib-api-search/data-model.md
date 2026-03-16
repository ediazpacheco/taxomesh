# Data Model: 037-contrib-api-search

## New Pydantic Request Schemas

These are request input objects — not domain models. They live in `taxomesh/contrib/api/schemas.py`.

### SearchItemsRequest

| Field | Type | Default | Constraint | Notes |
|-------|------|---------|------------|-------|
| `q` | `str` | required | `max_length=MAX_SEARCH_QUERY_LENGTH` | Search query text |
| `limit` | `int` | `DEFAULT_SEARCH_LIMIT` (20) | none | Max results to return |
| `category_id` | `UUID \| None` | `None` | none | Restrict to items in this category |
| `recursive` | `bool` | `False` | none | Include items in descendant categories |
| `enabled_only` | `bool` | `True` | none | Exclude disabled items when True |
| `fuzzy` | `bool` | `True` | none | Enable rapidfuzz scoring |

Maps directly to `TaxomeshService.search_items(query, limit, category_id, enabled_only, fuzzy, recursive)`.

### SearchCategoriesRequest

| Field | Type | Default | Constraint | Notes |
|-------|------|---------|------------|-------|
| `q` | `str` | required | `max_length=MAX_SEARCH_QUERY_LENGTH` | Search query text |
| `limit` | `int` | `DEFAULT_SEARCH_LIMIT` (20) | none | Max results to return |
| `parent_id` | `UUID \| None` | `None` | none | Restrict to direct children of this parent |
| `enabled_only` | `bool` | `True` | none | Exclude disabled categories when True |
| `fuzzy` | `bool` | `True` | none | Enable rapidfuzz scoring |

Maps directly to `TaxomeshService.search_categories(query, limit, parent_id, enabled_only, fuzzy)`.

---

## New Constant

`MAX_SEARCH_QUERY_LENGTH: Final[int] = 500` — added to `taxomesh/domain/constants.py`.

---

## No New Domain Models

This feature introduces no new domain entities (`Category`, `Item`, `Tag`, etc.) and requires no repository changes. All domain logic lives in the existing `TaxomeshService.search_items()` and `TaxomeshService.search_categories()` methods.

---

## Serializer Output Shapes

These are the dict shapes produced by the new serializers. They are derived from `model_dump(mode="json")` on the respective domain models, which already exist.

### `items_to_list(items: list[Item]) -> list[dict[str, Any]]`

Each dict mirrors `Item.model_dump(mode="json")`. Key fields:

| Key | Type | Example |
|-----|------|---------|
| `item_id` | `str` (UUID) | `"3f5a1c..."` |
| `name` | `str` | `"Anibal Troilo"` |
| `slug` | `str` | `"anibal-troilo"` |
| `external_id` | `str` | `""` or `"uuid-del-content"` |
| `enabled` | `bool` | `true` |
| `metadata` | `dict` | `{"short_bio": "..."}` |

### `categories_to_list(categories: list[Category]) -> list[dict[str, Any]]`

Each dict mirrors `Category.model_dump(mode="json")`. Key fields:

| Key | Type | Example |
|-----|------|---------|
| `category_id` | `str` (UUID) | `"9a2b3c..."` |
| `name` | `str` | `"Tango"` |
| `slug` | `str` | `"tango"` |
| `external_id` | `str` | `""` |
| `enabled` | `bool` | `true` |
| `metadata` | `dict` | `{}` |
