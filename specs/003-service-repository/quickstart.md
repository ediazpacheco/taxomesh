# Quickstart: Service Layer and Pluggable Storage (003-service-repository)

**Date**: 2026-02-22

This guide shows how to use `TaxomeshService` for category, item, and tag management.
No knowledge of the storage layer is required for basic use.

---

## Basic Setup — Default Storage

```python
from taxomesh import TaxomeshService

# Uses JsonRepository with taxomesh.json in the current directory
service = TaxomeshService()
```

---

## Custom Storage Path

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

service = TaxomeshService(repository=JsonRepository(Path("/data/my_taxonomy.json")))
```

---

## Managing Categories

```python
from taxomesh import TaxomeshService, TaxomeshCategoryNotFoundError

service = TaxomeshService()

# Create
music = service.create_category(name="Music")
jazz  = service.create_category(name="Jazz", description="Improvisational genre.")
print(music.category_id)   # UUID assigned by the library

# Retrieve
same = service.get_category(music.category_id)
assert same.name == "Music"

# List
all_cats = service.list_categories()
print(len(all_cats))   # 2

# Delete
service.delete_category(jazz.category_id)

# Not-found raises a typed error
try:
    service.get_category(jazz.category_id)
except TaxomeshCategoryNotFoundError as e:
    print(e)   # category not found
```

---

## Managing Items

```python
from uuid import uuid4
from taxomesh import TaxomeshService, TaxomeshItemNotFoundError

service = TaxomeshService()

# External ID can be UUID, int, or string slug
song    = service.create_item(external_id=42)
article = service.create_item(external_id="how-to-brew-coffee")
product = service.create_item(external_id=uuid4())

print(song.item_id)      # library-assigned internal UUID
print(song.external_id)  # 42

# Retrieve by internal UUID
same = service.get_item(song.item_id)
assert same.external_id == 42   # noqa: PLR2004

# List all
all_items = service.list_items()

# Delete
service.delete_item(song.item_id)

try:
    service.get_item(song.item_id)
except TaxomeshItemNotFoundError:
    print("item gone")
```

---

## Managing Tags

```python
from taxomesh import TaxomeshService, TaxomeshTagNotFoundError, TaxomeshItemNotFoundError

service = TaxomeshService()

# Create tag and item
live_tag = service.create_tag(name="live")
song     = service.create_item(external_id=99)

# Assign — idempotent, safe to call multiple times
service.assign_tag(tag_id=live_tag.tag_id, item_id=song.item_id)
service.assign_tag(tag_id=live_tag.tag_id, item_id=song.item_id)  # no-op

# Remove — no-op if association already absent
service.remove_tag(tag_id=live_tag.tag_id, item_id=song.item_id)
service.remove_tag(tag_id=live_tag.tag_id, item_id=song.item_id)  # no-op

# Missing entity raises typed error
try:
    service.assign_tag(tag_id=live_tag.tag_id, item_id=song.item_id)
except TaxomeshItemNotFoundError:
    print("item was deleted")
```

---

## Plugging In a Custom Backend

Any object satisfying `TaxomeshRepositoryBase` is accepted — no inheritance required:

```python
from taxomesh import TaxomeshService
from taxomesh.ports.repository import TaxomeshRepositoryBase
from taxomesh.domain.models import Category, Item, Tag, ItemTagLink
from uuid import UUID

class InMemoryRepository:
    """Minimal in-memory backend for testing."""

    def __init__(self) -> None:
        self._categories: dict[UUID, Category] = {}
        self._items: dict[UUID, Item] = {}
        self._tags: dict[UUID, Tag] = {}
        self._links: list[ItemTagLink] = []

    def save_category(self, category: Category) -> None:
        self._categories[category.category_id] = category

    def get_category(self, category_id: UUID) -> Category | None:
        return self._categories.get(category_id)

    def list_categories(self) -> list[Category]:
        return list(self._categories.values())

    def delete_category(self, category_id: UUID) -> bool:
        return self._categories.pop(category_id, None) is not None

    def save_item(self, item: Item) -> None:
        self._items[item.item_id] = item

    def get_item(self, item_id: UUID) -> Item | None:
        return self._items.get(item_id)

    def list_items(self) -> list[Item]:
        return list(self._items.values())

    def delete_item(self, item_id: UUID) -> bool:
        return self._items.pop(item_id, None) is not None

    def save_tag(self, tag: Tag) -> None:
        self._tags[tag.tag_id] = tag

    def get_tag(self, tag_id: UUID) -> Tag | None:
        return self._tags.get(tag_id)

    def list_tags(self) -> list[Tag]:
        return list(self._tags.values())

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        if not any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links):
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        return len(self._links) < before


service = TaxomeshService(repository=InMemoryRepository())
cat = service.create_category(name="Rock")
print(cat.name)  # Rock
```

---

## Error Handling

```python
from taxomesh import (
    TaxomeshService,
    TaxomeshError,
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshRepositoryError,
)

service = TaxomeshService()

# Catch at any granularity:
try:
    service.get_category(some_uuid)
except TaxomeshCategoryNotFoundError:
    print("category not found — handle specifically")
except TaxomeshError:
    print("any other taxomesh error")

# JsonRepository parse error on startup:
from taxomesh.adapters.repositories.json_repository import JsonRepository
from pathlib import Path

try:
    repo = JsonRepository(Path("corrupt.json"))
except TaxomeshRepositoryError as e:
    print(f"could not load storage: {e}")
```

---

## Persistence Across Restarts

```python
from pathlib import Path
from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository

DB = Path("my_taxonomy.json")

# First run — write data
s1 = TaxomeshService(repository=JsonRepository(DB))
cat = s1.create_category(name="Electronic")
print(cat.category_id)

# Later run — data survives
s2 = TaxomeshService(repository=JsonRepository(DB))
same = s2.get_category(cat.category_id)
assert same.name == "Electronic"
```
