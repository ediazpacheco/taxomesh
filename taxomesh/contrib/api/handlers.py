"""Framework-agnostic handler functions for taxomesh HTTP operations.

Each function accepts a TaxomeshService instance and a validated request schema,
delegates all business logic to the service, and returns the domain model result.
Consuming applications provide the HTTP glue (route registration, request parsing,
response serialization).
"""

from uuid import UUID

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api.schemas import (
    AddParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceInCategoryRequest,
    SearchCategoriesRequest,
    SearchItemsRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def list_categories(service: TaxomeshService, parent_id: UUID | None = None) -> list[Category]:
    """List categories, optionally filtered by parent.

    Args:
        service: The TaxomeshService instance to delegate to.
        parent_id: When provided, returns children of this parent ordered by
            sort_index. When None, returns top-level categories.

    Returns:
        List of matching categories.

    Raises:
        TaxomeshCategoryNotFoundError: If parent_id is provided but not found.
    """
    return service.list_categories(parent_id=parent_id)


def get_category(service: TaxomeshService, category_id: UUID) -> Category:
    """Retrieve a category by its UUID.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: The library-assigned UUID of the category.

    Returns:
        The matching Category.

    Raises:
        TaxomeshCategoryNotFoundError: If no category with the given id exists.
    """
    return service.get_category(category_id)


def get_category_by_slug(service: TaxomeshService, slug: str) -> Category:
    """Retrieve a category by its slug.

    Args:
        service: The TaxomeshService instance to delegate to.
        slug: The URL-friendly identifier of the category.

    Returns:
        The matching Category.

    Raises:
        TaxomeshCategoryNotFoundError: If no category with the given slug exists.
    """
    return service.get_category_by_slug(slug)


def create_category(service: TaxomeshService, body: CreateCategoryRequest) -> Category:
    """Create a new category.

    Args:
        service: The TaxomeshService instance to delegate to.
        body: Validated create request containing name, description, slug, metadata.

    Returns:
        The newly created Category.

    Raises:
        TaxomeshDuplicateSlugError: If slug is non-empty and already in use.
    """
    return service.create_category(
        name=body.name,
        description=body.description,
        slug=body.slug,
        metadata=body.metadata,
    )


def update_category(service: TaxomeshService, category_id: UUID, body: UpdateCategoryRequest) -> Category:
    """Update an existing category.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: The library-assigned UUID of the category to update.
        body: Validated update request; only non-None fields are applied.

    Returns:
        The updated Category.

    Raises:
        TaxomeshCategoryNotFoundError: If no category with the given id exists.
        TaxomeshDuplicateSlugError: If slug is non-empty and already in use.
    """
    return service.update_category(
        category_id=category_id,
        name=body.name,
        description=body.description,
        slug=body.slug,
        metadata=body.metadata,
    )


def delete_category(service: TaxomeshService, category_id: UUID) -> None:
    """Delete a category.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: The library-assigned UUID of the category to delete.

    Raises:
        TaxomeshCategoryNotFoundError: If no category with the given id exists.
    """
    service.delete_category(category_id)


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def list_items(service: TaxomeshService, category_id: UUID | None = None) -> list[Item]:
    """List items, optionally filtered by category.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: When provided, returns items in this category ordered by
            sort_index. When None, returns all items.

    Returns:
        List of matching items.

    Raises:
        TaxomeshCategoryNotFoundError: If category_id is provided but not found.
    """
    return service.list_items(category_id=category_id)


def get_item(service: TaxomeshService, item_id: UUID) -> Item:
    """Retrieve an item by its UUID.

    Args:
        service: The TaxomeshService instance to delegate to.
        item_id: The library-assigned UUID of the item.

    Returns:
        The matching Item.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given id exists.
    """
    return service.get_item(item_id)


def get_item_by_slug(service: TaxomeshService, slug: str) -> Item:
    """Retrieve an item by its slug.

    Args:
        service: The TaxomeshService instance to delegate to.
        slug: The URL-friendly identifier of the item.

    Returns:
        The matching Item.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given slug exists.
    """
    return service.get_item_by_slug(slug)


def get_item_by_external_id(service: TaxomeshService, external_id: str) -> Item | None:
    """Return the item matching the given external_id, or None.

    Args:
        service: The TaxomeshService instance to delegate to.
        external_id: The external identifier to look up.

    Returns:
        The matching Item, or None if not found.
    """
    return service.get_item_by_external_id(external_id)


def create_item(service: TaxomeshService, body: CreateItemRequest) -> Item:
    """Create a new item.

    Args:
        service: The TaxomeshService instance to delegate to.
        body: Validated create request containing name, external_id, slug, metadata.

    Returns:
        The newly created Item.

    Raises:
        TaxomeshDuplicateSlugError: If slug is non-empty and already in use.
    """
    return service.create_item(
        name=body.name,
        external_id=body.external_id,
        slug=body.slug,
        metadata=body.metadata,
    )


def update_item(service: TaxomeshService, item_id: UUID, body: UpdateItemRequest) -> Item:
    """Update an existing item.

    Args:
        service: The TaxomeshService instance to delegate to.
        item_id: The library-assigned UUID of the item to update.
        body: Validated update request; only non-None fields are applied.

    Returns:
        The updated Item.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given id exists.
        TaxomeshDuplicateSlugError: If slug is non-empty and already in use.
    """
    return service.update_item(
        item_id=item_id,
        name=body.name,
        external_id=body.external_id,
        enabled=body.enabled,
        slug=body.slug,
        metadata=body.metadata,
    )


def delete_item(service: TaxomeshService, item_id: UUID) -> None:
    """Delete an item.

    Args:
        service: The TaxomeshService instance to delegate to.
        item_id: The library-assigned UUID of the item to delete.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given id exists.
    """
    service.delete_item(item_id)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def list_tags(service: TaxomeshService) -> list[Tag]:
    """List all tags.

    Args:
        service: The TaxomeshService instance to delegate to.

    Returns:
        List of all tags; empty list if none exist.
    """
    return service.list_tags()


def create_tag(service: TaxomeshService, body: CreateTagRequest) -> Tag:
    """Create a new tag.

    Args:
        service: The TaxomeshService instance to delegate to.
        body: Validated create request containing name and metadata.

    Returns:
        The newly created Tag.
    """
    return service.create_tag(name=body.name, metadata=body.metadata)


def update_tag(service: TaxomeshService, tag_id: UUID, body: UpdateTagRequest) -> Tag:
    """Update an existing tag.

    Args:
        service: The TaxomeshService instance to delegate to.
        tag_id: The library-assigned UUID of the tag to update.
        body: Validated update request; only non-None fields are applied.

    Returns:
        The updated Tag.

    Raises:
        TaxomeshTagNotFoundError: If no tag with the given id exists.
    """
    return service.update_tag(tag_id=tag_id, name=body.name)


def delete_tag(service: TaxomeshService, tag_id: UUID) -> None:
    """Delete a tag.

    Args:
        service: The TaxomeshService instance to delegate to.
        tag_id: The library-assigned UUID of the tag to delete.

    Raises:
        TaxomeshTagNotFoundError: If no tag with the given id exists.
    """
    service.delete_tag(tag_id)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def add_category_parent(
    service: TaxomeshService,
    category_id: UUID,
    body: AddParentRequest,
) -> CategoryParentLink:
    """Add a parent relationship to a category.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: The child category's UUID.
        body: Validated request with parent_id and sort_index.

    Returns:
        The created CategoryParentLink.

    Raises:
        TaxomeshCategoryNotFoundError: If either category does not exist.
        TaxomeshCyclicDependencyError: If the relationship would create a cycle.
    """
    return service.add_category_parent(
        category_id=category_id,
        parent_id=body.parent_id,
        sort_index=body.sort_index,
    )


def remove_category_parent(service: TaxomeshService, category_id: UUID, parent_id: UUID) -> None:
    """Remove a parent relationship from a category.

    Args:
        service: The TaxomeshService instance to delegate to.
        category_id: The child category's UUID.
        parent_id: The parent category's UUID.

    Raises:
        TaxomeshCategoryNotFoundError: If either category does not exist.
    """
    service.remove_category_parent(category_id=category_id, parent_id=parent_id)


def place_item_in_category(
    service: TaxomeshService,
    item_id: UUID,
    body: PlaceInCategoryRequest,
) -> ItemParentLink:
    """Place an item in a category.

    Args:
        service: The TaxomeshService instance to delegate to.
        item_id: The library-assigned UUID of the item.
        body: Validated request with category_id and sort_index.

    Returns:
        The resulting ItemParentLink.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given id exists.
        TaxomeshCategoryNotFoundError: If no category with the given id exists.
    """
    return service.place_item_in_category(
        item_id=item_id,
        category_id=body.category_id,
        sort_index=body.sort_index,
    )


def remove_item_from_category(service: TaxomeshService, item_id: UUID, category_id: UUID) -> None:
    """Remove an item's placement from a category.

    Args:
        service: The TaxomeshService instance to delegate to.
        item_id: The item's UUID.
        category_id: The category's UUID.

    Raises:
        TaxomeshItemNotFoundError: If no item with the given id exists.
        TaxomeshCategoryNotFoundError: If no category with the given id exists.
    """
    service.remove_item_from_category(item_id=item_id, category_id=category_id)


def assign_tag(service: TaxomeshService, tag_id: UUID, item_id: UUID) -> None:
    """Associate a tag with an item. Idempotent.

    Args:
        service: The TaxomeshService instance to delegate to.
        tag_id: The library-assigned UUID of the tag.
        item_id: The library-assigned UUID of the item.

    Raises:
        TaxomeshTagNotFoundError: If no tag with the given id exists.
        TaxomeshItemNotFoundError: If no item with the given id exists.
    """
    service.assign_tag(tag_id=tag_id, item_id=item_id)


def remove_tag_from_item(service: TaxomeshService, tag_id: UUID, item_id: UUID) -> None:
    """Remove a tag association from an item.

    Args:
        service: The TaxomeshService instance to delegate to.
        tag_id: The library-assigned UUID of the tag.
        item_id: The library-assigned UUID of the item.

    Raises:
        TaxomeshTagNotFoundError: If no tag with the given id exists.
        TaxomeshItemNotFoundError: If no item with the given id exists.
    """
    service.remove_tag(tag_id=tag_id, item_id=item_id)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_items(service: TaxomeshService, params: SearchItemsRequest) -> list[Item]:
    """Search items using all parameters from SearchItemsRequest.

    Delegates 1:1 to service.search_items(). Adds no business logic.

    Args:
        service: The TaxomeshService instance.
        params: Validated search parameters.

    Returns:
        Items ranked by relevance, trimmed to params.limit.

    Raises:
        ValueError: If params.limit <= 0 (raised by service).
        TaxomeshCategoryNotFoundError: If params.category_id does not exist.
    """
    return service.search_items(
        params.q,
        limit=params.limit,
        category_id=params.category_id,
        enabled_only=params.enabled_only,
        fuzzy=params.fuzzy,
        recursive=params.recursive,
    )


def search_categories(service: TaxomeshService, params: SearchCategoriesRequest) -> list[Category]:
    """Search categories using all parameters from SearchCategoriesRequest.

    Delegates 1:1 to service.search_categories(). Adds no business logic.

    Args:
        service: The TaxomeshService instance.
        params: Validated search parameters.

    Returns:
        Categories ranked by relevance, trimmed to params.limit.

    Raises:
        ValueError: If params.limit <= 0 (raised by service).
        TaxomeshCategoryNotFoundError: If params.parent_id does not exist.
    """
    return service.search_categories(
        params.q,
        limit=params.limit,
        parent_id=params.parent_id,
        enabled_only=params.enabled_only,
        fuzzy=params.fuzzy,
    )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def get_graph(service: TaxomeshService) -> TaxomeshGraph:
    """Build and return the full taxonomy graph snapshot.

    Args:
        service: The TaxomeshService instance to delegate to.

    Returns:
        A TaxomeshGraph snapshot with all categories, items, and relationships.
    """
    return service.get_graph()
