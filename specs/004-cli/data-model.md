# Data Model: CLI (004-cli)

**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Source**: `specs/004-cli/spec.md` (FR-001 – FR-039)

---

## Layer Map — Changes from 003-service-repository

```
taxomesh/
├── exceptions.py                       ← unchanged
├── domain/
│   ├── types.py                        ← unchanged
│   ├── models.py                       ← MODIFIED: Category.description → str = ""
│   └── dag.py                          ← unchanged
├── ports/
│   └── repository.py                   ← EXTENDED: +delete_tag, +save_item_parent_link,
│                                                   +list_item_parent_links (18 methods total)
├── application/
│   └── service.py                      ← EXTENDED: +update_category, +update_item,
│                                                   +update_tag, +delete_tag,
│                                                   +place_item_in_category;
│                                                   list_items / list_categories
│                                                   gain optional keyword filter
└── adapters/
    ├── repositories/
    │   └── json_repository.py          ← EXTENDED: +delete_tag, +save_item_parent_link,
    │                                               +list_item_parent_links
    └── cli/                            ← NEW package
        ├── __init__.py
        ├── main.py                     ← Typer app + all command implementations
        └── config.py                   ← Config file loading; builds TaxomeshService
```

`pyproject.toml` — EXTENDED:
- `[project.dependencies]` gains `typer>=0.12`.
- `[project.scripts]` gains `taxomesh = "taxomesh.adapters.cli.main:app"`.

---

## `Category` Domain Model — Modified Field (`taxomesh/domain/models.py`)

```python
class Category(ModelBase):
    category_id: UUID
    name: Annotated[str, Field(max_length=256)]                        # unchanged (required)
    description: Annotated[str, Field(max_length=100_000)] = ""        # CHANGED: was Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

**Migration note**: Existing `taxomesh.json` files written by spec 003 store
`"description": null` for categories where description was not provided. A Pydantic
`BeforeValidator` on the `description` field coerces `None` → `""` at load time — no
data file migration is required.

```python
from typing import Annotated, Any
from pydantic import Field, field_validator

class Category(ModelBase):
    category_id: UUID
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("description", mode="before")
    @classmethod
    def _coerce_none_description(cls, v: object) -> object:
        return "" if v is None else v
```

---

## `TaxomeshRepositoryBase` Protocol — New Methods

```python
def delete_tag(self, tag_id: UUID) -> bool:
    """Delete a tag entity. Returns True if deleted, False if not found."""
    ...

def save_item_parent_link(self, link: ItemParentLink) -> None:
    """Upsert an item→category placement. If a link with the same (item_id, category_id)
    pair exists, its sort_index is updated in-place. No duplicate is created."""
    ...

def list_item_parent_links(self) -> list[ItemParentLink]:
    """Return all item→category placement records. Internal use by service layer."""
    ...
```

Total Protocol methods after this spec: **18**.

| Group | Methods |
|-------|---------|
| Category CRUD | `save_category`, `get_category`, `list_categories`, `delete_category` |
| Item CRUD | `save_item`, `get_item`, `list_items`, `delete_item` |
| Tag CRUD | `save_tag`, `get_tag`, `list_tags`, **`delete_tag`** ← new |
| Tag ↔ Item association | `assign_tag`, `remove_tag` |
| Category parent links | `save_category_parent_link`, `list_category_parent_links` |
| Item → Category placement | **`save_item_parent_link`**, **`list_item_parent_links`** ← new |

---

## `TaxomeshService` — New and Modified Methods

### `update_category`

```python
def update_category(
    self,
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> Category:
```

- Fetches the category (raises `TaxomeshCategoryNotFoundError` if absent).
- Applies only non-`None` fields via Pydantic `validate_assignment`.
- Saves and returns the updated category.

### `update_item`

```python
def update_item(
    self,
    item_id: UUID,
    enabled: bool | None = None,
) -> Item:
```

- Fetches the item (raises `TaxomeshItemNotFoundError` if absent).
- Applies `enabled` if not `None`.
- Saves and returns the updated item.

### `update_tag`

```python
def update_tag(
    self,
    tag_id: UUID,
    name: str | None = None,
) -> Tag:
```

- Fetches the tag (raises `TaxomeshTagNotFoundError` if absent).
- Applies `name` if not `None` (Pydantic enforces `max_length=25`).
- Saves and returns the updated tag.

### `delete_tag`

```python
def delete_tag(self, tag_id: UUID) -> None:
```

- Delegates to `self._repo.delete_tag(tag_id)`.
- Raises `TaxomeshTagNotFoundError` if the repository returns `False`.

### `place_item_in_category`

```python
def place_item_in_category(
    self,
    item_id: UUID,
    category_id: UUID,
    sort_index: int = 0,
) -> ItemParentLink:
```

- Validates that both the item and category exist (raises the appropriate `NotFoundError`).
- Constructs an `ItemParentLink` and delegates to `self._repo.save_item_parent_link(link)`.
  The repository handles upsert (idempotency).
- Returns the link.

### `list_items` (signature extended)

```python
def list_items(self, *, category_id: UUID | None = None) -> list[Item]:
```

- When `category_id` is `None`: returns all items (existing behaviour, unordered).
- When `category_id` is a UUID: validates the category exists (raises
  `TaxomeshCategoryNotFoundError` if absent), then returns items placed in that category
  ordered ascending by `sort_index`.

### `list_categories` (signature extended)

```python
def list_categories(self, *, parent_id: UUID | None = None) -> list[Category]:
```

- When `parent_id` is `None`: returns all categories (existing behaviour, unordered).
- When `parent_id` is a UUID: validates the category exists (raises
  `TaxomeshCategoryNotFoundError` if absent), then returns child categories of that parent
  ordered ascending by `sort_index`.

---

## `JsonRepository` — New Methods

### `delete_tag`

```python
def delete_tag(self, tag_id: UUID) -> bool:
```

- Removes entry from `self._tags`.
- Calls `self._flush()` if found.
- Returns `True` if deleted, `False` if not found.

### `save_item_parent_link`

```python
def save_item_parent_link(self, link: ItemParentLink) -> None:
```

- Upsert: searches `self._item_parent_links` for an existing record with the same
  `(item_id, category_id)` pair.
- If found, replaces `sort_index` in-place.
- If not found, appends the link.
- Calls `self._flush()`.

### `list_item_parent_links`

```python
def list_item_parent_links(self) -> list[ItemParentLink]:
```

- Returns a copy of `self._item_parent_links`.

### In-memory state (updated)

```python
_categories:            dict[UUID, Category]
_items:                 dict[UUID, Item]
_tags:                  dict[UUID, Tag]
_links:                 list[ItemTagLink]
_category_parent_links: list[CategoryParentLink]
_item_parent_links:     list[ItemParentLink]    # NEW
```

### JSON file schema (updated)

```json
{
  "categories":            { "<uuid>": { ...Category fields... } },
  "items":                 { "<uuid>": { ...Item fields... } },
  "tags":                  { "<uuid>": { ...Tag fields... } },
  "item_tag_links":        [ { "tag_id": "<uuid>", "item_id": "<uuid>" } ],
  "category_parent_links": [ { "category_id": "<uuid>", "parent_category_id": "<uuid>", "sort_index": 0 } ],
  "item_parent_links":     [ { "item_id": "<uuid>", "category_id": "<uuid>", "sort_index": 0 } ]
}
```

**Migration**: Existing files without `"item_parent_links"` will load with an empty list
(via `data.get("item_parent_links", [])`). Category records with `"description": null`
load as `""` via the `BeforeValidator`.

---

## CLI Command Summary

### Category

| Command | Arguments | Options |
|---------|-----------|---------|
| `category list` | — | `[--parent-id UUID]` |
| `category add` | — | `--name` (req), `--description`, `--parent-id`, `--sort-index` |
| `category delete` | `CATEGORY_ID` | — |
| `category update` | `CATEGORY_ID` | `--name`, `--description`, `--parent-id`, `--sort-index` (≥1 req) |

### Item

| Command | Arguments | Options |
|---------|-----------|---------|
| `item list` | — | `[--category-id UUID]` |
| `item add` | — | `--external-id` (req), `--category-id`, `--sort-index`, `--tag-id` |
| `item delete` | `ITEM_ID` | — |
| `item update` | `ITEM_ID` | `--enable/--disable`, `--category-id`, `--sort-index`, `--tag-id` (≥1 req) |
| `item add-to-category` | `ITEM_ID` | `--category-id` (req), `--sort-index` |
| `item add-to-tag` | `ITEM_ID` | `--tag-id` (req) |

### Tag

| Command | Arguments | Options |
|---------|-----------|---------|
| `tag list` | — | — |
| `tag add` | — | `--name` (req) |
| `tag delete` | `TAG_ID` | — |
| `tag update` | `TAG_ID` | `--name` (req) |

---

## Config File Schema (`taxomesh.toml`)

```toml
[repository]
type = "json"           # only supported value in this spec
path = "taxomesh.json"  # relative to CWD or absolute
```

Defaults when file is absent or keys are missing: `type = "json"`, `path = "taxomesh.json"`.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Any `TaxomeshError`, config parse error, or unexpected exception |
| 2 | Typer/Click built-in: missing required argument or option |

---

## `pyproject.toml` Changes

```toml
[project.dependencies]
# add:
"typer>=0.12",

[project.scripts]
taxomesh = "taxomesh.adapters.cli.main:app"
```
