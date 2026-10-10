"""DjangoRepository — taxomesh storage adapter backed by the Django ORM.

Every Django import is inside ``__init__`` or a method body, so that this module, and
``import taxomesh``, work when Django is not installed.
Every deferred import line carries ``# noqa: PLC0415``. The ORM models and ``QuerySet`` are
imported at module level for the type checker only, under ``TYPE_CHECKING``.

Usage::

    from taxomesh import TaxomeshService
    from taxomesh.adapters.repositories.django_repository import DjangoRepository

    svc = TaxomeshService(repository=DjangoRepository())
"""

from collections.abc import Collection, Mapping
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID

from taxomesh.adapters.repositories._version import version_conflict
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
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

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from taxomesh.contrib.django.models import (
        CategoryModel,
        CategoryParentLinkModel,
        ItemModel,
        ItemParentLinkModel,
        ItemRelationLinkModel,
        TagModel,
    )

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

_USING_DEFAULT = "default"
DJANGO_REPO_TYPE: Final[str] = "django"


class DjangoRepository:
    """The storage adapter that stores taxomesh data through the Django ORM.

    It has the members of ``TaxomeshRepositoryBase``, and it does not inherit from the port.

    Args:
        using: The Django database alias. The default is ``"default"``.

    Raises:
        TaxomeshRepositoryError: If Django is not installed, with a message that names
            ``pip install taxomesh[django]``, or if the settings of Django are not configured.
    """

    def __init__(self, using: str = _USING_DEFAULT) -> None:
        """Check that Django is installed and configured, and keep the ORM models.

        Args:
            using: The Django database alias. The default is ``"default"``.

        Raises:
            TaxomeshRepositoryError: If Django cannot be imported, or if its settings are not
                configured.
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
                from django.core.exceptions import (  # noqa: PLC0415
                    ImproperlyConfigured,
                )

                if isinstance(exc, ImproperlyConfigured):
                    from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

                    raise TaxomeshRepositoryError(
                        "Django settings are not configured: set the DJANGO_SETTINGS_MODULE environment "
                        "variable before running taxomesh with type = 'django'"
                    ) from exc
            except ImportError:
                pass
            raise

        self._using = using
        # The ORM models, kept so that no member imports them again
        self._CategoryModel = CategoryModel
        self._ItemModel = ItemModel
        self._TagModel = TagModel
        self._CategoryParentLinkModel = CategoryParentLinkModel
        self._ItemParentLinkModel = ItemParentLinkModel
        self._ItemTagLinkModel = ItemTagLinkModel
        self._ItemRelationLinkModel = ItemRelationLinkModel

    def __repr__(self) -> str:
        """Render as the constructor call that opens the same database alias."""
        return f"{type(self).__name__}(using={self._using!r})"

    # ------------------------------------------------------------------
    # Atomicity boundary
    # ------------------------------------------------------------------

    def atomic(self) -> AbstractContextManager[None]:
        """Return a database transaction that rolls back **every** write of the block on a failure.

        The block is ``django.db.transaction.atomic`` on this repository's database. When a
        collection runs the writes of one member inside it and the body raises, the whole
        transaction rolls back, and no write of the block is committed.

        Django's ``atomic()`` blocks nest. The outermost block opens the database transaction, and
        the ``transaction.atomic`` block that each write of this repository opens, such as
        ``save_category`` or ``save_item_parent_link``, is a **savepoint** inside it. An exception
        that leaves the block rolls back every savepoint and the transaction, so the data is as it
        was before the block.
        """
        from django.db import transaction  # noqa: PLC0415

        result: AbstractContextManager[None] = transaction.atomic(using=self._using)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_category(self, row: "CategoryModel") -> Category:
        """Build the ``Category`` row from its ORM object."""
        return Category(
            category_id=row.category_id,
            name=row.name,
            description=row.description,
            enabled=row.enabled,
            external_id=row.external_id,
            slug=row.slug,
            metadata=row.metadata,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )

    def _row_to_item(self, row: "ItemModel") -> Item:
        """Build the ``Item`` row from its ORM object."""
        return Item(
            item_id=row.item_id,
            name=row.name,
            external_id=row.external_id,
            slug=row.slug,
            enabled=row.enabled,
            metadata=row.metadata,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )

    def _row_to_tag(self, row: "TagModel") -> Tag:
        """Build the ``Tag`` row from its ORM object."""
        return Tag(
            tag_id=row.tag_id,
            name=row.name,
            metadata=row.metadata,
        )

    def _row_to_category_parent_link(self, row: "CategoryParentLinkModel") -> CategoryParentLink:
        """Build the parent link from its ORM object."""
        return CategoryParentLink(
            category_id=row.category_id,
            parent_category_id=row.parent_category_id,
            sort_index=row.sort_index,
        )

    def _row_to_item_parent_link(self, row: "ItemParentLinkModel") -> ItemParentLink:
        """Build the placement from its ORM object."""
        return ItemParentLink(
            item_id=row.item_id,
            category_id=row.category_id,
            sort_index=row.sort_index,
        )

    def _row_to_item_relation_link(self, row: "ItemRelationLinkModel") -> ItemRelationLink:
        """Build the relation from its ORM object."""
        return ItemRelationLink(
            source_item_id=row.source_item_id,
            target_item_id=row.target_item_id,
            relation_type=row.relation_type,
            sort_index=row.sort_index,
            metadata=row.metadata,
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @property
    def config_summary(self) -> str:
        """The engine and the database alias, as ``django:<engine>/<alias>``.

        The text never holds the ``NAME``, ``USER``, ``PASSWORD``, ``HOST`` or ``PORT`` of the
        database.

        Returns:
            Text that is not empty and holds no secret, such as ``django:sqlite3/default``.
        """
        from django.conf import settings  # noqa: PLC0415

        engine: str = settings.DATABASES[self._using]["ENGINE"].split(".")[-1]
        return f"django:{engine}/{self._using}"

    def describe(self) -> RepositoryInfo:
        """Return what this repository reports about itself.

        Returns:
            A :class:`RepositoryInfo` whose ``path`` is ``None``, since the data is in a database
            and not in a file, and whose ``diagnostics`` hold the database alias under
            ``database_alias``.
        """
        return RepositoryInfo(backend=type(self).__name__, path=None, diagnostics={"database_alias": self._using})

    # ------------------------------------------------------------------
    # Category CRUD
    # ------------------------------------------------------------------

    def save_category(self, category: Category, *, expected_version: int | None = None) -> Category:
        """Store a category row: insert it, or replace the stored row with its identifier.

        The given row does not change.

        Args:
            category: The category row to store.
            expected_version: The version the stored row must be at, or ``None`` for no
                comparison. Given, the save is one ``UPDATE`` filtered on it, and a row count of
                zero is the conflict: the comparison and the write are one statement.

        Returns:
            The row as stored, carrying the version the database assigned: ``0`` on an insert,
            and the replaced row's version plus one on an update.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored.
            TaxomeshExternalIdConflictError: If ``category.external_id`` is not ``None`` and another
                category already has it.
            TaxomeshRepositoryError: On any other database error.
        """
        from django.db import DatabaseError, IntegrityError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshExternalIdConflictError, TaxomeshRepositoryError  # noqa: PLC0415

        fields: dict[str, object] = {
            "name": category.name,
            "description": category.description,
            "enabled": category.enabled,
            "external_id": category.external_id,
            "slug": category.slug,
            "metadata": category.metadata,
            "created_at": category.created_at,
            "updated_at": category.updated_at,
        }
        try:
            with transaction.atomic(using=self._using):
                from django.db.models import F  # noqa: PLC0415

                rows = self._CategoryModel.objects.using(self._using).filter(category_id=category.category_id)
                if expected_version is not None:
                    if not rows.filter(version=expected_version).update(**fields, version=F("version") + 1):
                        raise version_conflict("category", category.category_id, expected_version)
                    version = expected_version + 1
                else:
                    row, created = self._CategoryModel.objects.using(self._using).get_or_create(
                        category_id=category.category_id, defaults={**fields, "version": 0}
                    )
                    if not created:
                        rows.update(**fields, version=F("version") + 1)
                        row.refresh_from_db(using=self._using)
                    version = row.version
        except IntegrityError as exc:
            raise TaxomeshExternalIdConflictError(
                f"External id {category.external_id!r} is already used by another category"
            ) from exc
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return category.model_copy(update={"version": version})

    def find_category(self, category_id: UUID) -> Category | None:
        """Return the category with this identifier, or ``None``.

        Args:
            category_id: The identifier of the category.

        Returns:
            The category row, or ``None`` when no category with this identifier is stored.
        """
        row = self._CategoryModel.objects.using(self._using).filter(category_id=category_id).first()
        if row is None:
            return None
        return self._row_to_category(row)

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return the stored categories, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching categories, ordered by ``(name ASC, category_id ASC)``; empty when none
            match.
        """
        qs = self._CategoryModel.objects.using(self._using)
        if enabled is not None:
            qs = qs.filter(enabled=enabled)
        return [self._row_to_category(row) for row in qs.order_by("name", "category_id")]

    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category and every link that names it, in one transaction.

        The links deleted with it are its parent links, as child and as parent, and its
        placements. ``on_delete=CASCADE`` deletes them, inside the transaction that Django opens
        for the delete.

        Args:
            category_id: The identifier of the category to delete.

        Returns:
            ``True`` if the category was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def save_item(self, item: Item, *, expected_version: int | None = None) -> Item:
        """Store an item row: insert it, or replace the stored row with its identifier.

        The given row does not change.

        Args:
            item: The item row to store.
            expected_version: The version the stored row must be at, or ``None`` for no
                comparison. Given, the save is one ``UPDATE`` filtered on it, and a row count of
                zero is the conflict: the comparison and the write are one statement.

        Returns:
            The row as stored, carrying the version the database assigned: ``0`` on an insert,
            and the replaced row's version plus one on an update.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored.
            TaxomeshExternalIdConflictError: If ``item.external_id`` is not ``None`` and another
                item already has it.
            TaxomeshRepositoryError: On any other database error.
        """
        from django.db import DatabaseError, IntegrityError, transaction  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshExternalIdConflictError, TaxomeshRepositoryError  # noqa: PLC0415

        fields: dict[str, object] = {
            "name": item.name,
            "external_id": item.external_id,
            "slug": item.slug,
            "enabled": item.enabled,
            "metadata": item.metadata,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        try:
            with transaction.atomic(using=self._using):
                from django.db.models import F  # noqa: PLC0415

                rows = self._ItemModel.objects.using(self._using).filter(item_id=item.item_id)
                if expected_version is not None:
                    if not rows.filter(version=expected_version).update(**fields, version=F("version") + 1):
                        raise version_conflict("item", item.item_id, expected_version)
                    version = expected_version + 1
                else:
                    row, created = self._ItemModel.objects.using(self._using).get_or_create(
                        item_id=item.item_id, defaults={**fields, "version": 0}
                    )
                    if not created:
                        rows.update(**fields, version=F("version") + 1)
                        row.refresh_from_db(using=self._using)
                    version = row.version
        except IntegrityError as exc:
            raise TaxomeshExternalIdConflictError(
                f"External id {item.external_id!r} is already used by another item"
            ) from exc
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return item.model_copy(update={"version": version})

    def find_item(self, item_id: UUID) -> Item | None:
        """Return the item with this identifier, or ``None``.

        Args:
            item_id: The identifier of the item.

        Returns:
            The item row, or ``None`` when no item with this identifier is stored.
        """
        row = self._ItemModel.objects.using(self._using).filter(item_id=item_id).first()
        if row is None:
            return None
        return self._row_to_item(row)

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return the stored items, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled items, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching items, ordered by ``(name ASC, item_id ASC)``; empty when none match.
        """
        qs = self._ItemModel.objects.using(self._using)
        if enabled is not None:
            qs = qs.filter(enabled=enabled)
        return [self._row_to_item(row) for row in qs.order_by("name", "item_id")]

    def delete_item(self, item_id: UUID) -> bool:
        """Delete an item and every link that names it, in one transaction.

        The links deleted with it are its placements, its tag links and its relations at either
        end. ``on_delete=CASCADE`` deletes them, inside the transaction that Django opens for the
        delete.

        Args:
            item_id: The identifier of the item to delete.

        Returns:
            ``True`` if the item was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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
        """Store a tag row: insert it, or replace the stored row with its identifier.

        Args:
            tag: The tag row to store.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def find_tag(self, tag_id: UUID) -> Tag | None:
        """Return the tag with this identifier, or ``None``.

        Args:
            tag_id: The identifier of the tag.

        Returns:
            The tag row, or ``None`` when no tag with this identifier is stored.
        """
        row = self._TagModel.objects.using(self._using).filter(tag_id=tag_id).first()
        if row is None:
            return None
        return self._row_to_tag(row)

    def list_tags(self) -> list[Tag]:
        """Return every stored tag, in no fixed order.

        Returns:
            Every tag row, in the order that the database returns them; empty when no tag is
            stored.
        """
        return [self._row_to_tag(row) for row in self._TagModel.objects.using(self._using).all()]

    def map_tags_by_id(self, tag_ids: Collection[UUID]) -> Mapping[UUID, Tag]:
        """Return the tags whose ``tag_id`` is in ``tag_ids``.

        One query, ``tag_id__in``, does the lookup: the repository does not read every tag and
        filter them in Python.

        Args:
            tag_ids: The identifiers of the tags to look up.

        Returns:
            A dict from the identifier of each stored tag to its row. An identifier that names no
            stored tag is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._TagModel.objects.using(self._using).filter(tag_id__in=tag_ids)
            return {row.tag_id: self._row_to_tag(row) for row in qs}
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete a tag and every link that names it, in one transaction.

        The links deleted with it are its tag links. ``on_delete=CASCADE`` deletes them, inside
        the transaction that Django opens for the delete.

        Args:
            tag_id: The identifier of the tag to delete.

        Returns:
            ``True`` if the tag was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def add_item_tag_link(self, item_id: UUID, tag_id: UUID) -> None:
        """Store a tag link: the tag on the item. Nothing changes when the link is already stored.

        The link table holds one link for each ``(item_id, tag_id)``.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def delete_item_tag_link(self, item_id: UUID, tag_id: UUID) -> bool:
        """Delete the tag link of this tag on this item.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Returns:
            ``True`` if the link was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def list_item_tag_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        tag_ids: Collection[UUID] | None = None,
    ) -> list[ItemTagLink]:
        """Return the stored tag links, filtered by either end when a filter is given.

        The filters are part of the database query: the repository does not read every link and
        filter them in Python.

        Args:
            item_ids: When given, only the links whose ``item_id`` is in it. An empty collection
                returns ``[]``: it is not "no filter".
            tag_ids: When given, only the links whose ``tag_id`` is in it. An empty collection
                returns ``[]``: it is not "no filter". When both filters are given, a link must
                match both.

        Returns:
            The matching tag links, ordered by ``(item_id ASC, tag_id ASC)``.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._ItemTagLinkModel.objects.using(self._using)
            if item_ids is not None:
                qs = qs.filter(item_id__in=item_ids)
            if tag_ids is not None:
                qs = qs.filter(tag_id__in=tag_ids)
            rows = qs.order_by("item_id", "tag_id").values_list("item_id", "tag_id")
            return [ItemTagLink(item_id=item_id, tag_id=tag_id) for item_id, tag_id in rows]
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Category parent links
    # ------------------------------------------------------------------

    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Store a parent link: insert it, or update the stored one.

        When a link with the same ``(category_id, parent_category_id)`` is stored, its
        ``sort_index`` is updated. No second link is created.

        Args:
            link: The parent link to store.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        """Return the stored parent links, filtered by either end when a filter is given.

        Both filters are part of the database query, as ``category_id__in`` and
        ``parent_category_id__in``: the repository does not read every link and filter them in
        Python.

        Args:
            category_ids: When given, only the links whose ``category_id`` is in it. An empty
                collection returns ``[]``: it is not "no filter". ``None`` (the default) applies no
                child filter.
            parent_category_ids: When given, only the links whose ``parent_category_id`` is in it.
                An empty collection returns ``[]``: it is not "no filter". ``None`` (the default)
                applies no parent filter. When both filters are given, a link must match both.

        Returns:
            The matching parent links, ordered by ``(parent_category_id ASC, sort_index ASC,
            category_id ASC)``.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._CategoryParentLinkModel.objects.using(self._using)
            if category_ids is not None:
                qs = qs.filter(category_id__in=category_ids)
            if parent_category_ids is not None:
                qs = qs.filter(parent_category_id__in=parent_category_ids)
            return [
                self._row_to_category_parent_link(row)
                for row in qs.order_by("parent_category_id", "sort_index", "category_id")
            ]
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Item parent links
    # ------------------------------------------------------------------

    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Store a placement: insert it, or update the stored one.

        When a placement with the same ``(item_id, category_id)`` is stored, its ``sort_index`` is
        updated. No second placement is created.

        Args:
            link: The placement to store.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def list_item_parent_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        """Return the stored placements, filtered by either end when a filter is given.

        The filters are part of the database query: the repository does not read every placement
        and filter them in Python.

        Args:
            item_ids: When given, only the placements whose ``item_id`` is in it.
            category_ids: When given, only the placements whose ``category_id`` is in it. An empty
                collection in either filter returns ``[]``: it is not "no filter". When both
                filters are given, a placement must match both.

        Returns:
            The matching placements, ordered by ``(category_id ASC, sort_index ASC, item_id ASC)``.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._ItemParentLinkModel.objects.using(self._using)
            if item_ids is not None:
                qs = qs.filter(item_id__in=item_ids)
            if category_ids is not None:
                qs = qs.filter(category_id__in=category_ids)
            return [self._row_to_item_parent_link(row) for row in qs.order_by("category_id", "sort_index", "item_id")]
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Link deletion
    # ------------------------------------------------------------------

    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete the parent link of this category under this parent.

        Args:
            category_id: The identifier of the child category.
            parent_category_id: The identifier of the parent category.

        Returns:
            ``True`` if the link was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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
        """Delete the placement of this item in this category.

        Args:
            item_id: The identifier of the item.
            category_id: The identifier of the category.

        Returns:
            ``True`` if the placement was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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

    def find_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with this external id, or ``None``.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The item row, or ``None`` when no item has this external id.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            row = self._ItemModel.objects.using(self._using).filter(external_id=external_id).first()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return self._row_to_item(row) if row is not None else None

    def find_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with this external id, or ``None``.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The category row, or ``None`` when no category has this external id. The repository
            does not leave out the implicit root: the caller does.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            row = self._CategoryModel.objects.using(self._using).filter(external_id=external_id).first()
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return self._row_to_category(row) if row is not None else None

    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, "Item"]:
        """Return the items whose ``item_id`` is in ``item_ids``.

        One query, ``item_id__in``, does the lookup: the repository does not read every item and
        filter them in Python.

        Args:
            item_ids: The identifiers of the items to look up, with no duplicates.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A dict from the identifier of each stored item to its row. An identifier that names no
            stored item is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._ItemModel.objects.using(self._using).filter(item_id__in=item_ids)
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return {row.item_id: self._row_to_item(row) for row in qs}
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, "Category"]:
        """Return the categories whose ``category_id`` is in ``category_ids``.

        One query, ``category_id__in``, does the lookup: the repository does not read every
        category and filter them in Python, and does not split the identifiers into several
        queries.

        Args:
            category_ids: The identifiers of the categories to look up, with no duplicates.
            enabled: ``True`` returns only the enabled categories, ``False`` only the disabled
                ones, and ``None`` (the default) every matching category.

        Returns:
            A dict from the identifier of each stored category to its row. An identifier that
            names no stored category is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._CategoryModel.objects.using(self._using).filter(category_id__in=category_ids)
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return {row.category_id: self._row_to_category(row) for row in qs}
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def map_items_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, "Item"]:
        """Return the items whose ``external_id`` is in ``external_ids``.

        Args:
            external_ids: The external ids to look up, in stored form, with no duplicates.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A dict from the external id of each stored item to its row. An external id that no
            stored item has is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._ItemModel.objects.using(self._using).filter(external_id__in=external_ids)
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return {row.external_id: self._row_to_item(row) for row in qs if row.external_id is not None}
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def map_categories_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, "Category"]:
        """Return the categories whose ``external_id`` is in ``external_ids``.

        The service leaves out the implicit root, and the repository does not: the repository
        returns the implicit root too when its external id matches.

        Args:
            external_ids: The external ids to look up, in stored form, with no duplicates.
            enabled: ``True`` returns only the enabled categories, ``False`` only the disabled
                ones, and ``None`` (the default) every matching category.

        Returns:
            A dict from the external id of each stored category to its row. An external id that
            no stored category has is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            qs = self._CategoryModel.objects.using(self._using).filter(external_id__in=external_ids)
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return {row.external_id: self._row_to_category(row) for row in qs if row.external_id is not None}
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc

    def find_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The item row, or ``None`` when no item has this slug.
        """
        row = self._ItemModel.objects.using(self._using).filter(slug=slug).first()
        return self._row_to_item(row) if row is not None else None

    def find_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The category row, or ``None`` when no category has this slug.
        """
        row = self._CategoryModel.objects.using(self._using).filter(slug=slug).first()
        return self._row_to_category(row) if row is not None else None

    # ------------------------------------------------------------------
    # Item relation links
    # ------------------------------------------------------------------

    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Store a relation: insert it, or update the stored one.

        When a relation with the same ``(source_item_id, target_item_id, relation_type)`` is
        stored, its ``sort_index`` and ``metadata`` are updated. No second relation is created.

        Args:
            link: The relation to store.

        Raises:
            TaxomeshRepositoryError: On a database error.
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
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return the relations of one item, ordered by sort index.

        Args:
            item_id: The identifier of the item.
            relation_types: The relation types to keep, already stripped and in lowercase.
                ``None`` or an empty collection is no filter.
            direction: ``"outgoing"`` returns the relations whose ``source_item_id`` is
                ``item_id``; ``"incoming"`` those whose ``target_item_id`` is ``item_id``;
                ``"both"`` those whose source or target is ``item_id``, in one ``OR`` query, each
                relation at most once.

        Returns:
            The matching relations, ordered by ``(sort_index ASC, source_item_id ASC,
            target_item_id ASC)``; empty when none match.
        """
        from django.db import DatabaseError  # noqa: PLC0415
        from django.db.models import Q  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            base = self._ItemRelationLinkModel.objects.using(self._using)
            if direction == "outgoing":
                qs = base.filter(source_item_id=item_id)
            elif direction == "incoming":
                qs = base.filter(target_item_id=item_id)
            else:  # "both"
                qs = base.filter(Q(source_item_id=item_id) | Q(target_item_id=item_id))
            if relation_types:
                qs = qs.filter(relation_type__in=list(relation_types))
            qs = qs.order_by("sort_index", "source_item_id", "target_item_id")
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return [self._row_to_item_relation_link(row) for row in qs]

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return the relations of many items in one ORM query, by direction.

        ``"both"`` is one ``source OR target`` query, ``Q(...) | Q(...)``, and not two, so every
        direction reads the relations in one query.
        """
        from django.db import DatabaseError  # noqa: PLC0415
        from django.db.models import Q  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        id_list = list(item_ids)
        if not id_list:
            return []
        try:
            qs = self._ItemRelationLinkModel.objects.using(self._using)
            if direction == "outgoing":
                qs = qs.filter(source_item_id__in=id_list).order_by(
                    "source_item_id", "relation_type", "sort_index", "target_item_id"
                )
            elif direction == "incoming":
                qs = qs.filter(target_item_id__in=id_list).order_by(
                    "target_item_id", "relation_type", "sort_index", "source_item_id"
                )
            else:
                qs = qs.filter(Q(source_item_id__in=id_list) | Q(target_item_id__in=id_list)).order_by(
                    "sort_index", "source_item_id", "target_item_id"
                )
            if relation_types:
                qs = qs.filter(relation_type__in=list(relation_types))
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
        return [self._row_to_item_relation_link(row) for row in qs]

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
            ``True`` if the relation was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: On a database error.
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
    # Members for Django only, outside the port
    # ------------------------------------------------------------------

    def assignable_categories_qs(self) -> "QuerySet[CategoryModel]":
        """Return a queryset of the enabled categories, without the implicit root, for the admin.

        The port does not have this member: it is for the Django ORM only, so a caller that needs
        it imports ``DjangoRepository``. The admin uses it for the category choices of its list
        filter and its ``categories`` field.

        The queryset keeps the rows with ``enabled=True``, and leaves out the category named
        ``__root__``, the implicit root.

        Returns:
            A lazy ``QuerySet[CategoryModel]`` that the caller can filter and order further.
            Building it reads nothing. When the caller evaluates it, a database error is raised as
            Django's ``DatabaseError``.
        """
        from django.db import DatabaseError  # noqa: PLC0415

        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        try:
            return self._CategoryModel.objects.using(self._using).filter(enabled=True).exclude(name=ROOT_CATEGORY_NAME)
        except DatabaseError as exc:
            raise TaxomeshRepositoryError(str(exc)) from exc
