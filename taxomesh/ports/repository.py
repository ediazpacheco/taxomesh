"""Storage interface for the taxomesh repository layer.

``TaxomeshRepositoryBase`` is a ``typing.Protocol`` — any class that
implements all required methods with compatible signatures is a valid
repository. Explicit inheritance is NOT required; mypy verifies compliance
structurally at type-check time.
"""

from collections.abc import Collection
from typing import Any, Literal, Protocol
from uuid import UUID

from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink, Tag


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

        Raises:
            TaxomeshExternalIdConflictError: If category.external_id is not None and another
                record with a different category_id already holds the same external_id.
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

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return all stored categories ordered by name then category_id.

        Results are ordered ascending by ``name``; when two categories share the
        same name they are further ordered ascending by ``category_id`` for
        deterministic output.  ``Category`` has no direct ``sort_index`` field;
        ``name`` is the stable fallback for a global category listing.

        Returns:
            List of all categories ordered by ``(name ASC, category_id ASC)``;
            empty list if the store is empty.
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

        Raises:
            TaxomeshExternalIdConflictError: If item.external_id is not None and another
                record with a different item_id already holds the same external_id.
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

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return all stored items ordered by name then item_id.

        Results are ordered ascending by ``name``; when two items share the same
        name they are further ordered ascending by ``item_id`` for deterministic
        output.  ``Item`` has no direct ``sort_index`` field; ``name`` is the
        stable fallback for a global item listing.

        Returns:
            List of all items ordered by ``(name ASC, item_id ASC)``; empty
            list if the store is empty.
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
        """Upsert a category→parent relationship.

        If a link with the same (category_id, parent_category_id) pair already
        exists its sort_index is updated in-place. No duplicate is created.

        Args:
            link: The CategoryParentLink to persist.
        """
        ...

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all stored category-parent relationships grouped by parent then sort_index.

        Results are ordered by ``(parent_category_id ASC, sort_index ASC,
        category_id ASC)``.  Links are grouped so that all children of the same
        parent appear together, ordered by their ``sort_index`` within that
        group.  When two links share the same parent and ``sort_index``, they
        are further ordered by ``category_id`` for deterministic output.

        Returns:
            List of all CategoryParentLink records ordered by
            ``(parent_category_id ASC, sort_index ASC, category_id ASC)``;
            empty list if none exist.
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
        """Return all item→category placements grouped by category then sort_index.

        Results are ordered by ``(category_id ASC, sort_index ASC, item_id
        ASC)``.  Links are grouped so that all items in the same category appear
        together, ordered by their ``sort_index`` within that group.  When two
        links share the same category and ``sort_index``, they are further
        ordered by ``item_id`` for deterministic output.

        Returns:
            List of all ItemParentLink records ordered by
            ``(category_id ASC, sort_index ASC, item_id ASC)``; empty list if
            none exist.
        """
        ...

    # --- External-ID lookup ---

    def get_item_by_external_id(self, external_id: str) -> "Item | None":
        """Return the item with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Item, or None if no item has this external_id.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def get_category_by_external_id(self, external_id: str) -> "Category | None":
        """Return the category with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Category, or None if no category has this external_id.
            Root category filtering is the caller's responsibility.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """

    def get_items_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> "dict[str, Item]":
        """Return items whose external_id matches any value in external_ids.

        The input is pre-normalised: blank strings and duplicates have already
        been removed by the caller (e.g. ``TaxomeshService``). The adapter
        MUST NOT perform any further normalisation.

        Args:
            external_ids: A collection of external ID strings to look up.
                Guaranteed to contain no blank strings and no duplicates.
            enabled: ``True`` returns only enabled items; ``False`` only
                disabled; ``None`` (default) returns all matching items
                regardless of enabled state.

        Returns:
            A dict mapping each found external_id to its Item. Missing IDs
            are silently absent from the result — no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def get_categories_by_external_ids(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> "dict[str, Category]":
        """Return categories whose external_id matches any value in external_ids.

        The input is pre-normalised: blank strings and duplicates have already
        been removed by the caller (e.g. ``TaxomeshService``). The adapter
        MUST NOT perform any further normalisation.

        Root category exclusion is the service's responsibility, not the
        adapter's. The adapter returns the raw result including the root
        category if its external_id matches.

        Args:
            external_ids: A collection of external ID strings to look up.
                Guaranteed to contain no blank strings and no duplicates.
            enabled: ``True`` returns only enabled categories; ``False`` only
                disabled; ``None`` (default) returns all matching categories
                regardless of enabled state.

        Returns:
            A dict mapping each found external_id to its Category. Missing IDs
            are silently absent from the result — no error is raised.

        Raises:
            TaxomeshRepositoryError: On storage failure.
        """
        ...

    def get_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given non-empty slug, or None.

        Args:
            slug: A non-empty slug string to look up.

        Returns:
            The matching Item, or None if no item has this slug.
        """
        ...

    def get_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given non-empty slug, or None.

        Args:
            slug: A non-empty slug string to look up.

        Returns:
            The matching Category, or None if no category has this slug.
        """
        ...

    # --- Configuration introspection ---

    def get_config_summary(self) -> str:
        """Return a human-readable string describing this repository's configuration.

        Implementations MUST satisfy the following contract:

        - The returned string MUST be non-empty.
        - This method MUST NOT raise under any circumstances.
        - The returned string MUST NOT contain passwords, credentials, or other
          secrets; implementations are required to sanitize or omit sensitive values.

        Returns:
            A non-empty, human-readable description of the repository's
            configuration (e.g. the storage file path, a sanitized connection
            string, or a named data source identifier).
        """
        ...

    def get_debug_info(self) -> dict[str, Any]:
        """Return adapter-specific diagnostic information.

        Returns:
            A flat dict with adapter-specific diagnostic keys. Must never raise.
        """
        ...

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete a category→parent relationship.

        Args:
            category_id: The child category's UUID.
            parent_category_id: The parent category's UUID.

        Returns:
            True if the link was found and deleted; False if it did not exist.
        """
        ...

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete an item→category placement.

        Args:
            item_id: The item's UUID.
            category_id: The category's UUID.

        Returns:
            True if the placement was found and deleted; False if it did not exist.
        """
        ...

    # --- Item relation links ---

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Upsert a directed item-to-item relation.

        If a link with the same ``(source_item_id, target_item_id, relation_type)``
        triple already exists, its ``sort_index`` and ``metadata`` are updated in-place.
        No duplicate is created.

        Args:
            link: The ItemRelationLink to persist.
        """
        ...

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item, ordered by sort_index.

        Results are ordered by ``(sort_index ASC, source_item_id ASC,
        target_item_id ASC)``.  Filters are applied before sorting.

        Args:
            item_id: The UUID of the item to query.
            relation_type: Optional filter; if provided only links with this
                exact (already-normalised) type are returned.
            direction: ``"outgoing"`` returns links where ``source_item_id``
                equals ``item_id``; ``"incoming"`` returns links where
                ``target_item_id`` equals ``item_id``.

        Returns:
            List of matching ItemRelationLink objects ordered by
            ``(sort_index ASC, source_item_id ASC, target_item_id ASC)``;
            empty list if none match.
        """
        ...

    def list_item_relation_links_for_sources(
        self,
        source_item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
    ) -> list[ItemRelationLink]:
        """Return outgoing relation links for many source items in a single query.

        Eliminates the N+1 pattern that arises when calling
        :meth:`list_item_relation_links` in a loop over many source items.
        Only outgoing links (where ``source_item_id`` is in *source_item_ids*)
        are returned.  Results are ordered deterministically by
        ``(source_item_id ASC, relation_type ASC, sort_index ASC, target_item_id ASC)``.

        Args:
            source_item_ids: Collection of source UUIDs to query.
                An empty collection returns ``[]`` immediately without hitting storage.
            relation_types: Optional allow-list of relation type strings.
                ``None`` or ``[]`` means no filter — all types are returned.

        Returns:
            List of matching :class:`~taxomesh.domain.models.ItemRelationLink` objects
            in deterministic order; empty list if *source_item_ids* is empty or no
            links match.

        Example:

            # items: song_a (UUID a), song_b (UUID b), artist_x (UUID x), label_y (UUID y)
            # links: song_a --(performed_by)--> artist_x
            #        song_b --(performed_by)--> artist_x
            #        song_a --(released_by)-->  label_y

            links = repo.list_item_relation_links_for_sources(
                [song_a_id, song_b_id],
                relation_types=["performed_by"],
            )
            # → [
            #     ItemRelationLink(source=song_a_id, target=artist_x_id, relation_type="performed_by"),
            #     ItemRelationLink(source=song_b_id, target=artist_x_id, relation_type="performed_by"),
            #   ]
        """
        ...

    def delete_item_relation_link(
        self,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
    ) -> bool:
        """Delete the specific directed relation identified by the triple.

        Args:
            source_item_id: UUID of the source item.
            target_item_id: UUID of the target item.
            relation_type: Exact (already-normalised, lowercase) relation type string.

        Returns:
            True if the relation was found and deleted; False if it did not exist.
        """
        ...
