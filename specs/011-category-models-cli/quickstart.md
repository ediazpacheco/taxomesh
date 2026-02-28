# Quickstart: Category Fields, Models Refactor, CLI Output & Service Cache

**Feature**: 011-category-models-cli
**Date**: 2026-02-27

## Scenario 1: Category with enabled and external_id

```python
from uuid import uuid4
from taxomesh.domain.models import Category

# New category with defaults
cat = Category(category_id=uuid4(), name="Rock")
assert cat.enabled is True
assert cat.external_id == ""

# New category with explicit values
cat2 = Category(
    category_id=uuid4(),
    name="Jazz",
    enabled=False,
    external_id="genre-jazz",
)
assert cat2.enabled is False
assert cat2.external_id == "genre-jazz"
```

## Scenario 2: Backward-compatible import after models refactor

```python
# All existing imports continue to work
from taxomesh.domain.models import (
    ModelBase,
    Item,
    Category,
    Tag,
    CategoryParentLink,
    ItemParentLink,
    ItemTagLink,
)

# Direct module imports also work
from taxomesh.domain.models.category import Category
from taxomesh.domain.models.item import Item
```

## Scenario 3: CLI graph output with icons

```text
# Before (current):
Taxonomy
├── Rock  abc-category-id
│   ├── song-42  abc123-item-id  enabled=True
│   └── song-99  def456-item-id  enabled=False

# After (this feature):
Taxonomy
├── genre-rock  Rock  abc-category-id  ✓
│   ├── song-42  abc123-item-id  ✓
│   └── song-99  def456-item-id  ✗
└── Jazz  def-category-id  ✓
    └── song-77  ghi789-item-id  ✓
```

- Green `✓` = enabled, Red `✗` = disabled
- Category `external_id` shown only when non-empty
- Items always show `external_id` (required field)

## Scenario 4: Legacy store loading

```python
# Store JSON with category missing enabled/external_id:
# {"category_id": "abc-123", "name": "Rock", "description": ""}
#
# After loading:
cat = service.get_category(uuid)
assert cat.enabled is True       # default
assert cat.external_id == ""     # default
```

## Scenario 5: Memoize decorator usage

```python
from taxomesh.utils.memoize import memoize

@memoize(ttl=10)
def expensive_lookup(key: str) -> str:
    # called only once for same key within 10s
    return db.query(key)

result1 = expensive_lookup("abc")  # calls db.query
result2 = expensive_lookup("abc")  # returns cached result
result3 = expensive_lookup("xyz")  # different key — calls db.query
```

## Scenario 6: Service cache behavior

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# First call — hits repository
cat1 = service.get_category(some_uuid)

# Second call within 5s — returns cached result (no repository call)
cat2 = service.get_category(some_uuid)

assert cat1 == cat2  # same object from cache

# After 5s — cache expires, repository called again
import time
time.sleep(5)
cat3 = service.get_category(some_uuid)  # fresh repository call
```

## Scenario 7: Cache invalidation on write

```python
from taxomesh import TaxomeshService

service = TaxomeshService()

# Read — populates cache
cat = service.get_category(some_uuid)

# Write — clears entire read cache
service.update_category(some_uuid, name="New Name")

# Next read — cache was cleared, hits repository again
cat_fresh = service.get_category(some_uuid)
assert cat_fresh.name == "New Name"
```
