"""The HTTP handlers: functions that each call one member of the service.

A handler takes the service, the values of the request and, where it has one, a validated request
schema. It calls one member, and returns what the member returns: rows, links or a graph snapshot.
The application does the rest of the HTTP work: it registers the routes, reads the requests and
serializes the responses.

Each handler is named ``<namespace>_<member>`` after the collection member it calls, so
``categories_get_by_slug`` calls ``service.categories.get_by_slug``, and ``graph`` calls
``service.graph``. A handler keeps its member's contract: it returns what the member returns,
a tuple from a listing, and a lookup (``*_get``, ``*_get_by_slug``, ``*_get_by_external_id``)
returns ``None`` on a miss. The consuming application turns that ``None`` into its 404.

Every handler takes its arguments in the same way: ``service`` and the **subject** of the
operation are the only positional parameters, and every other parameter is keyword-only. So two
identifiers of the same type cannot change places without an error: ``items_tag(service, item_id,
tag_id=...)`` fails the type check with its arguments in the other order, and two bare ``UUID``
positionals would pass it. HTTP names a row by its identifier, so the parameters keep their ``_id``
names, and each one is passed to the member's parameter that the noun names.
"""

from collections.abc import Sequence
from uuid import UUID

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api.schemas import (
    AddCategoryParentRequest,
    CreateCategoryRequest,
    CreateItemRequest,
    CreateTagRequest,
    PlaceItemRequest,
    SearchCategoriesRequest,
    SearchItemsRequest,
    UpdateCategoryRequest,
    UpdateItemRequest,
    UpdateTagRequest,
)
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, Tag
from taxomesh.domain.types import UNSET

# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def categories_list(
    service: TaxomeshService,
    *,
    parent_id: UUID | None = None,
    item_id: UUID | None = None,
    enabled: bool | None = True,
) -> Sequence[Category]:
    """List categories: every one, or the children of a parent, or those that an item is placed in.

    Args:
        service: The service to call.
        parent_id: When given, only the children of this parent, ordered by their ``sort_index``.
        item_id: When given, only the categories that this item is placed in, ordered by the
            ``sort_index`` of each placement.
        enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
            disabled ones, and ``None`` all of them.

    Returns:
        The matching categories. With neither filter, every category, wherever it is;
        :func:`categories_roots` lists the top level.

    Raises:
        TaxomeshValidationError: If both ``parent_id`` and ``item_id`` are given.
        TaxomeshCategoryNotFoundError: If ``parent_id`` names a category that is not stored.
        TaxomeshItemNotFoundError: If ``item_id`` names an item that is not stored.
    """
    return service.categories.list(parent=parent_id, item=item_id, enabled=enabled)


def categories_roots(service: TaxomeshService, *, enabled: bool | None = True) -> Sequence[Category]:
    """List the top level: the categories that have no parent.

    Args:
        service: The service to call.
        enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
            disabled ones, and ``None`` all of them.

    Returns:
        The top-level categories, in their stored order.
    """
    return service.categories.roots(enabled=enabled)


def categories_get(service: TaxomeshService, category_id: UUID) -> Category | None:
    """Return the category with this identifier, or ``None``.

    Args:
        service: The service to call.
        category_id: The identifier of the category.

    Returns:
        The category row, or ``None`` when no category with this identifier is stored.
    """
    return service.categories.get(category_id)


def categories_get_by_slug(service: TaxomeshService, slug: str) -> Category | None:
    """Return the category with this slug, or ``None``.

    Args:
        service: The service to call.
        slug: The slug of the category: a text key for URLs.

    Returns:
        The category row, or ``None`` when no category has this slug. An empty slug names no
        category.
    """
    return service.categories.get_by_slug(slug)


def categories_get_by_external_id(service: TaxomeshService, external_id: str) -> Category | None:
    """Return the category with this external id, or ``None``.

    Args:
        service: The service to call.
        external_id: The external id to look up.

    Returns:
        The category row, or ``None`` when no category has this external id.
    """
    return service.categories.get_by_external_id(external_id)


def categories_create(service: TaxomeshService, *, body: CreateCategoryRequest) -> Category:
    """Create a category at the top level.

    Args:
        service: The service to call.
        body: The validated request, with ``name``, ``description``, ``slug``, ``external_id`` and
            ``metadata``.

    Returns:
        The row of the new category.

    Raises:
        TaxomeshRootCategoryError: If the name is the reserved name of the implicit root.
        TaxomeshDuplicateSlugError: If the slug is not empty and another category has it.
        TaxomeshExternalIdConflictError: If another category already has the external id.
    """
    return service.categories.create(
        name=body.name,
        description=body.description,
        slug=body.slug,
        external_id=body.external_id,
        metadata=body.metadata,
    )


def categories_update(service: TaxomeshService, category_id: UUID, *, body: UpdateCategoryRequest) -> Category:
    """Update a category.

    Only the fields that the caller set are passed on: an omitted field carries no instruction and
    keeps the stored value. A present field is assigned its value. ``external_id`` is the one
    stored field that accepts null, so a null ``external_id`` clears the stored external id. The
    request validation refuses a null in any other stored field, ``enabled`` included, before this
    handler runs. ``expected_version`` is passed on as it is: omitted or null, the update compares
    no version.

    Each field is passed under its own keyword, and not unpacked from a model dump, so a service
    parameter with another name is a type error here, and not a ``TypeError`` at run time.

    Args:
        service: The service to call.
        category_id: The identifier of the category to update.
        body: The validated request; only the fields that the caller set are passed on.

    Returns:
        The new row of the category.

    Raises:
        TaxomeshCategoryNotFoundError: If the category is not stored.
        TaxomeshRootCategoryError: If the new name is the reserved name of the implicit root.
        TaxomeshDuplicateSlugError: If the slug is not empty and another category has it.
        TaxomeshExternalIdConflictError: If another category already has the external id.
        TaxomeshVersionConflictError: If ``expected_version`` is given and the stored category is
            not at it.
    """
    provided = body.model_fields_set
    return service.categories.update(
        category_id,
        name=body.name if "name" in provided else UNSET,
        description=body.description if "description" in provided else UNSET,
        slug=body.slug if "slug" in provided else UNSET,
        metadata=body.metadata if "metadata" in provided else UNSET,
        external_id=body.external_id if "external_id" in provided else UNSET,
        enabled=body.enabled if "enabled" in provided else UNSET,
        expected_version=body.expected_version,
    )


def categories_delete(service: TaxomeshService, category_id: UUID) -> None:
    """Delete a category, and every link that names it.

    Args:
        service: The service to call.
        category_id: The identifier of the category to delete.

    Raises:
        TaxomeshCategoryNotFoundError: If the category is not stored.
    """
    service.categories.delete(category_id)


def categories_add_parent(
    service: TaxomeshService,
    category_id: UUID,
    *,
    body: AddCategoryParentRequest,
) -> CategoryParentLink:
    """Add a parent to a category.

    Args:
        service: The service to call.
        category_id: The identifier of the child category.
        body: The validated request, with ``parent_id`` and ``sort_index``.

    Returns:
        The parent link.

    Raises:
        TaxomeshCategoryNotFoundError: If either category is not stored.
        TaxomeshCyclicDependencyError: If the parent link would make a cycle.
    """
    return service.categories.add_parent(
        category=category_id,
        parent=body.parent_id,
        sort_index=body.sort_index,
    )


def categories_remove_parent(service: TaxomeshService, category_id: UUID, *, parent_id: UUID) -> None:
    """Remove one parent from a category. Removing a parent it does not have does nothing.

    Args:
        service: The service to call.
        category_id: The identifier of the child category.
        parent_id: The identifier of the parent category.

    Raises:
        TaxomeshCategoryNotFoundError: If either category is not stored.
    """
    service.categories.remove_parent(category=category_id, parent=parent_id)


def categories_search(service: TaxomeshService, *, params: SearchCategoriesRequest) -> Sequence[Category]:
    """Search the categories with every parameter of ``SearchCategoriesRequest``.

    The request object is named ``params`` and not ``body``: it serves a GET endpoint, which has
    no body.

    Args:
        service: The service to call.
        params: The validated search parameters.

    Returns:
        The categories in order of relevance, at most ``params.limit`` of them.

    Raises:
        TaxomeshValidationError: If ``params.limit`` is 0 or less.
        TaxomeshCategoryNotFoundError: If ``params.parent_id`` names a category that is not stored.
    """
    return service.categories.search(
        params.query,
        limit=params.limit,
        parent=params.parent_id,
        enabled=params.enabled,
        fuzzy=params.fuzzy,
    )


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def items_list(
    service: TaxomeshService,
    *,
    category_id: UUID | None = None,
    recursive: bool = False,
    tag_id: UUID | None = None,
    enabled: bool | None = True,
) -> Sequence[Item]:
    """List items: every one, or those in a category, or those that have a tag, or both.

    Args:
        service: The service to call.
        category_id: When given, only the items placed in this category, ordered by the
            ``sort_index`` of each placement.
        recursive: With ``category_id``, also the items placed in the descendants of the category.
            Without ``category_id``, it has no effect.
        tag_id: When given, only the items that have this tag, ordered by name. With
            ``category_id``, the items of the category that have the tag, in the order of the
            category.
        enabled: ``True`` (the default) returns only the enabled items, ``False`` only the
            disabled ones, and ``None`` all of them.

    Returns:
        The matching items.

    Raises:
        TaxomeshCategoryNotFoundError: If ``category_id`` names a category that is not stored.
        TaxomeshTagNotFoundError: If ``tag_id`` names a tag that is not stored.
    """
    return service.items.list(category=category_id, recursive=recursive, tag=tag_id, enabled=enabled)


def items_get(service: TaxomeshService, item_id: UUID) -> Item | None:
    """Return the item with this identifier, or ``None``.

    Args:
        service: The service to call.
        item_id: The identifier of the item.

    Returns:
        The item row, or ``None`` when no item with this identifier is stored.
    """
    return service.items.get(item_id)


def items_get_by_slug(service: TaxomeshService, slug: str) -> Item | None:
    """Return the item with this slug, or ``None``.

    Args:
        service: The service to call.
        slug: The slug of the item: a text key for URLs.

    Returns:
        The item row, or ``None`` when no item has this slug. An empty slug names no item.
    """
    return service.items.get_by_slug(slug)


def items_get_by_external_id(service: TaxomeshService, external_id: str) -> Item | None:
    """Return the item with this external id, or ``None``.

    Args:
        service: The service to call.
        external_id: The external id to look up.

    Returns:
        The item row, or ``None`` when no item has this external id.
    """
    return service.items.get_by_external_id(external_id)


def items_create(service: TaxomeshService, *, body: CreateItemRequest) -> Item:
    """Create an item.

    Args:
        service: The service to call.
        body: The validated request, with ``name``, ``external_id``, ``slug`` and ``metadata``.

    Returns:
        The row of the new item.

    Raises:
        TaxomeshDuplicateSlugError: If the slug is not empty and another item has it.
        TaxomeshExternalIdConflictError: If another item already has the external id.
    """
    return service.items.create(
        name=body.name,
        external_id=body.external_id,
        slug=body.slug,
        metadata=body.metadata,
    )


def items_update(service: TaxomeshService, item_id: UUID, *, body: UpdateItemRequest) -> Item:
    """Update an item.

    Only the fields that the caller set are passed on: an omitted field carries no instruction and
    keeps the stored value. A present field is assigned its value. ``external_id`` is the one
    stored field that accepts null, so a null ``external_id`` clears the stored external id. The
    request validation refuses a null in any other stored field before this handler runs.
    ``expected_version`` is passed on as it is: omitted or null, the update compares no version.

    Each field is passed under its own keyword, and not unpacked from a model dump, so a service
    parameter with another name is a type error here, and not a ``TypeError`` at run time.

    Args:
        service: The service to call.
        item_id: The identifier of the item to update.
        body: The validated request; only the fields that the caller set are passed on.

    Returns:
        The new row of the item.

    Raises:
        TaxomeshItemNotFoundError: If the item is not stored.
        TaxomeshDuplicateSlugError: If the slug is not empty and another item has it.
        TaxomeshExternalIdConflictError: If another item already has the external id.
        TaxomeshVersionConflictError: If ``expected_version`` is given and the stored item is not
            at it.
    """
    provided = body.model_fields_set
    return service.items.update(
        item_id,
        name=body.name if "name" in provided else UNSET,
        slug=body.slug if "slug" in provided else UNSET,
        metadata=body.metadata if "metadata" in provided else UNSET,
        external_id=body.external_id if "external_id" in provided else UNSET,
        enabled=body.enabled if "enabled" in provided else UNSET,
        expected_version=body.expected_version,
    )


def items_delete(service: TaxomeshService, item_id: UUID) -> None:
    """Delete an item, and every link that names it.

    Args:
        service: The service to call.
        item_id: The identifier of the item to delete.

    Raises:
        TaxomeshItemNotFoundError: If the item is not stored.
    """
    service.items.delete(item_id)


def items_place_in(
    service: TaxomeshService,
    item_id: UUID,
    *,
    body: PlaceItemRequest,
) -> ItemParentLink:
    """Place an item in a category.

    Args:
        service: The service to call.
        item_id: The identifier of the item.
        body: The validated request, with ``category_id`` and ``sort_index``.

    Returns:
        The placement.

    Raises:
        TaxomeshItemNotFoundError: If the item is not stored.
        TaxomeshCategoryNotFoundError: If the category is not stored.
    """
    return service.items.place_in(
        item=item_id,
        category=body.category_id,
        sort_index=body.sort_index,
    )


def items_remove_from(service: TaxomeshService, item_id: UUID, *, category_id: UUID) -> None:
    """Remove an item from one category. Removing a placement it does not have does nothing.

    Args:
        service: The service to call.
        item_id: The identifier of the item.
        category_id: The identifier of the category.

    Raises:
        TaxomeshItemNotFoundError: If the item is not stored.
        TaxomeshCategoryNotFoundError: If the category is not stored.
    """
    service.items.remove_from(item=item_id, category=category_id)


def items_tag(service: TaxomeshService, item_id: UUID, *, tag_id: UUID) -> None:
    """Tag an item. Tagging it again with the same tag changes nothing.

    The item comes first, as in ``service.items.tag``: the member is on the collection of the
    entity that it changes. Both parameters are ``UUID``s, so ``tag_id`` is keyword-only, and the two
    cannot change places.

    Args:
        service: The service to call.
        item_id: The identifier of the item.
        tag_id: The identifier of the tag.

    Raises:
        TaxomeshTagNotFoundError: If the tag is not stored.
        TaxomeshItemNotFoundError: If the item is not stored.
    """
    service.items.tag(item=item_id, tag=tag_id)


def items_untag(service: TaxomeshService, item_id: UUID, *, tag_id: UUID) -> None:
    """Remove a tag from an item. Removing a tag that it does not have does nothing.

    The item comes first, as in ``service.items.untag``: the member is on the collection of the
    entity that it changes. Both parameters are ``UUID``s, so ``tag_id`` is keyword-only, and the two
    cannot change places.

    Args:
        service: The service to call.
        item_id: The identifier of the item.
        tag_id: The identifier of the tag.

    Raises:
        TaxomeshTagNotFoundError: If the tag is not stored.
        TaxomeshItemNotFoundError: If the item is not stored.
    """
    service.items.untag(item=item_id, tag=tag_id)


def items_search(service: TaxomeshService, *, params: SearchItemsRequest) -> Sequence[Item]:
    """Search the items with every parameter of ``SearchItemsRequest``.

    The request object is named ``params`` and not ``body``: it serves a GET endpoint, which has
    no body.

    Args:
        service: The service to call.
        params: The validated search parameters.

    Returns:
        The items in order of relevance, at most ``params.limit`` of them.

    Raises:
        TaxomeshValidationError: If ``params.limit`` is 0 or less.
        TaxomeshCategoryNotFoundError: If ``params.category_id`` names a category that is not
            stored.
    """
    return service.items.search(
        params.query,
        limit=params.limit,
        category=params.category_id,
        enabled=params.enabled,
        fuzzy=params.fuzzy,
        recursive=params.recursive,
    )


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def tags_list(service: TaxomeshService, *, item_id: UUID | None = None) -> Sequence[Tag]:
    """List tags: every one, or those that an item has.

    Args:
        service: The service to call.
        item_id: When given, only the tags of this item, ordered by name.

    Returns:
        The matching tags.

    Raises:
        TaxomeshItemNotFoundError: If ``item_id`` names an item that is not stored.
    """
    return service.tags.list(item=item_id)


def tags_get(service: TaxomeshService, tag_id: UUID) -> Tag | None:
    """Return the tag with this identifier, or ``None``.

    Args:
        service: The service to call.
        tag_id: The identifier of the tag.

    Returns:
        The tag row, or ``None`` when no tag with this identifier is stored.
    """
    return service.tags.get(tag_id)


def tags_create(service: TaxomeshService, *, body: CreateTagRequest) -> Tag:
    """Create a tag.

    Args:
        service: The service to call.
        body: The validated request, with ``name`` and ``metadata``.

    Returns:
        The row of the new tag.
    """
    return service.tags.create(name=body.name, metadata=body.metadata)


def tags_update(service: TaxomeshService, tag_id: UUID, *, body: UpdateTagRequest) -> Tag:
    """Update a tag.

    Only the fields that the caller set are passed on: an omitted field carries no instruction and
    keeps the stored value. Neither field accepts null, so the request validation refuses a null
    before this handler runs. A present ``metadata`` replaces the stored one, as in the item and
    category updates.

    Each field is passed under its own keyword, and not unpacked from a model dump, so a service
    parameter with another name is a type error here, and not a ``TypeError`` at run time.

    Args:
        service: The service to call.
        tag_id: The identifier of the tag to update.
        body: The validated request; only the fields that the caller set are passed on.

    Returns:
        The new row of the tag.

    Raises:
        TaxomeshTagNotFoundError: If the tag is not stored.
    """
    provided = body.model_fields_set
    return service.tags.update(
        tag_id,
        name=body.name if "name" in provided else UNSET,
        metadata=body.metadata if "metadata" in provided else UNSET,
    )


def tags_delete(service: TaxomeshService, tag_id: UUID) -> None:
    """Delete a tag, and every link that names it.

    Args:
        service: The service to call.
        tag_id: The identifier of the tag to delete.

    Raises:
        TaxomeshTagNotFoundError: If the tag is not stored.
    """
    service.tags.delete(tag_id)


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def graph(service: TaxomeshService, *, enabled: bool | None = True) -> TaxomeshGraph:
    """Return the graph snapshot.

    Args:
        service: The service to call.
        enabled: ``True`` (the default) keeps only the enabled categories and items, ``False``
            only the disabled ones, and ``None`` all of them.

    Returns:
        The ``TaxomeshGraph``: the categories, their parent links and their items, as they were
        stored at the call.

    Note:
        A filtered graph is not the whole graph with some rows hidden. A link is kept only when
        both of its ends pass the filter, so ``enabled=False`` drops the parent link between a
        disabled category and an enabled parent. The child stays under each parent that the
        filter keeps. With none, it is in no node's children: ``walk()`` reaches it, and
        ``roots`` does not list it.
    """
    return service.graph(enabled=enabled)
