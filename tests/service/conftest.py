"""Shared pytest fixtures for the service test suite."""

from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)


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
        self._item_parent_links: list[ItemParentLink] = []
        self._item_relation_links: list[ItemRelationLink] = []

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
        """Delete item; return True if it existed. Cascades relation links."""
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self._item_relation_links = [
            lnk for lnk in self._item_relation_links if item_id not in {lnk.source_item_id, lnk.target_item_id}
        ]
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
        """Upsert a category→parent relationship."""
        for i, existing in enumerate(self._category_parent_links):
            if existing.category_id == link.category_id and existing.parent_category_id == link.parent_category_id:
                self._category_parent_links[i] = link
                return
        self._category_parent_links.append(link)

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all category parent links."""
        return list(self._category_parent_links)

    # --- Tag delete ---

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete tag; return True if it existed."""
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        return True

    # --- Item → Category placement ---

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Upsert item→category placement."""
        for existing in self._item_parent_links:
            if existing.item_id == link.item_id and existing.category_id == link.category_id:
                existing.sort_index = link.sort_index
                return
        self._item_parent_links.append(link)

    def list_item_parent_links(self) -> list[ItemParentLink]:
        """Return all item→category placement records."""
        return list(self._item_parent_links)

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete a category→parent relationship; return True if found."""
        before = len(self._category_parent_links)
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if not (lnk.category_id == category_id and lnk.parent_category_id == parent_category_id)
        ]
        return len(self._category_parent_links) < before

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete an item→category placement; return True if found."""
        before = len(self._item_parent_links)
        self._item_parent_links = [
            lnk for lnk in self._item_parent_links if not (lnk.item_id == item_id and lnk.category_id == category_id)
        ]
        return len(self._item_parent_links) < before

    # --- External-ID lookup ---

    def list_items_by_external_id(self, external_id: str) -> list[Item]:
        """Return all items whose external_id matches the given value."""
        return [item for item in self._items.values() if item.external_id == external_id]

    def list_categories_by_external_id(self, external_id: str) -> list[Category]:
        """Return all categories whose external_id matches the given value."""
        return [cat for cat in self._categories.values() if cat.external_id == external_id]

    def get_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given slug, or None."""
        return next((i for i in self._items.values() if i.slug == slug), None)

    def get_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given slug, or None."""
        return next((c for c in self._categories.values() if c.slug == slug), None)

    # --- Item relation links ---

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Upsert a directed item-to-item relation."""
        for i, existing in enumerate(self._item_relation_links):
            if (
                existing.source_item_id == link.source_item_id
                and existing.target_item_id == link.target_item_id
                and existing.relation_type == link.relation_type
            ):
                self._item_relation_links[i] = link
                return
        self._item_relation_links.append(link)

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item."""
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id == item_id]
        else:
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id == item_id]
        if relation_type is not None:
            result = [lnk for lnk in result if lnk.relation_type == relation_type]
        return result

    def delete_item_relation_link(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> bool:
        """Delete the specific directed relation; return True if found."""
        before = len(self._item_relation_links)
        self._item_relation_links = [
            lnk
            for lnk in self._item_relation_links
            if not (
                lnk.source_item_id == source_item_id
                and lnk.target_item_id == target_item_id
                and lnk.relation_type == relation_type
            )
        ]
        return len(self._item_relation_links) < before

    # --- Configuration introspection ---

    def get_debug_info(self) -> dict[str, Any]:
        """Return a fixed description identifying this as an in-memory test repository."""
        return {"type": "InMemoryRepository"}

    def get_config_summary(self) -> str:
        """Return a fixed description identifying this as an in-memory test repository."""
        return "InMemoryRepository (test)"


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
