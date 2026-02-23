"""Storage interface for the taxomesh repository layer.

``TaxomeshRepositoryBase`` is a ``typing.Protocol`` — any class that
implements all required methods with compatible signatures is a valid
repository. Explicit inheritance is NOT required; mypy verifies compliance
structurally at type-check time.
"""

from typing import Protocol
from uuid import UUID

from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag


class TaxomeshRepositoryBase(Protocol):
    """Structural interface that every taxomesh storage backend must satisfy.

    All method names and signatures below form the contract. Implement them
    in any class (no inheritance required) and pass the instance to
    ``TaxomeshService`` at construction time.
    """

    # --- Category ---

    def save_category(self, category: Category) -> None:
        """Insert or update a category record.

        Args:
            category: The Category instance to persist.
        """
        ...

    def get_category(self, category_id: UUID) -> Category | None:
        """Retrieve a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category.

        Returns:
            The matching Category, or None if it does not exist.
        """
        ...

    def list_categories(self) -> list[Category]:
        """Return all stored categories.

        Returns:
            List of all categories; empty list if the store is empty.
        """
        ...

    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category to delete.

        Returns:
            True if the category was found and deleted; False if it did not exist.
        """
        ...

    # --- Item ---

    def save_item(self, item: Item) -> None:
        """Insert or update an item record.

        Args:
            item: The Item instance to persist.
        """
        ...

    def get_item(self, item_id: UUID) -> Item | None:
        """Retrieve an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item.

        Returns:
            The matching Item, or None if it does not exist.
        """
        ...

    def list_items(self) -> list[Item]:
        """Return all stored items.

        Returns:
            List of all items; empty list if the store is empty.
        """
        ...

    def delete_item(self, item_id: UUID) -> bool:
        """Delete an item by its internal identifier.

        Args:
            item_id: The library-assigned UUID of the item to delete.

        Returns:
            True if the item was found and deleted; False if it did not exist.
        """
        ...

    # --- Tag ---

    def save_tag(self, tag: Tag) -> None:
        """Insert or update a tag record.

        Args:
            tag: The Tag instance to persist.
        """
        ...

    def get_tag(self, tag_id: UUID) -> Tag | None:
        """Retrieve a tag by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag.

        Returns:
            The matching Tag, or None if it does not exist.
        """
        ...

    def list_tags(self) -> list[Tag]:
        """Return all stored tags.

        Returns:
            List of all tags; empty list if the store is empty.
        """
        ...

    # --- Tag ↔ Item association ---

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Associate a tag with an item. Idempotent — no-op if already linked.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.
        """
        ...

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        """Remove the association between a tag and an item.

        Args:
            tag_id: The library-assigned UUID of the tag.
            item_id: The library-assigned UUID of the item.

        Returns:
            True if the association was found and removed; False if it did not exist.
        """
        ...

    # --- Category parent links ---

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Persist a category-parent relationship.

        Args:
            link: The CategoryParentLink to persist.
        """
        ...

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all stored category-parent relationships.

        Returns:
            List of all CategoryParentLink records; empty list if none exist.
        """
        ...

    # --- Tag delete ---

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete a tag entity by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag.

        Returns:
            True if the tag was found and deleted; False if it did not exist.
        """
        ...

    # --- Item → Category placement ---

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Upsert an item→category placement.

        If a link with the same (item_id, category_id) pair already exists its
        sort_index is updated in-place. No duplicate is created.

        Args:
            link: The ItemParentLink to persist.
        """
        ...

    def list_item_parent_links(self) -> list[ItemParentLink]:
        """Return all item→category placement records.

        Returns:
            List of all ItemParentLink records; empty list if none exist.
        """
        ...
