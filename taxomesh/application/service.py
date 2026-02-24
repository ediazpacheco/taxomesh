"""Application service layer for taxomesh.

TaxomeshService is the single public facade for all taxomesh operations.
It delegates all reads and writes to a pluggable repository backend and
contains no storage logic itself.
"""

from typing import Any, Final
from uuid import UUID, uuid4

from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.graph import CategoryNode, TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag
from taxomesh.domain.types import ExternalId
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshItemNotFoundError,
    TaxomeshRootCategoryError,
    TaxomeshTagNotFoundError,
)
from taxomesh.ports.repository import TaxomeshRepositoryBase

ROOT_CATEGORY_NAME: Final[str] = "__root__"


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
        self._root_id: UUID = self._ensure_root()

    def _ensure_root(self) -> UUID:
        """Guarantee the reserved root category exists and return its UUID.

        Scans the repository for an existing root category. Creates one if absent.
        Called once at the end of ``__init__``.
        """
        for cat in self._repo.list_categories():
            if cat.name == ROOT_CATEGORY_NAME:
                return cat.category_id
        root = Category(category_id=uuid4(), name=ROOT_CATEGORY_NAME)
        self._repo.save_category(root)
        return root.category_id

    # ------------------------------------------------------------------
    # Category
    # ------------------------------------------------------------------

    def create_category(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Category:
        """Create a new category and persist it.

        Args:
            name: Category name; max 256 characters.
            description: Optional description; max 100 000 characters. Defaults to "".
            metadata: Optional arbitrary key-value pairs; defaults to {}.

        Returns:
            The newly created Category with a library-assigned UUID.
        """
        if name == ROOT_CATEGORY_NAME:
            raise TaxomeshRootCategoryError(f"Category name '{ROOT_CATEGORY_NAME}' is reserved")
        category = Category(
            category_id=uuid4(),
            name=name,
            description=description,
            metadata=metadata if metadata is not None else {},
        )
        self._repo.save_category(category)
        self._repo.save_category_parent_link(
            CategoryParentLink(category_id=category.category_id, parent_category_id=self._root_id, sort_index=0)
        )
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

    def list_categories(self, *, parent_id: UUID | None = None) -> list[Category]:
        """Return stored categories, optionally filtered by parent.

        Args:
            parent_id: When provided, returns child categories of this parent
                ordered by sort_index. When None, returns all categories.

        Returns:
            List of categories.

        Raises:
            TaxomeshCategoryNotFoundError: If parent_id is provided but not found.
        """
        if parent_id is None:
            parent_id = self._root_id
        else:
            self.get_category(parent_id)
        links = sorted(
            [lnk for lnk in self._repo.list_category_parent_links() if lnk.parent_category_id == parent_id],
            key=lambda lnk: lnk.sort_index,
        )
        return [self.get_category(lnk.category_id) for lnk in links]

    def delete_category(self, category_id: UUID) -> None:
        """Delete a category by its identifier.

        Args:
            category_id: The library-assigned UUID of the category to delete.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot delete the root category")
        found = self._repo.delete_category(category_id)
        if not found:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")

    def update_category(
        self,
        category_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Category:
        """Update a category's name and/or description.

        Args:
            category_id: The library-assigned UUID of the category to update.
            name: New name; unchanged if None.
            description: New description; unchanged if None.

        Returns:
            The updated Category.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot update the root category")
        category = self.get_category(category_id)
        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        self._repo.save_category(category)
        return category

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

    def list_items(self, *, category_id: UUID | None = None) -> list[Item]:
        """Return stored items, optionally filtered by category.

        Args:
            category_id: When provided, returns items placed in this category
                ordered by sort_index. When None, returns all items.

        Returns:
            List of items.

        Raises:
            TaxomeshCategoryNotFoundError: If category_id is provided but not found.
        """
        if category_id is None:
            return self._repo.list_items()
        self.get_category(category_id)
        links = sorted(
            [lnk for lnk in self._repo.list_item_parent_links() if lnk.category_id == category_id],
            key=lambda lnk: lnk.sort_index,
        )
        return [self.get_item(lnk.item_id) for lnk in links]

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

    def update_item(self, item_id: UUID, enabled: bool | None = None) -> Item:
        """Update an item's enabled state.

        Args:
            item_id: The library-assigned UUID of the item to update.
            enabled: New enabled state; unchanged if None.

        Returns:
            The updated Item.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
        """
        item = self.get_item(item_id)
        if enabled is not None:
            item.enabled = enabled
        self._repo.save_item(item)
        return item

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

    def list_tags(self) -> list[Tag]:
        """Return all stored tags.

        Returns:
            List of all tags; empty list if none exist.
        """
        return self._repo.list_tags()

    def update_tag(self, tag_id: UUID, name: str | None = None) -> Tag:
        """Update a tag's name.

        Args:
            tag_id: The library-assigned UUID of the tag to update.
            name: New name; unchanged if None.

        Returns:
            The updated Tag.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given id exists.
        """
        result = self._repo.get_tag(tag_id)
        if result is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        if name is not None:
            result.name = name
        self._repo.save_tag(result)
        return result

    def delete_tag(self, tag_id: UUID) -> None:
        """Delete a tag by its identifier.

        Args:
            tag_id: The library-assigned UUID of the tag to delete.

        Raises:
            TaxomeshTagNotFoundError: If no tag with the given id exists.
        """
        found = self._repo.delete_tag(tag_id)
        if not found:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")

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
        if category_id == self._root_id:
            raise TaxomeshRootCategoryError("Cannot add a parent to the root category")
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

    def get_graph(self) -> TaxomeshGraph:
        """Build and return a full taxonomy snapshot.

        Reads all categories (excluding the internal root), all category-parent
        relationships, and all item placements from the configured repository.
        Constructs a tree of CategoryNode instances rooted at the implicit
        taxonomy root.

        Returns:
            A TaxomeshGraph snapshot. Returns a graph with an empty roots list
            when no user-created categories exist.

        Raises:
            TaxomeshRepositoryError: If the underlying repository fails during read.
        """
        all_cats = {c.category_id: c for c in self._repo.list_categories() if c.category_id != self._root_id}
        all_links = self._repo.list_category_parent_links()

        explicit_links = [lnk for lnk in all_links if lnk.parent_category_id != self._root_id]
        root_child_links = [lnk for lnk in all_links if lnk.parent_category_id == self._root_id]
        root_sort = {lnk.category_id: lnk.sort_index for lnk in root_child_links}

        explicitly_parented = {lnk.category_id for lnk in explicit_links}
        top_level_ids = {cid for cid in root_sort if cid not in explicitly_parented}

        children_by_parent: dict[UUID, list[tuple[int, UUID]]] = {}
        for lnk in explicit_links:
            children_by_parent.setdefault(lnk.parent_category_id, []).append((lnk.sort_index, lnk.category_id))
        for bucket in children_by_parent.values():
            bucket.sort(key=lambda t: t[0])

        item_links = self._repo.list_item_parent_links()
        items_map = {i.item_id: i for i in self._repo.list_items()}
        items_pairs_by_cat: dict[UUID, list[tuple[int, Item]]] = {}
        for ilnk in item_links:
            items_pairs_by_cat.setdefault(ilnk.category_id, []).append((ilnk.sort_index, items_map[ilnk.item_id]))
        sorted_items_by_cat: dict[UUID, list[Item]] = {
            cid: [item for _, item in sorted(pairs, key=lambda t: t[0])] for cid, pairs in items_pairs_by_cat.items()
        }

        def _build_node(cat_id: UUID) -> CategoryNode:
            items = sorted_items_by_cat.get(cat_id, [])
            children = [_build_node(cid) for _, cid in children_by_parent.get(cat_id, [])]
            return CategoryNode(category=all_cats[cat_id], items=items, children=children)

        roots = [_build_node(cid) for cid in sorted(top_level_ids, key=lambda cid: root_sort[cid])]
        return TaxomeshGraph(roots=roots)

    def place_item_in_category(
        self,
        item_id: UUID,
        category_id: UUID,
        sort_index: int = 0,
    ) -> ItemParentLink:
        """Place an item in a category. Idempotent — updates sort_index if already placed.

        Args:
            item_id: The library-assigned UUID of the item.
            category_id: The library-assigned UUID of the category.
            sort_index: Sort position within the category; defaults to 0.

        Returns:
            The resulting ItemParentLink.

        Raises:
            TaxomeshItemNotFoundError: If no item with the given id exists.
            TaxomeshCategoryNotFoundError: If no category with the given id exists.
        """
        self.get_item(item_id)
        self.get_category(category_id)
        link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
        self._repo.save_item_parent_link(link)
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
