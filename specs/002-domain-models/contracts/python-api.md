# Contract: Domain Models Python API (002-domain-models)

**Type**: Python library public import contract
**Date**: 2026-02-22
**Layer**: `taxomesh.domain.models`

---

## Import Surface

### Domain models

```python
from taxomesh.domain.models import (
    ModelBase,
    Item,
    Category,
    Tag,
    CategoryParentLink,
    ItemParentLink,
    ItemTagLink,
)
```

These are the only names exported by `taxomesh/domain/models.py`. No other symbols
from this module are part of the public contract.

### Domain type aliases

```python
from taxomesh.domain.types import ExternalId
```

`ExternalId` is exported from `taxomesh/domain/types.py`. Consumers who need to annotate
functions, variables, or repository adapters that accept an external identifier should
import `ExternalId` directly from this module rather than repeating the inline union.

**Note**: Neither `taxomesh.domain.models` nor `taxomesh.domain.types` are re-exported from
`taxomesh/__init__.py`. Consumers import them directly from their respective modules.

---

## Construction Contracts

### `Item`

```python
Item(
    external_id: UUID | str | int,   # required
    item_id: UUID = <auto>,          # auto-generated; callers SHOULD omit this
    enabled: bool = True,            # optional
    metadata: dict[str, Any] = {},   # optional; each instance gets its own dict
) -> Item
```

**Raises** `pydantic.ValidationError` if:
- `external_id` is a `str` with `len > 256`
- `external_id` is not a `UUID`, `str`, or `int`
- Any field receives a value that cannot be coerced to its declared type

---

### `Category`

```python
Category(
    category_id: UUID,               # required
    name: str,                       # required; max 256 chars
    description: str | None = None,  # optional; max 100 000 chars when present
    metadata: dict[str, Any] = {},   # optional
) -> Category
```

**Raises** `pydantic.ValidationError` if:
- `name` has `len > 256`
- `description` is not `None` and has `len > 100_000`

---

### `Tag`

```python
Tag(
    tag_id: UUID,                    # required
    name: str,                       # required; max 25 chars
    metadata: dict[str, Any] = {},   # optional
) -> Tag
```

**Raises** `pydantic.ValidationError` if:
- `name` has `len > 25`

---

### `CategoryParentLink`

```python
CategoryParentLink(
    category_id: UUID,               # required — the child category
    parent_category_id: UUID,        # required — the parent category
    sort_index: int = 0,             # optional — position within parent's listing
) -> CategoryParentLink
```

No model-level constraint on `category_id == parent_category_id` or cycle detection.
Those are application-layer responsibilities.

---

### `ItemParentLink`

```python
ItemParentLink(
    item_id: UUID,                   # required — references Item.item_id
    category_id: UUID,               # required — references Category.category_id
    sort_index: int = 0,             # optional
) -> ItemParentLink
```

---

### `ItemTagLink`

```python
ItemTagLink(
    tag_id: UUID,                    # required — references Tag.tag_id
    item_id: UUID,                   # required — references Item.item_id
) -> ItemTagLink
```

---

## Mutation Contract

All models support field mutation. Constraints are enforced identically at mutation
time as at construction time (`validate_assignment=True`).

```python
tag = Tag(tag_id=uuid4(), name="live")
tag.name = "x" * 26  # raises pydantic.ValidationError — same as at construction
tag.name = "acoustic"  # valid
```

---

## Metadata Contract

- `metadata` on `Item`, `Category`, and `Tag` is always a `dict[str, Any]`.
- Each instance has its own independent dict.
- The library never reads, validates, or modifies `metadata` contents.
- Consumers may store arbitrary nested data.

```python
a = Item(external_id=1)
b = Item(external_id=2)
a.metadata["key"] = "value"
assert b.metadata == {}  # guaranteed independent
```

---

## Serialisation Contract

All models inherit Pydantic v2's serialisation methods:

```python
item = Item(external_id="slug-001")
item.model_dump()          # → dict
item.model_dump_json()     # → JSON string
Item.model_validate(data)  # → Item (from dict)
```

Serialisation format is Pydantic v2 default — field names are the Python attribute names.
No aliases are defined in this layer.

---

## What This Layer Does NOT Provide

- Uniqueness enforcement (`external_id`, `name`, etc.) — repository concern
- Referential integrity between junction models and entity models — repository concern
- Cycle detection for `CategoryParentLink` — `domain/dag.py` concern (future feature)
- Persistence — repository adapter concern
- REST serialisation schemas — `adapters/api/` concern (future feature)
