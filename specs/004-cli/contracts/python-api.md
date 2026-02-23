# Contract: CLI and Service Extension Python API (004-cli)

**Type**: CLI command contract + Python library extension contract
**Date**: 2026-02-23
**Last Updated**: 2026-02-23 (rev 3)
**Layer**: `taxomesh.adapters.cli`, `taxomesh.application.service`,
           `taxomesh.ports.repository`, `taxomesh.adapters.repositories.json_repository`

---

## CLI Entry Point

```
taxomesh [--config PATH] <group> <command> [ARGS] [OPTIONS]
```

| Group | Commands |
|-------|----------|
| `category` | `list`, `add`, `delete`, `update` |
| `item` | `list`, `add`, `delete`, `update`, `add-to-category`, `add-to-tag` |
| `tag` | `list`, `add`, `delete`, `update` |

---

## Category Commands

### `taxomesh category list`

```
taxomesh category list [--parent-id UUID]
```

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--parent-id` | UUID | no | Returns child categories of this parent, ordered by `sort_index`. When absent, returns all categories. |

Prints categories. Exit 0 always.

---

### `taxomesh category add`

```
taxomesh category add --name TEXT [--description TEXT] [--parent-id UUID] [--sort-index INT]
```

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--name` | str | yes | max 256 chars |
| `--description` | str | no | max 100 000 chars |
| `--parent-id` | UUID | no | must refer to an existing category |
| `--sort-index` | int | no | default 0; only meaningful when `--parent-id` is given |

**Exit 0**: prints the created category (and confirmation if parent was added).
**Exit 1**: `TaxomeshCategoryNotFoundError` (parent not found), `TaxomeshCyclicDependencyError`,
or validation error.

---

### `taxomesh category delete`

```
taxomesh category delete CATEGORY_ID
```

**Exit 0**: prints confirmation.
**Exit 1**: `TaxomeshCategoryNotFoundError` or invalid UUID.

---

### `taxomesh category update`

```
taxomesh category update CATEGORY_ID [--name TEXT] [--description TEXT]
                                     [--parent-id UUID] [--sort-index INT]
```

At least one of `--name`, `--description`, or `--parent-id` must be provided.

**Exit 0**: prints the updated category.
**Exit 1**: not found, validation error, cycle error, or no options provided.

---

## Item Commands

### `taxomesh item list`

```
taxomesh item list [--category-id UUID]
```

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--category-id` | UUID | no | Returns items placed in this category, ordered by `sort_index`. When absent, returns all items. |

Prints items. Exit 0 always.

---

### `taxomesh item add`

```
taxomesh item add --external-id TEXT [--category-id UUID [--sort-index INT]] [--tag-id UUID]
```

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--external-id` | str (raw) | yes | Parsed as UUID → int → str |
| `--category-id` | UUID | no | Places item in category after creation |
| `--sort-index` | int | no | default 0; only meaningful with `--category-id` |
| `--tag-id` | UUID | no | Assigns tag to item after creation |

**Exit 0**: prints the created item; confirmations for any assignments made.
**Exit 1**: validation error, entity not found (for assignment targets).

---

### `taxomesh item delete`

```
taxomesh item delete ITEM_ID
```

**Exit 0**: prints confirmation.
**Exit 1**: `TaxomeshItemNotFoundError` or invalid UUID.

---

### `taxomesh item update`

```
taxomesh item update ITEM_ID [--enable | --disable]
                             [--category-id UUID [--sort-index INT]] [--tag-id UUID]
```

At least one option must be provided.

**Exit 0**: prints the updated item; confirmations for any assignments made.
**Exit 1**: not found, validation error, or no options provided.

---

### `taxomesh item add-to-category`

```
taxomesh item add-to-category ITEM_ID --category-id UUID [--sort-index INT]
```

Places an existing item in a category. Idempotent (upserts sort_index).

**Exit 0**: prints confirmation.
**Exit 1**: `TaxomeshItemNotFoundError`, `TaxomeshCategoryNotFoundError`, or invalid UUID.

---

### `taxomesh item add-to-tag`

```
taxomesh item add-to-tag ITEM_ID --tag-id UUID
```

Assigns an existing tag to an existing item. Idempotent.

**Exit 0**: prints confirmation.
**Exit 1**: `TaxomeshItemNotFoundError`, `TaxomeshTagNotFoundError`, or invalid UUID.

---

## Tag Commands

### `taxomesh tag list`

```
taxomesh tag list
```

Prints all tags. Exit 0 always.

---

### `taxomesh tag add`

```
taxomesh tag add --name TEXT
```

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--name` | str | yes | max 25 chars |

**Exit 0**: prints the created tag.
**Exit 1**: name too long or other validation error.

---

### `taxomesh tag delete`

```
taxomesh tag delete TAG_ID
```

**Exit 0**: prints confirmation.
**Exit 1**: `TaxomeshTagNotFoundError` or invalid UUID.

---

### `taxomesh tag update`

```
taxomesh tag update TAG_ID --name TEXT
```

**Exit 0**: prints the updated tag.
**Exit 1**: not found or validation error.

---

## `taxomesh.toml` Config File Contract

```toml
[repository]
type = "json"           # only "json" supported in this spec
path = "taxomesh.json"  # optional; relative to CWD or absolute
```

Config file is read from CWD by default; overridden with `taxomesh --config <path> ...`.

---

## Service Extension Methods

Import: `from taxomesh import TaxomeshService`

### `list_items` (extended)

```python
service.list_items(*, category_id: UUID | None = None) -> list[Item]
```

- `category_id=None`: returns all items (existing behaviour).
- `category_id=<uuid>`: returns items placed in that category, ordered by `sort_index`.

**Raises**: `TaxomeshCategoryNotFoundError` when `category_id` is provided but not found.

---

### `list_categories` (extended)

```python
service.list_categories(*, parent_id: UUID | None = None) -> list[Category]
```

- `parent_id=None`: returns all categories (existing behaviour).
- `parent_id=<uuid>`: returns child categories of that parent, ordered by `sort_index`.

**Raises**: `TaxomeshCategoryNotFoundError` when `parent_id` is provided but not found.

---

### `update_category`

```python
service.update_category(
    category_id: UUID,
    name: str | None = None,
    description: str | None = None,
) -> Category
```

**Raises**: `TaxomeshCategoryNotFoundError`; `pydantic.ValidationError` on constraint violations.

---

### `update_item`

```python
service.update_item(
    item_id: UUID,
    enabled: bool | None = None,
) -> Item
```

**Raises**: `TaxomeshItemNotFoundError`.

---

### `update_tag`

```python
service.update_tag(
    tag_id: UUID,
    name: str | None = None,
) -> Tag
```

**Raises**: `TaxomeshTagNotFoundError`; `pydantic.ValidationError` if name > 25 chars.

---

### `delete_tag`

```python
service.delete_tag(tag_id: UUID) -> None
```

**Raises**: `TaxomeshTagNotFoundError`.

---

### `place_item_in_category`

```python
service.place_item_in_category(
    item_id: UUID,
    category_id: UUID,
    sort_index: int = 0,
) -> ItemParentLink
```

Idempotent — if the `(item_id, category_id)` placement already exists, the `sort_index`
is updated (upsert). Returns the resulting `ItemParentLink`.

**Raises**: `TaxomeshItemNotFoundError`; `TaxomeshCategoryNotFoundError`.

---

## Repository Extension Methods

Import: `from taxomesh.ports.repository import TaxomeshRepositoryBase`

```python
def delete_tag(self, tag_id: UUID) -> bool:
    """Delete a tag entity. Returns True if deleted, False if not found."""

def save_item_parent_link(self, link: ItemParentLink) -> None:
    """Upsert item→category placement. Updates sort_index if (item_id, category_id) exists."""

def list_item_parent_links(self) -> list[ItemParentLink]:
    """Return all item→category placement records. Internal use by service layer."""
```

Custom backend implementors must add all three methods (making 18 Protocol methods total).

---

## `Category` Domain Model — Modified Shape

```python
class Category(ModelBase):
    category_id: UUID
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""   # changed: was Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

A `BeforeValidator` coerces `None` → `""` on load for backward compatibility with JSON
files written before this spec.

---

## `build_service` (CLI internal)

```python
from taxomesh.adapters.cli.config import build_service
from pathlib import Path

service = build_service()                               # reads taxomesh.toml from CWD
service = build_service(config_path=Path("other.toml"))  # reads custom path
```

Not part of the public library API.
