"""The storage port: the members that a taxomesh repository implements.

``TaxomeshRepositoryBase`` is a ``typing.Protocol``. A class that has every member below, with
compatible signatures, is a repository, and it does not need to inherit from the port. mypy checks
that a class has the members of the port.
"""

from collections.abc import Collection, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Literal, Protocol
from uuid import UUID

from taxomesh.domain.info import RepositoryInfo
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    ItemTagLink,
    Tag,
)


class TaxomeshRepositoryBase(Protocol):
    """The members that every storage backend implements: the contract of a repository.

    The names and the signatures below are the contract. Implement them in any class, with no
    inheritance, and give an instance to ``TaxomeshService`` when you build it.
    """

    # --- Atomicity boundary ---

    def atomic(self) -> AbstractContextManager[None]:
        """Return a context manager that groups writes, as far as the backend can.

        The collections run the writes of each member that writes more than once, such as
        ``categories.create``, ``add_parent``, ``move`` and ``reorder``, inside
        ``with repository.atomic():``.

        What the block guarantees depends on the backend:

        - **A backend with transactions**, such as ``DjangoRepository``, must roll back the whole
          block. If the body raises, every write in the block is rolled back, the inner blocks
          that the backend's own writes open (Django savepoints) included. The data is then as it
          was before the block.
        - **A backend without transactions**, such as ``JsonRepository``, ``YamlRepository`` or
          one in memory, does **not roll back**. When the block succeeds, the writes are the same
          as without the block. After a failure in the block, the writes made before the failure
          stay. Such a block does nothing, as ``contextlib.nullcontext()``, or only keeps other
          threads out while it is open, as the block of the file repositories does.

        Entering the block must not raise. On a normal exit, the writes are durable as the
        backend's writes always are. On an exit by an exception, the context manager must
        propagate the exception, and a backend with transactions also rolls back.

        Returns:
            A context manager for ``with repo.atomic():``, which yields ``None``.
        """
        ...

    # --- Category ---

    def save_category(self, category: Category, *, expected_version: int | None = None) -> Category:
        """Store a category row: insert it, or replace the stored row with its identifier.

        The given row does not change. The repository assigns the ``version`` of the stored row:
        an update stores the version of the row that it replaces plus one, whatever the given row
        has. With ``expected_version``, the save is a conditional update: the comparison and the
        write are one atomic step, so two writers that hold the same version cannot both succeed.

        Args:
            category: The category row to store.
            expected_version: The version that the stored row must be at, or ``None`` (the
                default) for no comparison. A row that is not stored is at no version.

        Returns:
            The row as stored, with the version that the repository assigned.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored; nothing is written.
            TaxomeshExternalIdConflictError: If ``category.external_id`` is not ``None`` and
                another category already has it.
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def find_category(self, category_id: UUID) -> Category | None:
        """Return the category with this identifier, or ``None``.

        Args:
            category_id: The identifier of the category.

        Returns:
            The category row, or ``None`` when no category with this identifier is stored.
        """
        ...

    def list_categories(self, *, enabled: bool | None = True) -> Sequence[Category]:
        """Return the stored categories, ordered by name and then by identifier.

        The order is ascending by ``name``, and two categories with the same name are in ascending
        order of ``category_id``, so the order is always the same. ``Category`` has no
        ``sort_index`` field of its own, so a listing of every category is ordered by ``name``.

        Args:
            enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching categories, ordered by ``(name ASC, category_id ASC)``; empty when none
            match.
        """
        ...

    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category and every link that names it, in one write.

        The links deleted with it are its parent links, as child and as parent, and its item
        placements. No stored link names the category afterwards.

        Args:
            category_id: The identifier of the category to delete.

        Returns:
            True if the category was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    # --- Item ---

    def save_item(self, item: Item, *, expected_version: int | None = None) -> Item:
        """Store an item row: insert it, or replace the stored row with its identifier.

        The given row does not change. The repository assigns the ``version`` of the stored row:
        an update stores the version of the row that it replaces plus one, whatever the given row
        has. With ``expected_version``, the save is a conditional update: the comparison and the
        write are one atomic step, so two writers that hold the same version cannot both succeed.

        Args:
            item: The item row to store.
            expected_version: The version that the stored row must be at, or ``None`` (the
                default) for no comparison. A row that is not stored is at no version.

        Returns:
            The row as stored, with the version that the repository assigned.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored; nothing is written.
            TaxomeshExternalIdConflictError: If ``item.external_id`` is not ``None`` and another
                item already has it.
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def find_item(self, item_id: UUID) -> Item | None:
        """Return the item with this identifier, or ``None``.

        Args:
            item_id: The identifier of the item.

        Returns:
            The item row, or ``None`` when no item with this identifier is stored.
        """
        ...

    def list_items(self, *, enabled: bool | None = True) -> Sequence[Item]:
        """Return the stored items, ordered by name and then by identifier.

        The order is ascending by ``name``, and two items with the same name are in ascending order
        of ``item_id``, so the order is always the same. ``Item`` has no ``sort_index`` field of its
        own, so a listing of every item is ordered by ``name``.

        Args:
            enabled: ``True`` (the default) returns only the enabled items, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching items, ordered by ``(name ASC, item_id ASC)``; empty when none match.
        """
        ...

    def delete_item(self, item_id: UUID) -> bool:
        """Delete an item and every link that names it, in one write.

        The links deleted with it are its placements, its tag links and its relation links at
        either end. No stored link names the item afterwards.

        Args:
            item_id: The identifier of the item to delete.

        Returns:
            True if the item was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    # --- Tag ---

    def save_tag(self, tag: Tag) -> None:
        """Store a tag row: insert it, or replace the stored row with its identifier.

        Args:
            tag: The tag row to store.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def find_tag(self, tag_id: UUID) -> Tag | None:
        """Return the tag with this identifier, or ``None``.

        Args:
            tag_id: The identifier of the tag.

        Returns:
            The tag row, or ``None`` when no tag with this identifier is stored.
        """
        ...

    def list_tags(self) -> Sequence[Tag]:
        """Return every stored tag.

        Returns:
            Every tag row; empty when no tag is stored.
        """
        ...

    def map_tags_by_id(self, tag_ids: Collection[UUID]) -> "Mapping[UUID, Tag]":
        """Return the tags whose ``tag_id`` is in ``tag_ids``, in one read.

        A tag has no ``enabled`` field, so this member takes no ``enabled`` filter.

        Args:
            tag_ids: The identifiers of the tags to look up. An empty collection returns an empty
                mapping.

        Returns:
            A mapping from the identifier of each stored tag to its row. An identifier that names
            no stored tag is left out of the mapping, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    # --- Tag ↔ Item association ---

    def add_item_tag_link(self, item_id: UUID, tag_id: UUID) -> None:
        """Store a tag link: the tag on the item. Nothing changes when the link is already stored.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def delete_item_tag_link(self, item_id: UUID, tag_id: UUID) -> bool:
        """Delete the tag link of this tag on this item.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Returns:
            True if the link was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def list_item_tag_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        tag_ids: Collection[UUID] | None = None,
    ) -> Sequence[ItemTagLink]:
        """Return the stored tag links, filtered by either end when a filter is given.

        The order is ``(item_id ASC, tag_id ASC)``. A tag link has no sort index, so its two
        identifiers are the whole order. Every combination of filters keeps this order.

        Args:
            item_ids: When given, only the links whose ``item_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no item filter.
            tag_ids: When given, only the links whose ``tag_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no tag filter. When both filters are given, a link must match
                both.

        Returns:
            The matching links, ordered by ``(item_id ASC, tag_id ASC)``; empty when none match.
            With both filters ``None``, every stored link.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    # --- Category parent links ---

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Store a parent link: insert it, or update the stored one.

        When a link with the same ``(category_id, parent_category_id)`` is stored, its
        ``sort_index`` is updated. No second link is created.

        Args:
            link: The parent link to store.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> Sequence[CategoryParentLink]:
        """Return the stored parent links, filtered by either end when a filter is given.

        The order is ``(parent_category_id ASC, sort_index ASC, category_id ASC)``. So the children
        of one parent are together, in the order of their ``sort_index``, and two links with the
        same parent and ``sort_index`` are in the order of ``category_id``. Every combination of
        filters keeps this order.

        Args:
            category_ids: When given, only the links whose ``category_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no child filter.
            parent_category_ids: When given, only the links whose ``parent_category_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no parent filter. When both
                filters are given, a link must match both.

        Returns:
            The matching links, ordered by ``(parent_category_id ASC, sort_index ASC,
            category_id ASC)``; empty when none match. With both filters ``None``, every stored
            link.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    # --- Tag delete ---

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete a tag and every link that names it, in one write.

        The links deleted with it are its tag links. No stored link names the tag afterwards.

        Args:
            tag_id: The identifier of the tag to delete.

        Returns:
            True if the tag was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    # --- Item → Category placement ---

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Store a placement: insert it, or update the stored one.

        When a placement with the same ``(item_id, category_id)`` is stored, its ``sort_index`` is
        updated. No second placement is created.

        Args:
            link: The placement to store.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def list_item_parent_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> Sequence[ItemParentLink]:
        """Return the stored placements, filtered by either end when a filter is given.

        The order is ``(category_id ASC, sort_index ASC, item_id ASC)``. So the items of one
        category are together, in the order of their ``sort_index``, and two placements with the
        same category and ``sort_index`` are in the order of ``item_id``. Every combination of
        filters keeps this order.

        Args:
            item_ids: When given, only the links whose ``item_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no item filter.
            category_ids: When given, only the links whose ``category_id`` is in it are returned. An
                **empty** collection returns ``[]``: it is **not** "no filter". ``None`` (the
                default) applies no category filter. When both
                filters are given, a link must match both.

        Returns:
            The matching placements, ordered by ``(category_id ASC, sort_index ASC, item_id ASC)``;
            empty when none match. With both filters ``None``, every stored placement.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    # --- External-ID lookup ---

    def find_item_by_external_id(self, external_id: str) -> "Item | None":
        """Return the item with the given external_id, or None.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The item row, or ``None`` when no item has this external id.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def find_category_by_external_id(self, external_id: str) -> "Category | None":
        """Return the category with the given external_id, or None.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The category row, or ``None`` when no category has this external id. The repository
            does not leave out the implicit root: the caller does.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """

    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> "Mapping[UUID, Item]":
        """Return the items whose ``item_id`` is in ``item_ids``.

        The caller, such as ``TaxomeshService``, removes the duplicates before the call. The
        repository must not change the input further.

        Args:
            item_ids: The identifiers of the items to look up, with no duplicates. An empty
                collection returns an empty mapping.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A mapping from the identifier of each stored item to its row. An identifier that names
            no stored item is left out of the mapping, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> "Mapping[UUID, Category]":
        """Return the categories whose ``category_id`` is in ``category_ids``.

        The caller, such as ``TaxomeshService``, removes the duplicates before the call. The
        repository must not change the input further.

        The repository passes the collection to its storage as one request, and must not split it.
        When the storage has a limit for each query, that limit is the library's limit, and a
        request over it raises ``TaxomeshRepositoryError``, as any other storage failure does.

        Args:
            category_ids: The identifiers of the categories to look up, with no duplicates. An
                empty collection returns an empty mapping, and storage is not read.
            enabled: ``True`` returns only the enabled categories, ``False`` only the disabled
                ones, and ``None`` (the default) every matching category.

        Returns:
            A mapping from the identifier of each stored category to its row. An identifier that
            names no stored category is left out of the mapping, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def map_items_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> "Mapping[str, Item]":
        """Return the items whose ``external_id`` is in ``external_ids``.

        The caller, such as ``TaxomeshService``, converts each value to its stored form with the
        one rule that writes use, and removes the duplicates. The repository must not change the
        input further: a value matches a row only as written. Surrounding whitespace counts, and the
        empty string is a value like any other.

        Args:
            external_ids: The external ids to look up, in stored form, with no duplicates.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A mapping from the external id of each stored item to its row. An external id that no
            stored item has is left out of the mapping, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def map_categories_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> "Mapping[str, Category]":
        """Return the categories whose ``external_id`` is in ``external_ids``.

        The caller, such as ``TaxomeshService``, converts each value to its stored form with the
        one rule that writes use, and removes the duplicates. The repository must not change the
        input further: a value matches a row only as written. Surrounding whitespace counts, and the
        empty string is a value like any other.

        The service leaves out the implicit root, and the repository does not: the repository
        returns the implicit root too when its external id matches.

        Args:
            external_ids: The external ids to look up, in stored form, with no duplicates.
            enabled: ``True`` returns only the enabled categories, ``False`` only the disabled
                ones, and ``None`` (the default) every matching category.

        Returns:
            A mapping from the external id of each stored category to its row. An external id that
            no stored category has is left out of the mapping, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def find_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given non-empty slug, or None.

        Args:
            slug: A non-empty slug string to look up.

        Returns:
            The matching Item, or None if no item has this slug.
        """
        ...

    def find_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given non-empty slug, or None.

        Args:
            slug: A non-empty slug string to look up.

        Returns:
            The matching Category, or None if no category has this slug.
        """
        ...

    # --- Configuration introspection ---

    @property
    def config_summary(self) -> str:
        """Text, for a person to read, that describes the configuration of this repository.

        An implementation must keep this contract:

        - The text is not empty.
        - Reading it never raises.
        - The text contains no password, credential or other secret: the implementation removes
          or masks each sensitive value.

        Returns:
            A description of the configuration of the repository, not empty, for a person to read:
            for example, the path of the storage file, a connection string without its secrets, or
            the name of a data source.
        """
        ...

    def describe(self) -> RepositoryInfo:
        """Return what this repository reports about itself.

        Returns:
            A :class:`RepositoryInfo` that names the class of the repository, its storage path if
            it has one, and the facts that only its backend has. This member must never raise.
        """
        ...

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete the parent link of this category under this parent.

        Args:
            category_id: The identifier of the child category.
            parent_category_id: The identifier of the parent category.

        Returns:
            True if the link was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete the placement of this item in this category.

        Args:
            item_id: The identifier of the item.
            category_id: The identifier of the category.

        Returns:
            True if the placement was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    # --- Item relation links ---

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Store a relation: insert it, or update the stored one.

        When a relation with the same ``(source_item_id, target_item_id, relation_type)`` is
        stored, its ``sort_index`` and ``metadata`` are updated. No second relation is created.

        Args:
            link: The relation to store.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> Sequence[ItemRelationLink]:
        """Return the relations of one item, ordered by sort index.

        The order is ``(sort_index ASC, source_item_id ASC, target_item_id ASC)``. The filters
        apply before the sort.

        Args:
            item_id: The identifier of the item.
            relation_types: The relation types to keep, already stripped and in lowercase, as
                :meth:`list_item_relation_links_batch` takes them. ``None`` or an empty collection
                is no filter.
            direction: ``"outgoing"`` returns the links whose ``source_item_id`` is ``item_id``;
                ``"incoming"`` the links whose ``target_item_id`` is ``item_id``; ``"both"`` the
                links whose source *or* target is ``item_id``, each link at most once.

        Returns:
            The matching relations, ordered by ``(sort_index ASC, source_item_id ASC,
            target_item_id ASC)``; empty when none match.
        """
        ...

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> Sequence[ItemRelationLink]:
        """Return the relations of many items in one query, by direction.

        One call replaces a loop of :meth:`list_item_relation_links` calls, one for each item: the
        N+1 query pattern. One query reads every given item, whatever the *direction*: ``"both"``
        also uses one ``source OR target`` query, and not two.

        What each direction selects, and its fixed order:

        - ``"outgoing"``: links where ``source_item_id`` is in *item_ids*,
          ordered by ``(source_item_id, relation_type, sort_index, target_item_id)``.
        - ``"incoming"``: links where ``target_item_id`` is in *item_ids*,
          ordered by ``(target_item_id, relation_type, sort_index, source_item_id)``.
        - ``"both"``: links where *item_ids* contains the source **or** the
          target, ordered by ``(sort_index, source_item_id, target_item_id)``.

        Args:
            item_ids: The identifiers of the items. An empty collection returns ``[]`` at once,
                and storage is not read.
            relation_types: The relation types to keep. ``None`` or ``[]`` is no filter: every type
                is returned.
            direction: The end of the link that the given items are matched on.

        Returns:
            The matching :class:`~taxomesh.domain.models.ItemRelationLink` relations, in the fixed
            order above; empty when *item_ids* is empty or no link matches.

        Example::

            # links: item_a --(related_to)--> item_b
            #        item_c --(related_to)--> item_b

            links = repo.list_item_relation_links_batch(
                [item_b_id],
                direction="incoming",
                relation_types=["related_to"],
            )
            # → [
            #     ItemRelationLink(source=item_a_id, target=item_b_id, relation_type="related_to"),
            #     ItemRelationLink(source=item_c_id, target=item_b_id, relation_type="related_to"),
            #   ]
        """
        ...

    def delete_item_relation_link(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> bool:
        """Delete the one relation that these three values name.

        Args:
            source_item_id: The identifier of the source item.
            target_item_id: The identifier of the target item.
            relation_type: The relation type exactly as stored: stripped and in lowercase.

        Returns:
            True if the relation was found and deleted; False if it did not exist.

        Raises:
            TaxomeshRepositoryError: On storage failure; nothing is written.
        """
        ...
