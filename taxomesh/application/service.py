"""Application service layer for taxomesh.

TaxomeshService is the single public facade for all taxomesh operations.
It delegates all reads and writes to a pluggable repository backend and
contains no storage logic itself.
"""

from typing import Any
from uuid import UUID, uuid4

from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.models import Category, CategoryParentLink, Item, Tag
from taxomesh.domain.types import ExternalId
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshTagNotFoundError,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase


class TaxomeshService:
    """Single entry point for all taxomesh category, item, and tag operations.

    Accepts any object that structurally satisfies TaxomeshRepositoryBase at
    construction time. No inheritance from TaxomeshRepositoryBase is required.
    When no repository is provided, defaults to JsonRepository with a sensible
    default file path.

    Args:
        repository: Storage backend. When None, defaults to
            JsonRepository(Path("taxomesh.json")).
    """

    def __init__(self, repository: TaxomeshRepositoryBase | None = None) -> None:
        """Initialise the service with a storage backend.

        Args:
            repository: Storage backend. When None, defaults to
                JsonRepository(Path("taxomesh.json")).
        """
        if repository is None:
            from taxomesh.adapters.repositories.json_repository import JsonRepository  # noqa: PLC0415

            self._repo: TaxomeshRepositoryBase = JsonRepository()
        else:
            self._repo = repository

    # ------------------------------------------------------------------
    # Category
    # ------------------------------------------------------------------

    def create_category(
        self,
        name: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Category:
        """Create a new category and persist it.

        Args:
            name: Category name; max 256 characters.
            description: Optional description; max 100 000 characters.
            metadata: Optional arbitrary key-value pairs; defaults to {}.

        Returns:
            The newly created Category with a library-assigned UUID.
        """
        category = Category(
            category_id=uuid4(),
            name=name,
            description=description,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_category(category)
        return category

    def get_category(self, category_id: UUID) -> Category:
        """Retrieve a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category.

        Returns:
            The matching Category.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        result = self._repo.get_category(category_id)
        if result is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return result

    def list_categories(self) -> list[Category]:
        """Return all stored categories.

        Returns:
            List of all categories; empty list if none exist.
        """
        return self._repo.list_categories()

    def delete_category(self, category_id: UUID) -> None:
        """Delete a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category to delete.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        found = self._repo.delete_category(category_id)
        if not found:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")

    # ------------------------------------------------------------------
    # Item
    # ------------------------------------------------------------------

    def create_item(
        self,
        external_id: ExternalId,
        metadata: dict[str, Any] | None = None,
    ) -> Item:
        """Create a new item and persist it.

        Args:
            external_id: Caller-provided identifier. May be a UUID, a string
                (max 256 chars), or an int.
            metadata: Optional arbitrary key-value pairs; defaults to {}.

        Returns:
            The newly created Item with a library-assigned internal UUID.
        """
        item = Item(
            external_id=external_id,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_item(item)
        return item

    def get_item(self, item_id: UUID) -> Item:
        """Retrieve an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item.

        Returns:
            The matching Item.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
        """
        result = self._repo.get_item(item_id)
        if result is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        return result

    def list_items(self) -> list[Item]:
        """Return all stored items.

        Returns:
            List of all items; empty list if none exist.
        """
        return self._repo.list_items()

    def delete_item(self, item_id: UUID) -> None:
        """Delete an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item to delete.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
        """
        found = self._repo.delete_item(item_id)
        if not found:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")

    # ------------------------------------------------------------------
    # Tag
    # ------------------------------------------------------------------

    def create_tag(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Tag:
        """Create a new tag and persist it.

        Args:
            name: Tag name; max 25 characters.
            metadata: Optional arbitrary key-value pairs; defaults to {}.

        Returns:
            The newly created Tag with a library-assigned UUID.
        """
        tag = Tag(
            tag_id=uuid4(),
            name=name,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_tag(tag)
        return tag

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate a tag with an item. Idempotent.

        Validates that both the tag and the item exist before delegating to
        the repository. Tag existence is validated before item existence.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given tag_id exists.
            TaxomeshItemNotFoundError: If no item with the given item_id exists.
        """
        if self._repo.get_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if self._repo.get_item(item_id) is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        self._repo.assign_tag(tag_id, item_id)

    def add_category_parent(
        self,
        category_id: UUID,
        parent_id: UUID,
        sort_index: int = 0,
    ) -> CategoryParentLink:
        """Add a parent relationship between two categories, enforcing DAG integrity.

        Validates that both categories exist, then delegates cycle detection to
        the domain layer before persisting the link.

        Args:
            category_id: The child category's UUID.
            parent_id: The parent category's UUID.
            sort_index: Sort position among this category's parents; defaults to 0.

        Returns:
            The created CategoryParentLink.

        Raises:
            TaxomeshCategoryNotFoundError: If either category does not exist.
            TaxomeshCyclicDependencyError: If the relationship would create a cycle.
        """
        if self._repo.get_category(category_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        if self._repo.get_category(parent_id) is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {parent_id}")
        check_no_cycle(category_id, parent_id, self._repo.list_category_parent_links())
        link = CategoryParentLink(
            category_id=category_id,
            parent_category_id=parent_id,
            sort_index=sort_index,
        )
        self._repo.save_category_parent_link(link)
        return link

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Remove the association between a tag and an item. No-op if not linked.

        Validates that both the tag and the item exist before delegating to
        the repository. Tag existence is validated before item existence.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given tag_id exists.
            TaxomeshItemNotFoundError: If no item with the given item_id exists.
        """
        if self._repo.get_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if self._repo.get_item(item_id) is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        self._repo.remove_tag(tag_id, item_id)
