# API Contract: `taxomesh.contrib.api`

**Feature**: 028-contrib-api
**Date**: 2026-03-10

This document defines the public contract of `taxomesh/contrib/api/`. Consuming apps depend on this contract; taxomesh guarantees stability within a major version.

---

## Module surface

```python
from taxomesh.contrib.api import schemas   # request models
from taxomesh.contrib.api import handlers  # delegation functions
from taxomesh.contrib.api import errors    # exception mapper
```

---

## `schemas` — Public request models

### Category schemas

```python
class CreateCategoryRequest(BaseModel):
    name: Annotated[str, Field(max_length=256)]
    description: Annotated[str, Field(max_length=100_000)] = ""
    slug: Annotated[str, Field(max_length=256)] = ""
    metadata: dict[str, Any] = {}

class UpdateCategoryRequest(BaseModel):
    name: Annotated[str, Field(max_length=256)] | None = None
    description: Annotated[str, Field(max_length=100_000)] | None = None
    slug: Annotated[str, Field(max_length=256)] | None = None
    metadata: dict[str, Any] | None = None
```

### Item schemas

```python
class CreateItemRequest(BaseModel):
    name: Annotated[str, Field(max_length=256)]
    external_id: Annotated[str, Field(max_length=256)] = ""
    slug: Annotated[str, Field(max_length=256)] = ""
    metadata: dict[str, Any] = {}

class UpdateItemRequest(BaseModel):
    name: Annotated[str, Field(max_length=256)] | None = None
    external_id: Annotated[str, Field(max_length=256)] | None = None
    enabled: bool | None = None
    slug: Annotated[str, Field(max_length=256)] | None = None
    metadata: dict[str, Any] | None = None
```

### Tag schemas

```python
class CreateTagRequest(BaseModel):
    name: Annotated[str, Field(max_length=25)]
    metadata: dict[str, Any] = {}

class UpdateTagRequest(BaseModel):
    name: Annotated[str, Field(max_length=25)] | None = None
```

### Relationship schemas

```python
class AddParentRequest(BaseModel):
    parent_id: UUID
    sort_index: int = 0

class PlaceInCategoryRequest(BaseModel):
    category_id: UUID
    sort_index: int = 0
```

---

## `handlers` — Public functions

All functions follow the pattern:
```python
def <operation>(service: TaxomeshService, [params]) -> <DomainModel | None>
```

### Categories

```python
def list_categories(service, parent_id: UUID | None = None) -> list[Category]
def get_category(service, category_id: UUID) -> Category
def get_category_by_slug(service, slug: str) -> Category
def create_category(service, body: CreateCategoryRequest) -> Category
def update_category(service, category_id: UUID, body: UpdateCategoryRequest) -> Category
def delete_category(service, category_id: UUID) -> None
```

### Items

```python
def list_items(service, category_id: UUID | None = None) -> list[Item]
def get_item(service, item_id: UUID) -> Item
def get_item_by_slug(service, slug: str) -> Item
def get_items_by_external_id(service, external_id: str) -> list[Item]
def create_item(service, body: CreateItemRequest) -> Item
def update_item(service, item_id: UUID, body: UpdateItemRequest) -> Item
def delete_item(service, item_id: UUID) -> None
```

### Tags

```python
def list_tags(service) -> list[Tag]
def create_tag(service, body: CreateTagRequest) -> Tag
def update_tag(service, tag_id: UUID, body: UpdateTagRequest) -> Tag
def delete_tag(service, tag_id: UUID) -> None
```

### Relationships

```python
def add_category_parent(service, category_id: UUID, body: AddParentRequest) -> CategoryParentLink
def remove_category_parent(service, category_id: UUID, parent_id: UUID) -> None
def place_item_in_category(service, item_id: UUID, body: PlaceInCategoryRequest) -> ItemParentLink
def remove_item_from_category(service, item_id: UUID, category_id: UUID) -> None
def assign_tag(service, tag_id: UUID, item_id: UUID) -> None
def remove_tag_from_item(service, tag_id: UUID, item_id: UUID) -> None
```

### Graph

```python
def get_graph(service) -> TaxomeshGraph
```

---

## `errors` — Public function

```python
def to_tuple(exc: TaxomeshError) -> tuple[int, dict[str, Any]]
```

**Mapping (checked in order)**:

| Exception | Status | Reason for order |
|-----------|--------|------------------|
| `TaxomeshDuplicateSlugError` | 409 | Must precede its parent `TaxomeshValidationError` |
| `TaxomeshNotFoundError` | 404 | — |
| `TaxomeshValidationError` | 422 | Catches remaining subclasses (e.g. `TaxomeshCyclicDependencyError`) |
| `TaxomeshRepositoryError` | 500 | — |
| `TaxomeshError` | 500 | Fallback for future subclasses |

**Body**: always `{"detail": str(exc)}`

---

## Exception propagation contract

Handlers do NOT catch exceptions. Any `TaxomeshError` raised by the service propagates to the consuming app, which calls `errors.to_tuple` to map it to an HTTP response. This is intentional — the consuming app controls the response format.

---

## Stability guarantee

- `schemas.*Request` class names and field names are stable.
- `handlers.*` function signatures (name + positional args) are stable.
- `errors.to_tuple` signature and exception → status mapping are stable.
- The `{"detail": str(exc)}` body shape is stable.

Breaking changes require a taxomesh major version bump.
