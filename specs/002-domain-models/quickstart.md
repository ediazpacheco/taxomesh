# Quickstart: Core Domain Models (002-domain-models)

**Date**: 2026-02-22

This guide shows how to import and work with the taxomesh domain model layer.
No storage, no services — just the model objects.

---

## Import

```python
from uuid import uuid4
from taxomesh.domain.models import (
    Item,
    Category,
    Tag,
    CategoryParentLink,
    ItemParentLink,
    ItemTagLink,
)
```

To annotate functions or variables that accept any valid external identifier, import the
`ExternalId` type alias directly:

```python
from taxomesh.domain.types import ExternalId

def register(external_id: ExternalId) -> Item:
    return Item(external_id=external_id)
```

---

## Creating an Item

An `Item` holds a reference to any external entity. The only required field is
`external_id` — the library auto-generates an internal UUID.

```python
# External ID as integer (e.g. legacy database PK)
song = Item(external_id=42)
print(song.item_id)    # UUID — auto-generated, unique per instance
print(song.enabled)    # True

# External ID as string slug
article = Item(external_id="how-to-brew-coffee")

# External ID as UUID
product = Item(external_id=uuid4())

# With metadata
user = Item(
    external_id=1001,
    metadata={"source": "import", "priority": 3},
)
```

String `external_id` values must be at most 256 characters:

```python
from pydantic import ValidationError

try:
    Item(external_id="x" * 257)
except ValidationError as e:
    print(e)  # String should have at most 256 characters
```

---

## Creating a Category

```python
music = Category(
    category_id=uuid4(),
    name="Music",
)

latin = Category(
    category_id=uuid4(),
    name="Latin Music",
    description="Music originating from Latin America and the Iberian Peninsula.",
)
```

---

## Creating a Tag

Tag names are capped at 25 characters:

```python
live_tag = Tag(tag_id=uuid4(), name="live")
acoustic = Tag(tag_id=uuid4(), name="acoustic")
```

---

## Building a Category Hierarchy

Use `CategoryParentLink` to place a category under a parent:

```python
tango_id = uuid4()
latin_id = uuid4()
world_id = uuid4()

# "Tango" is under both "Latin Music" and "World Music Genres"
link_latin = CategoryParentLink(
    category_id=tango_id,
    parent_category_id=latin_id,
    sort_index=1,   # rank 1 within "Latin Music"
)

link_world = CategoryParentLink(
    category_id=tango_id,
    parent_category_id=world_id,
    sort_index=5,   # rank 5 within "World Music Genres"
)
```

The same category can appear at different positions under different parents.

---

## Placing an Item in a Category

```python
song = Item(external_id=99)
tango_id = uuid4()

placement = ItemParentLink(
    item_id=song.item_id,       # internal UUID, not external_id
    category_id=tango_id,
    sort_index=2,
)
```

---

## Tagging an Item

```python
live_tag = Tag(tag_id=uuid4(), name="live")
song = Item(external_id=99)

association = ItemTagLink(
    tag_id=live_tag.tag_id,
    item_id=song.item_id,
)
```

---

## Validation at Assignment Time

All constraints apply when mutating fields, not just at construction:

```python
tag = Tag(tag_id=uuid4(), name="acoustic")
tag.name = "unplugged"    # valid — 9 chars
tag.name = "x" * 26      # raises ValidationError — exceeds 25 chars
```

---

## Metadata Independence

Each instance has its own independent `metadata` dict:

```python
a = Item(external_id=1)
b = Item(external_id=2)

a.metadata["color"] = "blue"
print(b.metadata)  # {} — unaffected
```

---

## Serialisation

All models support Pydantic v2 serialisation:

```python
song = Item(external_id="highway-to-hell")
data = song.model_dump()
# {
#   "item_id": UUID("..."),
#   "external_id": "highway-to-hell",
#   "enabled": True,
#   "metadata": {}
# }

reconstructed = Item.model_validate(data)
assert reconstructed.external_id == "highway-to-hell"
```
