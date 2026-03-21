"""DjangoRepository — taxomesh storage adapter backed by the Django ORM.

All Django imports are deferred inside ``__init__`` and method bodies
so that ``import taxomesh`` succeeds even when Django is not installed.
Every deferred import line carries ``# noqa: PLC0415``.

Usage::

    from taxomesh import TaxomeshService
    from taxomesh.adapters.repositories.django_repository import DjangoRepository

    svc = TaxomeshService(repository=DjangoRepository())
"""

from collections.abc import Collection
from typing import Any, Final, Literal
from uuid import UUID

from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    Tag,
)

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

_USING_DEFAULT = "default"
DJANGO_REPO_TYPE: Final[str] = "django"


class DjangoRepository:
    """taxomesh storage adapter that persists data via the Django ORM.

    Satisfies ``TaxomeshRepositoryBase`` structurally — no inheritance required.

    All Django symbols are imported inside ``__init__`` and every method body;
    no Django import appears at module level. This allows ``import taxomesh``
    to succeed without Django installed.

    Args:
        using: Django database alias (default: ``"default"``).

    Raises:
        TaxomeshRepositoryError: If Django is not installed. The error message
            includes the installation hint ``pip install taxomesh[django]``.
    """

    def __init__(self, using: str = _USING_DEFAULT) -> None:
        """Initialise the repository, verifying that Django is available.

        Args:
            using: Django database alias (default: ``"default"``).

        Raises:
            TaxomeshRepositoryError: If Django cannot be imported.
        """
        try:
            from taxomesh.contrib.django.models import (  # noqa: PLC0415
                CategoryModel,
                CategoryParentLinkModel,
                ItemModel,
                ItemParentLinkModel,
                ItemRelationLinkModel,
                ItemTagLinkModel,
                TagModel,
            )
        except ImportError as exc:
            from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

            raise TaxomeshRepositoryError("Django is not installed. Run: pip install taxomesh[django]") from exc
        except Exception as exc:
            try:
                from django.core.exceptions import (  # type: ignore[import-untyped]  # noqa: PLC0415
                    ImproperlyConfigured,
                )

                if isinstance(exc, ImproperlyConfigured):
                    from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

                    raise TaxomeshRepositoryError(
                        "Django settings are not configured. "
                        "Set the DJANGO_SETTINGS_MODULE environment variable before running "
                        "taxomesh with type = 'django'."
                    ) from exc
            except ImportError:
                pass
            raise

        self._using = using
        # Keep references to avoid repeated imports in hot paths
        self._CategoryModel = CategoryModel
        self._ItemModel = ItemModel
        self._TagModel = TagModel
        self._CategoryParentLinkModel = CategoryParentLinkModel
        self._ItemParentLinkModel = ItemParentLinkModel
        self._ItemTagLinkModel = ItemTagLinkModel
        self._ItemRelationLinkModel = ItemRelationLinkModel

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_category(self, row: object) -> Category:
        """Convert an ORM CategoryModel row to a domain Category."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return Category(
            category_id=row.category_id,  # type: ignore[attr-defined]
            name=row.name,  # type: ignore[attr-defined]
            description=row.description,  # type: ignore[attr-defined]
            enabled=row.enabled,  # type: ignore[attr-defined]
            external_id=row.external_id,  # type: ignore[attr-defined]
            slug=row.slug,  # type: ignore[attr-defined]
            metadata=row.metadata,  # type: ignore[attr-defined]
        )

    def _row_to_item(self, row: object) -> Item:
        """Convert an ORM ItemModel row to a domain Item."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return Item(
            item_id=row.item_id,  # type: ignore[attr-defined]
            name=row.name,  # type: ignore[attr-defined]
            external_id=row.external_id,  # type: ignore[attr-defined]
            slug=row.slug,  # type: ignore[attr-defined]
            enabled=row.enabled,  # type: ignore[attr-defined]
            metadata=row.metadata,  # type: ignore[attr-defined]
        )

    def _row_to_tag(self, row: object) -> Tag:
        """Convert an ORM TagModel row to a domain Tag."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return Tag(
            tag_id=row.tag_id,  # type: ignore[attr-defined]
            name=row.name,  # type: ignore[attr-defined]
            metadata=row.metadata,  # type: ignore[attr-defined]
        )

    def _row_to_category_parent_link(self, row: object) -> CategoryParentLink:
        """Convert an ORM CategoryParentLinkModel row to a domain CategoryParentLink."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return CategoryParentLink(
            category_id=row.category_id,  # type: ignore[attr-defined]
            parent_category_id=row.parent_category_id,  # type: ignore[attr-defined]
            sort_index=row.sort_index,  # type: ignore[attr-defined]
        )

    def _row_to_item_parent_link(self, row: object) -> ItemParentLink:
        """Convert an ORM ItemParentLinkModel row to a domain ItemParentLink."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return ItemParentLink(
            item_id=row.item_id,  # type: ignore[attr-defined]
            category_id=row.category_id,  # type: ignore[attr-defined]
            sort_index=row.sort_index,  # type: ignore[attr-defined]
        )

    def _row_to_item_relation_link(self, row: object) -> ItemRelationLink:
        """Convert an ORM ItemRelationLinkModel row to a domain ItemRelationLink."""
        # row is typed as object because Django ORM classes are only available at runtime (deferred import).
        return ItemRelationLink(
            source_item_id=row.source_item_id,  # type: ignore[attr-defined]
            target_item_id=row.target_item_id,  # type: ignore[attr-defined]
            relation_type=row.relation_type,  # type: ignore[attr-defined]
            sort_index=row.sort_index,  # type: ignore[attr-defined]
            metadata=row.metadata,  # type: ignore[attr-defined]
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def get_config_summary(self) -> str:
        """Return a safe configuration summary string.

        Format: ``django:<engine>/<alias>``.  Never includes NAME, USER,
        PASSWORD, HOST, or PORT.

        Returns:
            A non-empty summary string safe for display in CLI output.
        """
        from django.conf import settings  # type: ignore[import-untyped]  # noqa: PLC0415

        engine: str = settings.DATABASES[self._using]["ENGINE"].split(".")[-1]
        return f"django:{engine}/{self._using}"

    def get_debug_info(self) -> dict[str, Any]:
        """Return diagnostic info for this Django repository.

        Returns:
            Dict with key database_alias containing the Django database alias.
        """
        return {"database_alias": self._using}

    # ------------------------------------------------------------------
    # Category CRUD
    # ------------------------------------------------------------------

    def save_category(self, category: Category) -> None:
        """Persist a category (insert or update).

        Args:
            category: The Category domain object to save.

        Raises:
            TaxomeshExternalIdConflictError: If category.external_id is not None and another
                record with a different category_id already holds the same external_id.
            TaxomeshRepositoryError: On any other database error.
        """
        from django.db import (  # type: ignore[import-untyped]  # noqa: PLC0415
            DatabaseError,
            IntegrityError,
            transaction,
        )

        from taxomesh.exceptions import TaxomeshExternalIdConflictError, TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._CategoryModel.objects.using(self._using).update_or_create(
                    category_id=category.category_id,
                    defaults={
                        "name": category.name,
                        "description": category.description,
                        "enabled": category.enabled,
                        "external_id": category.external_id,
                        "slug": category.slug,
                        "metadata": category.metadata,
                    },
                )
        except IntegrityError as exc:
            raise TaxomeshExternalIdConflictError(
                f"external_id {category.external_id!r} is already assigned to another category."
            ) from exc
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def get_category(self, category_id: UUID) -> Category | None:
        """Return the category with the given ID, or None if absent.

        Args:
            category_id: UUID of the category to retrieve.

        Returns:
            The matching Category domain object, or None.
        """
        row = self._CategoryModel.objects.using(self._using).filter(category_id=category_id).first()
        if row is None:
            return None
        return self._row_to_category(row)

    def list_categories(self) -> list[Category]:
        """Return all categories ordered by name then category_id.

        Returns:
            A list of Category domain objects ordered by ``(name ASC, category_id ASC)``.
        """
        return [
            self._row_to_category(row)
            for row in self._CategoryModel.objects.using(self._using).order_by("name", "category_id")
        ]

    def delete_category(self, category_id: UUID) -> bool:
        """Delete the category with the given ID.

        Associated link rows are removed automatically via ``on_delete=CASCADE``.

        Args:
            category_id: UUID of the category to delete.

        Returns:
            True if a row was deleted, False if the category did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = self._CategoryModel.objects.using(self._using).filter(category_id=category_id).delete()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # Item CRUD
    # ------------------------------------------------------------------

    def save_item(self, item: Item) -> None:
        """Persist an item (insert or update).

        Args:
            item: The Item domain object to save.

        Raises:
            TaxomeshExternalIdConflictError: If item.external_id is not None and another
                record with a different item_id already holds the same external_id.
            TaxomeshRepositoryError: On any other database error.
        """
        from django.db import DatabaseError, IntegrityError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshExternalIdConflictError, TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._ItemModel.objects.using(self._using).update_or_create(
                    item_id=item.item_id,
                    defaults={
                        "name": item.name,
                        "external_id": item.external_id,
                        "slug": item.slug,
                        "enabled": item.enabled,
                        "metadata": item.metadata,
                    },
                )
        except IntegrityError as exc:
            raise TaxomeshExternalIdConflictError(
                f"external_id {item.external_id!r} is already assigned to another item."
            ) from exc
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def get_item(self, item_id: UUID) -> Item | None:
        """Return the item with the given ID, or None if absent.

        Args:
            item_id: UUID of the item to retrieve.

        Returns:
            The matching Item domain object, or None.
        """
        row = self._ItemModel.objects.using(self._using).filter(item_id=item_id).first()
        if row is None:
            return None
        return self._row_to_item(row)

    def list_items(self) -> list[Item]:
        """Return all items ordered by name then item_id.

        Returns:
            A list of Item domain objects ordered by ``(name ASC, item_id ASC)``.
        """
        return [
            self._row_to_item(row) for row in self._ItemModel.objects.using(self._using).order_by("name", "item_id")
        ]

    def delete_item(self, item_id: UUID) -> bool:
        """Delete the item with the given ID.

        Args:
            item_id: UUID of the item to delete.

        Returns:
            True if a row was deleted, False if the item did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = self._ItemModel.objects.using(self._using).filter(item_id=item_id).delete()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # Tag CRUD
    # ------------------------------------------------------------------

    def save_tag(self, tag: Tag) -> None:
        """Persist a tag (insert or update).

        Args:
            tag: The Tag domain object to save.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._TagModel.objects.using(self._using).update_or_create(
                    tag_id=tag.tag_id,
                    defaults={
                        "name": tag.name,
                        "metadata": tag.metadata,
                    },
                )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def get_tag(self, tag_id: UUID) -> Tag | None:
        """Return the tag with the given ID, or None if absent.

        Args:
            tag_id: UUID of the tag to retrieve.

        Returns:
            The matching Tag domain object, or None.
        """
        row = self._TagModel.objects.using(self._using).filter(tag_id=tag_id).first()
        if row is None:
            return None
        return self._row_to_tag(row)

    def list_tags(self) -> list[Tag]:
        """Return all tags without ordering guarantee.

        Returns:
            A list of Tag domain objects (order undefined).
        """
        return [self._row_to_tag(row) for row in self._TagModel.objects.using(self._using).all()]

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete the tag with the given ID.

        Args:
            tag_id: UUID of the tag to delete.

        Returns:
            True if a row was deleted, False if the tag did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = self._TagModel.objects.using(self._using).filter(tag_id=tag_id).delete()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # Tag ↔ Item links
    # ------------------------------------------------------------------

    def assign_tag(self, tag_id: UUID, item_id: UUID) -> None:
        """Assign a tag to an item (idempotent).

        Calling this method twice for the same ``(tag_id, item_id)`` pair
        results in exactly one row in the link table.

        Args:
            tag_id: UUID of the tag to assign.
            item_id: UUID of the item to tag.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._ItemTagLinkModel.objects.using(self._using).get_or_create(
                    tag_id=tag_id,
                    item_id=item_id,
                )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def remove_tag(self, tag_id: UUID, item_id: UUID) -> bool:
        """Remove a tag assignment from an item.

        Args:
            tag_id: UUID of the tag to remove.
            item_id: UUID of the item.

        Returns:
            True if the link was found and removed, False if it did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = (
                self._ItemTagLinkModel.objects.using(self._using).filter(tag_id=tag_id, item_id=item_id).delete()
            )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # Category parent links
    # ------------------------------------------------------------------

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Persist a category→parent relationship (upsert).

        If a link for the same ``(category_id, parent_category_id)`` pair already
        exists its ``sort_index`` is updated. Only one link per pair is kept.

        Args:
            link: The CategoryParentLink domain object to save.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._CategoryParentLinkModel.objects.using(self._using).update_or_create(
                    category_id=link.category_id,
                    parent_category_id=link.parent_category_id,
                    defaults={"sort_index": link.sort_index},
                )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def list_category_parent_links(self) -> list[CategoryParentLink]:
        """Return all category parent links ordered by parent then sort_index then category.

        Returns:
            A list of CategoryParentLink domain objects ordered by
            ``(parent_category_id ASC, sort_index ASC, category_id ASC)``.
        """
        return [
            self._row_to_category_parent_link(row)
            for row in self._CategoryParentLinkModel.objects.using(self._using).order_by(
                "parent_category_id", "sort_index", "category_id"
            )
        ]

    # ------------------------------------------------------------------
    # Item parent links
    # ------------------------------------------------------------------

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Persist an item→category placement (upsert).

        If a link for the same ``(item_id, category_id)`` pair already exists its
        ``sort_index`` is updated.

        Args:
            link: The ItemParentLink domain object to save.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._ItemParentLinkModel.objects.using(self._using).update_or_create(
                    item_id=link.item_id,
                    category_id=link.category_id,
                    defaults={"sort_index": link.sort_index},
                )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def list_item_parent_links(self) -> list[ItemParentLink]:
        """Return all item parent links ordered by category then sort_index then item.

        Returns:
            A list of ItemParentLink domain objects ordered by
            ``(category_id ASC, sort_index ASC, item_id ASC)``.
        """
        return [
            self._row_to_item_parent_link(row)
            for row in self._ItemParentLinkModel.objects.using(self._using).order_by(
                "category_id", "sort_index", "item_id"
            )
        ]

    # ------------------------------------------------------------------
    # Link deletion
    # ------------------------------------------------------------------

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete a category→parent relationship.

        Args:
            category_id: The child category's UUID.
            parent_category_id: The parent category's UUID.

        Returns:
            True if the link was found and deleted; False if it did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = (
                self._CategoryParentLinkModel.objects.using(self._using)
                .filter(category_id=category_id, parent_category_id=parent_category_id)
                .delete()
            )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete an item→category placement.

        Args:
            item_id: The item's UUID.
            category_id: The category's UUID.

        Returns:
            True if the placement was found and deleted; False if it did not exist.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = (
                self._ItemParentLinkModel.objects.using(self._using)
                .filter(item_id=item_id, category_id=category_id)
                .delete()
            )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # External-ID lookup
    # ------------------------------------------------------------------

    def get_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Item domain object, or None if not found.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            row = self._ItemModel.objects.using(self._using).filter(external_id=external_id).first()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return self._row_to_item(row) if row is not None else None

    def get_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with the given external_id, or None.

        Args:
            external_id: The external identifier to look up (already a str; never None).

        Returns:
            The matching Category domain object, or None if not found.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            row = self._CategoryModel.objects.using(self._using).filter(external_id=external_id).first()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return self._row_to_category(row) if row is not None else None

    def get_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with the given slug, or None.

        Args:
            slug: The slug to look up.

        Returns:
            The matching Item domain object, or None.
        """
        row = self._ItemModel.objects.using(self._using).filter(slug=slug).first()
        return self._row_to_item(row) if row is not None else None

    def get_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with the given slug, or None.

        Args:
            slug: The slug to look up.

        Returns:
            The matching Category domain object, or None.
        """
        row = self._CategoryModel.objects.using(self._using).filter(slug=slug).first()
        return self._row_to_category(row) if row is not None else None

    # ------------------------------------------------------------------
    # Item relation links
    # ------------------------------------------------------------------

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Upsert a directed item-to-item relation.

        Args:
            link: The ItemRelationLink to persist.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            with transaction.atomic(using=self._using):
                self._ItemRelationLinkModel.objects.using(self._using).update_or_create(
                    source_item_id=link.source_item_id,
                    target_item_id=link.target_item_id,
                    relation_type=link.relation_type,
                    defaults={"sort_index": link.sort_index, "metadata": link.metadata},
                )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def list_item_relation_links(
        self,
        item_id: UUID,
        *,
        relation_type: str | None = None,
        direction: Literal["outgoing", "incoming"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return item relation links for the given item.

        Args:
            item_id: The UUID of the item to query.
            relation_type: Optional filter; if provided only links with this
                exact (already-normalised) type are returned.
            direction: ``"outgoing"`` returns links where ``source_item_id``
                equals ``item_id``; ``"incoming"`` returns links where
                ``target_item_id`` equals ``item_id``.

        Returns:
            List of matching ItemRelationLink objects; empty list if none match.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            if direction == "outgoing":
                qs = self._ItemRelationLinkModel.objects.using(self._using).filter(source_item_id=item_id)
            else:
                qs = self._ItemRelationLinkModel.objects.using(self._using).filter(target_item_id=item_id)
            if relation_type is not None:
                qs = qs.filter(relation_type=relation_type)
            qs = qs.order_by("sort_index", "source_item_id", "target_item_id")
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return [self._row_to_item_relation_link(row) for row in qs]

    def list_item_relation_links_for_sources(
        self,
        source_item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
    ) -> list[ItemRelationLink]:
        """Return outgoing links for many source items via single ORM query."""
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        source_list = list(source_item_ids)
        if not source_list:
            return []
        try:
            qs = self._ItemRelationLinkModel.objects.using(self._using).filter(source_item_id__in=source_list)
            if relation_types:
                qs = qs.filter(relation_type__in=list(relation_types))
            qs = qs.order_by("source_item_id", "relation_type", "sort_index", "target_item_id")
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return [self._row_to_item_relation_link(row) for row in qs]

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
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            deleted_count, _ = (
                self._ItemRelationLinkModel.objects.using(self._using)
                .filter(
                    source_item_id=source_item_id,
                    target_item_id=target_item_id,
                    relation_type=relation_type,
                )
                .delete()
            )
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return int(deleted_count) > 0

    # ------------------------------------------------------------------
    # Django-specific extras (outside protocol)
    # ------------------------------------------------------------------

    def assignable_categories_qs(self) -> Any:
        """Return ORM queryset of enabled, non-root categories for admin autocomplete.

        This method is outside the ``TaxomeshRepositoryBase`` protocol — it is
        Django-ORM-specific and has no generic equivalent. Consumers that need
        this method must import ``DjangoRepository`` directly.

        Filters applied:
        - ``enabled=True``
        - ``name != "__root__"`` (root category excluded)

        Returns:
            A lazy Django ``QuerySet[CategoryModel]`` ready for further filtering,
            ordering, or use in admin autocomplete widgets.

        Raises:
            TaxomeshRepositoryError: On database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            return self._CategoryModel.objects.using(self._using).filter(enabled=True).exclude(name=ROOT_CATEGORY_NAME)
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
