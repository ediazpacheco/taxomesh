"""Shared pytest fixtures for the service test suite."""

from pathlib import Path
from uuid import UUID

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemTagLink, Tag


class InMemoryRepository:
    """Pure in-memory repository for testing.

    Implements all TaxomeshRepositoryBase methods without inheriting from it,
    proving that structural (Protocol) typing is sufficient.
    """

    def __init__(self) -> None:
        """Initialise empty in-memory collections."""
        self._categories: dict[UUID, Category] = {}
        self._items: dict[UUID, Item] = {}
        self._tags: dict[UUID, Tag] = {}
        self._links: list[ItemTagLink] = []
        self._category_parent_links: list[CategoryParentLink] = []

    # --- Category ---

    def save_category(self, category: Category) -> None:
        """Insert or update a category."""
        self._categories[category.category_id] = category

    def get_category(self, category_id: UUID) -> Category | None:
        """Return category by id, or None."""
        return self._categories.get(category_id)

    def list_categories(self) -> list[Category]:
        """Return all categories."""
        return list(self._categories.values())

    def delete_category(self, category_id: UUID) -> bool:
        """Delete category; return True if it existed."""
        if category_id not in self._categories:
            return False
        del self._categories[category_id]
        return True

    # --- Item ---

    def save_item(self, item: Item) -> None:
        """Insert or update an item."""
        self._items[item.item_id] = item

    def get_item(self, item_id: UUID) -> Item | None:
        """Return item by id, or None."""
        return self._items.get(item_id)

    def list_items(self) -> list[Item]:
        """Return all items."""
        return list(self._items.values())

    def delete_item(self, item_id: UUID) -> bool:
        """Delete item; return True if it existed."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        return True

    # --- Tag ---

    def save_tag(self, tag: Tag) -> None:
        """Insert or update a tag."""
        self._tags[tag.tag_id] = tag

    def get_tag(self, tag_id: UUID) -> Tag | None:
        """Return tag by id, or None."""
        return self._tags.get(tag_id)

    def list_tags(self) -> list[Tag]:
        """Return all tags."""
        return list(self._tags.values())

    # --- Tag ↔ Item association ---

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate tag with item; idempotent."""
        already_linked = any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links)
        if not already_linked:
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        """Remove tag-item association; return True if it existed."""
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        return len(self._links) < before

    # --- Category parent links ---

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Persist a category-parent relationship."""
        self._category_parent_links.append(link)

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all category parent links."""
        return list(self._category_parent_links)


@pytest.fixture
def service() -> TaxomeshService:
    """Return a TaxomeshService backed by a fresh InMemoryRepository."""
    return TaxomeshService(repository=InMemoryRepository())


@pytest.fixture
def tmp_json_path(tmp_path: Path) -> Path:
    """Return a temporary file path for JsonRepository tests.

    The file does not exist yet; JsonRepository must create it.
    """
    return tmp_path / "taxomesh_test.json"
