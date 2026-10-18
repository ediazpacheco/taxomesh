"""DjangoRepository — taxomesh storage adapter backed by the Django ORM.

Every Django import is inside ``__init__`` or a method body, so that this module, and
``import taxomesh``, work when Django is not installed.
Every deferred import line carries ``# noqa: PLC0415``. The names that only the annotations use, such
as ``QuerySet``, are imported at module level for the type checker only, under ``TYPE_CHECKING``.

Usage::

    from taxomesh import TaxomeshService
    from taxomesh.adapters.repositories.django_repository import DjangoRepository

    svc = TaxomeshService(repository=DjangoRepository())
"""

from collections.abc import Callable, Collection, Iterator, Mapping
from contextlib import contextmanager
from itertools import batched, product
from operator import attrgetter
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID

from taxomesh.adapters.repositories._relation_types import require_relation_types
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
    ModelBase,
    Tag,
)
from taxomesh.exceptions import (
    TaxomeshDuplicateSlugError,
    TaxomeshError,
    TaxomeshExternalIdConflictError,
    TaxomeshRepositoryError,
)

if TYPE_CHECKING:
    from django.db.models import Manager, Model, QuerySet

    from taxomesh.contrib.django.models import CategoryModel, ItemModel

# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

DEFAULT_DJANGO_USING: Final[str] = "default"
DJANGO_REPO_TYPE: Final[str] = "django"


def django_import_error(exc: ImportError) -> TaxomeshRepositoryError:
    """Return the error for an ``ImportError`` that setting up Django raised: Django, or its settings module.

    ``exc.name`` is ``django`` or one of its submodules when Django is not installed. Any other name
    is a module that the settings need, the settings module itself first.
    """
    if exc.name is None or exc.name == "django" or exc.name.startswith("django."):
        return TaxomeshRepositoryError("Django is not installed. Run: pip install 'taxomesh[django]'")
    return TaxomeshRepositoryError(
        f"Django could not import the module {exc.name!r}: check that DJANGO_SETTINGS_MODULE names a module "
        "on the Python path, and that the module imports"
    )


@contextmanager
def _storage_errors() -> Iterator[None]:
    """Raise a database error from the block as a ``TaxomeshRepositoryError`` with the error as its cause.

    Django is imported when the block fails, so that this module works without it.
    """
    try:
        yield
    except Exception as exc:
        from django.db import DatabaseError  # noqa: PLC0415

        if isinstance(exc, DatabaseError):
            raise TaxomeshRepositoryError(str(exc)) from exc
        raise


def _unique_key_failure(
    others: "QuerySet[CategoryModel] | QuerySet[ItemModel]",
    kind: str,
    slug: str,
    external_id: str | None,
    exc: Exception,
) -> TaxomeshError:
    """Return the error for a save that a unique column refused: the error of the key another row holds.

    The database names the refused column in its own words, which differ from one engine to the
    next, so the rows are asked instead: the slug first, then the external id. When another row
    holds neither, the refusal is a storage failure.

    Args:
        others: The stored rows of the kind, the saved row left out.
        kind: The noun the messages use, ``"category"`` or ``"item"``.
        slug: The slug of the saved row; ``""`` is no slug.
        external_id: The external id of the saved row, or ``None``.
        exc: The ``IntegrityError`` that the database raised.
    """
    if slug and others.filter(slug=slug).exists():
        return TaxomeshDuplicateSlugError(f"Slug '{slug}' is already used by another {kind}")
    if external_id is not None and others.filter(external_id=external_id).exists():
        return TaxomeshExternalIdConflictError(f"External id {external_id!r} is already used by another {kind}")
    return TaxomeshRepositoryError(str(exc))


def _row[R: ModelBase](row_type: type[R], orm_row: "Model") -> R:
    """Return the ``row_type`` row that ``orm_row`` holds: each field is read from the attribute of its name."""
    return row_type.model_validate(orm_row, from_attributes=True)


class DjangoRepository:
    """The storage adapter that stores taxomesh data through the Django ORM.

    It has the members of ``TaxomeshRepositoryBase``, and it does not inherit from the port.

    Args:
        using: The Django database alias. The default is ``"default"``.

    Raises:
        TaxomeshRepositoryError: If Django is not installed, with a message that names
            ``pip install 'taxomesh[django]'``, or if the settings of Django are not configured.
        TypeError: If ``using`` is not a ``str``.
    """

    def __init__(self, using: str = DEFAULT_DJANGO_USING) -> None:
        """Check that Django is installed and configured, and bind the manager of each ORM model to ``using``.

        Args:
            using: The Django database alias. The default is ``"default"``.

        Raises:
            TaxomeshRepositoryError: If Django cannot be imported, or if its settings are not
                configured.
            TypeError: If ``using`` is not a ``str``. Django reads ``None`` as ``"default"``, so it is
                refused before Django is imported.
        """
        if not isinstance(using, str):
            raise TypeError(f"using must be a str, not {type(using).__name__}")
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
            raise django_import_error(exc) from exc
        except Exception as exc:
            from django.core.exceptions import ImproperlyConfigured  # noqa: PLC0415

            if isinstance(exc, ImproperlyConfigured):
                raise TaxomeshRepositoryError(
                    "Django settings are not configured: set the DJANGO_SETTINGS_MODULE environment "
                    "variable before running taxomesh with type = 'django'"
                ) from exc
            raise

        self._using = using
        # The manager of each ORM model on the database alias, so that no member imports the models again
        self._categories = CategoryModel.objects.db_manager(using)
        self._items = ItemModel.objects.db_manager(using)
        self._tags = TagModel.objects.db_manager(using)
        self._parent_links = CategoryParentLinkModel.objects.db_manager(using)
        self._placements = ItemParentLinkModel.objects.db_manager(using)
        self._tag_links = ItemTagLinkModel.objects.db_manager(using)
        self._relations = ItemRelationLinkModel.objects.db_manager(using)

    def __repr__(self) -> str:
        """Render as the constructor call that opens the same database alias."""
        return f"{type(self).__name__}(using={self._using!r})"

    # ------------------------------------------------------------------
    # Atomicity boundary
    # ------------------------------------------------------------------

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Run the block in one database transaction that starts with a lock, and rolls back on a failure.

        The block is ``django.db.transaction.atomic`` on this repository's database. Its first
        statement is an ``UPDATE`` of the implicit root's row that changes nothing. The statement
        takes a lock that the transaction holds until it ends: the row's lock on PostgreSQL and
        MySQL, and the write lock of the database on SQLite, where ``select_for_update()`` takes no
        lock. So a block that another thread or another worker opens on the same database waits at
        its first statement until this block ends, and then reads what this block stored. On SQLite,
        a block that waits longer than the connection's timeout, 5 seconds by default, raises.
        Migration ``0012`` stores the implicit root, and the service stores it when it is built if
        it is absent, so the row is there.

        When a collection runs one member inside the block and the body raises, the whole
        transaction rolls back, and no write of the block is committed.

        Django's ``atomic()`` blocks nest. The outermost block opens the database transaction, and
        the ``transaction.atomic`` block that a write of this repository opens, such as
        ``save_category``, is a **savepoint** inside it. An exception that leaves the block rolls
        back every savepoint and the transaction, so the data is as it was before the block. A
        block inside a transaction that the caller opened takes the lock too, and holds it until
        the caller's transaction ends.

        Raises:
            TaxomeshRepositoryError: If the database fails while the block opens its transaction,
                takes the lock or commits. An exception that the body raises, a database error of
                the caller's own query included, leaves the block as it is.
        """
        from django.db import DatabaseError, transaction  # noqa: PLC0415

        body_raised = False
        try:
            with transaction.atomic(using=self._using):
                self._categories.filter(name=ROOT_CATEGORY_NAME).update(name=ROOT_CATEGORY_NAME)
                try:
                    yield
                except BaseException:
                    body_raised = True
                    raise
        except DatabaseError as exc:
            if body_raised:
                raise
            raise TaxomeshRepositoryError(str(exc)) from exc

    @property
    def in_transaction(self) -> bool:
        """Whether a transaction of this repository's database is open on the calling thread.

        ``True`` inside an ``atomic`` block of the database alias, the caller's or this
        repository's own, and while the open connection's autocommit is off. Django keeps one
        connection for each thread, so another thread's transaction is not this thread's. Reading
        it opens no connection.
        """
        from django.db import connections  # noqa: PLC0415

        connection = connections[self._using]
        return connection.in_atomic_block or (connection.connection is not None and not connection.get_autocommit())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _first[R: ModelBase](self, row_type: type[R], objects: "Manager[Model]", **lookup: object) -> R | None:
        """Return the first stored row that ``lookup`` matches, as a ``row_type`` row, or ``None``."""
        with _storage_errors():
            orm_row = objects.filter(**lookup).first()
        return None if orm_row is None else _row(row_type, orm_row)

    def _delete(self, objects: "Manager[Model]", **lookup: object) -> bool:
        """Delete the stored rows that ``lookup`` matches, and return whether one was stored."""
        with _storage_errors():
            deleted, _ = objects.filter(**lookup).delete()
        return int(deleted) > 0

    def _matching[M: Model](
        self, objects: "Manager[M]", lookup: str, values: Collection[object], enabled: bool | None = None
    ) -> list[M]:
        """Return the stored rows that the lookup ``lookup``, such as ``item_id__in``, matches in ``values``.

        When ``enabled`` is not ``None``, only the rows with that ``enabled`` value are returned. The
        values are read in as many queries as the database's limit on parameters needs.
        """
        with _storage_errors():
            rows = objects.all()
            if enabled is not None:
                rows = rows.filter(enabled=enabled)
            return [
                row
                for lookups in self._batches({lookup: values}, fixed=int(enabled is not None))
                for row in rows.filter(**lookups)
            ]

    def _save_versioned[R: (Category, Item)](
        self,
        objects: "Manager[CategoryModel] | Manager[ItemModel]",
        kind: str,
        row: R,
        row_id: UUID,
        expected_version: int | None,
    ) -> R:
        """Store a category row or an item row, as ``save_category`` and ``save_item`` describe.

        Args:
            objects: The manager of the row's ORM model.
            kind: The noun of the messages, ``"category"`` or ``"item"``.
            row: The row to store.
            row_id: The identifier of the row.
            expected_version: The version the stored row must be at, or ``None`` for no comparison.

        Returns:
            The row, with the version that the database assigned.
        """
        from django.db import IntegrityError, transaction  # noqa: PLC0415
        from django.db.models import F  # noqa: PLC0415

        # Every column but the primary key, which the lookups name, and the version, which the database assigns
        fields = row.model_dump(exclude={objects.model._meta.pk.name, "version"})
        with _storage_errors():
            try:
                with transaction.atomic(using=self._using):
                    rows = objects.filter(pk=row_id)
                    if expected_version is not None:
                        if not rows.filter(version=expected_version).update(**fields, version=F("version") + 1):
                            raise version_conflict(kind, row_id, expected_version)
                        version = expected_version + 1
                    else:
                        stored, created = objects.get_or_create(pk=row_id, defaults={**fields, "version": 0})
                        if not created:
                            rows.update(**fields, version=F("version") + 1)
                            stored.refresh_from_db(using=self._using)
                        version = stored.version
            except IntegrityError as exc:
                raise _unique_key_failure(objects.exclude(pk=row_id), kind, row.slug, row.external_id, exc) from exc
        return row.model_copy(update={"version": version})

    def _batches(
        self, lists: Mapping[str, Collection[object] | None], *, fixed: int = 0, uses: int = 1
    ) -> list[dict[str, list[object]]]:
        """Cut the values that one read filters by into the parts of its queries, so no query passes the limit.

        A database accepts a limited number of parameters in one query: ``max_query_params`` on the
        connection's features, by default 32,766 on SQLite, and ``None``, no limit, on PostgreSQL.
        A value given twice is kept once, in its first place, so the parts return each row once, as
        one query does. When the values fit, or the engine sets no limit, the read is one query, as
        it would be without this method. Past the limit, each list is cut, in its order, into parts of at most
        ``(limit - fixed) // (uses * number of lists)`` values, and one query reads each combination
        of parts: a row that matches every list matches one combination.

        Args:
            lists: Each list of values, by the key the caller reads it under: a lookup such as
                ``item_id__in`` goes to ``filter()`` as it is. ``None`` is no filter, and its key is
                left out.
            fixed: The number of the query's other parameters.
            uses: How many times the query passes each list: 2 for ``source OR target``.

        Returns:
            The values of each query, by key: one mapping when one query reads them all, and none
            when a list is empty past the limit, since no row matches an empty list.
        """
        from django.db import connections  # noqa: PLC0415

        given = {key: list(dict.fromkeys(values)) for key, values in lists.items() if values is not None}
        limit = connections[self._using].features.max_query_params
        if not given or limit is None or fixed + uses * sum(len(values) for values in given.values()) <= limit:
            return [given]
        size = max(1, (limit - fixed) // (uses * len(given)))
        return [
            {key: list(part) for key, part in zip(given, parts, strict=True)}
            for parts in product(*(batched(values, size, strict=False) for values in given.values()))
        ]

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
            TaxomeshDuplicateSlugError: If ``category.slug`` is not empty and another category already
                has it.
            TaxomeshExternalIdConflictError: If ``category.external_id`` is not ``None`` and another
                category already has it.
            TaxomeshRepositoryError: On any other database error.
        """
        return self._save_versioned(self._categories, "category", category, category.category_id, expected_version)

    def find_category(self, category_id: UUID) -> Category | None:
        """Return the category with this identifier, or ``None``.

        Args:
            category_id: The identifier of the category.

        Returns:
            The category row, or ``None`` when no category with this identifier is stored.
        """
        return self._first(Category, self._categories, category_id=category_id)

    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return the stored categories, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching categories, ordered by ``(name ASC, category_id ASC)``; empty when none
            match.
        """
        with _storage_errors():
            qs = self._categories.all()
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return [_row(Category, row) for row in qs.order_by("name", "category_id")]

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
        return self._delete(self._categories, category_id=category_id)

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
            TaxomeshDuplicateSlugError: If ``item.slug`` is not empty and another item already
                has it.
            TaxomeshExternalIdConflictError: If ``item.external_id`` is not ``None`` and another
                item already has it.
            TaxomeshRepositoryError: On any other database error.
        """
        return self._save_versioned(self._items, "item", item, item.item_id, expected_version)

    def find_item(self, item_id: UUID) -> Item | None:
        """Return the item with this identifier, or ``None``.

        Args:
            item_id: The identifier of the item.

        Returns:
            The item row, or ``None`` when no item with this identifier is stored.
        """
        return self._first(Item, self._items, item_id=item_id)

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return the stored items, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled items, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching items, ordered by ``(name ASC, item_id ASC)``; empty when none match.
        """
        with _storage_errors():
            qs = self._items.all()
            if enabled is not None:
                qs = qs.filter(enabled=enabled)
            return [_row(Item, row) for row in qs.order_by("name", "item_id")]

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
        return self._delete(self._items, item_id=item_id)

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
        with _storage_errors():
            self._tags.update_or_create(
                tag_id=tag.tag_id,
                defaults={
                    "name": tag.name,
                    "metadata": tag.metadata,
                },
            )

    def find_tag(self, tag_id: UUID) -> Tag | None:
        """Return the tag with this identifier, or ``None``.

        Args:
            tag_id: The identifier of the tag.

        Returns:
            The tag row, or ``None`` when no tag with this identifier is stored.
        """
        return self._first(Tag, self._tags, tag_id=tag_id)

    def list_tags(self) -> list[Tag]:
        """Return every stored tag, in no fixed order.

        Returns:
            Every tag row, in the order that the database returns them; empty when no tag is
            stored.
        """
        with _storage_errors():
            return [_row(Tag, row) for row in self._tags.all()]

    def map_tags_by_id(self, tag_ids: Collection[UUID]) -> Mapping[UUID, Tag]:
        """Return the tags whose ``tag_id`` is in ``tag_ids``.

        A ``tag_id__in`` query does the lookup, one for each part of ``tag_ids`` that the database
        accepts in one query: the repository does not read every tag and filter them in Python.

        Args:
            tag_ids: The identifiers of the tags to look up.

        Returns:
            A dict from the identifier of each stored tag to its row. An identifier that names no
            stored tag is left out of the dict, and no error is raised.

        Raises:
            TaxomeshRepositoryError: On a database error.
        """
        return {row.tag_id: _row(Tag, row) for row in self._matching(self._tags, "tag_id__in", tag_ids)}

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
        return self._delete(self._tags, tag_id=tag_id)

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
        with _storage_errors():
            self._tag_links.get_or_create(
                tag_id=tag_id,
                item_id=item_id,
            )

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
        return self._delete(self._tag_links, tag_id=tag_id, item_id=item_id)

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
        with _storage_errors():
            qs = self._tag_links.order_by("item_id", "tag_id")
            batches = self._batches({"item_id__in": item_ids, "tag_id__in": tag_ids})
            rows = [row for lookups in batches for row in qs.filter(**lookups).values_list("item_id", "tag_id")]
        if len(batches) > 1:
            rows.sort()
        return [ItemTagLink(item_id=item_id, tag_id=tag_id) for item_id, tag_id in rows]

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
        with _storage_errors():
            self._parent_links.update_or_create(
                category_id=link.category_id,
                parent_category_id=link.parent_category_id,
                defaults={"sort_index": link.sort_index},
            )

    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        """Return the stored parent links, filtered by either end when a filter is given.

        Both filters are part of the database query, as ``category_id__in`` and
        ``parent_category_id__in``, in as many queries as the database's limit on parameters needs:
        the repository does not read every link and filter them in Python.

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
        order = ("parent_category_id", "sort_index", "category_id")
        with _storage_errors():
            qs = self._parent_links.order_by(*order)
            batches = self._batches({"category_id__in": category_ids, "parent_category_id__in": parent_category_ids})
            links = [_row(CategoryParentLink, row) for lookups in batches for row in qs.filter(**lookups)]
        if len(batches) > 1:
            links.sort(key=attrgetter(*order))
        return links

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
        with _storage_errors():
            self._placements.update_or_create(
                item_id=link.item_id,
                category_id=link.category_id,
                defaults={"sort_index": link.sort_index},
            )

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
        order = ("category_id", "sort_index", "item_id")
        with _storage_errors():
            qs = self._placements.order_by(*order)
            batches = self._batches({"item_id__in": item_ids, "category_id__in": category_ids})
            links = [_row(ItemParentLink, row) for lookups in batches for row in qs.filter(**lookups)]
        if len(batches) > 1:
            links.sort(key=attrgetter(*order))
        return links

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
        return self._delete(self._parent_links, category_id=category_id, parent_category_id=parent_category_id)

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
        return self._delete(self._placements, item_id=item_id, category_id=category_id)

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
        return self._first(Item, self._items, external_id=external_id)

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
        return self._first(Category, self._categories, external_id=external_id)

    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, "Item"]:
        """Return the items whose ``item_id`` is in ``item_ids``.

        An ``item_id__in`` query does the lookup, one for each part of ``item_ids`` that the database
        accepts in one query: the repository does not read every item and filter them in Python.

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
        rows = self._matching(self._items, "item_id__in", item_ids, enabled)
        return {row.item_id: _row(Item, row) for row in rows}

    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, "Category"]:
        """Return the categories whose ``category_id`` is in ``category_ids``.

        A ``category_id__in`` query does the lookup, one for each part of ``category_ids`` that the
        database accepts in one query: the repository does not read every category and filter them
        in Python.

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
        rows = self._matching(self._categories, "category_id__in", category_ids, enabled)
        return {row.category_id: _row(Category, row) for row in rows}

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
        rows = self._matching(self._items, "external_id__in", external_ids, enabled)
        return {row.external_id: _row(Item, row) for row in rows if row.external_id is not None}

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
        rows = self._matching(self._categories, "external_id__in", external_ids, enabled)
        return {row.external_id: _row(Category, row) for row in rows if row.external_id is not None}

    def find_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The item row, or ``None`` when no item has this slug.
        """
        return self._first(Item, self._items, slug=slug)

    def find_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The category row, or ``None`` when no category has this slug.
        """
        return self._first(Category, self._categories, slug=slug)

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
        with _storage_errors():
            self._relations.update_or_create(
                source_item_id=link.source_item_id,
                target_item_id=link.target_item_id,
                relation_type=link.relation_type,
                defaults={"sort_index": link.sort_index, "metadata": link.metadata},
            )

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
        from django.db.models import Q  # noqa: PLC0415

        require_relation_types(relation_types)
        with _storage_errors():
            if direction == "outgoing":
                qs = self._relations.filter(source_item_id=item_id)
            elif direction == "incoming":
                qs = self._relations.filter(target_item_id=item_id)
            else:  # "both"
                qs = self._relations.filter(Q(source_item_id=item_id) | Q(target_item_id=item_id))
            if relation_types:
                qs = qs.filter(relation_type__in=list(relation_types))
            qs = qs.order_by("sort_index", "source_item_id", "target_item_id")
            return [_row(ItemRelationLink, row) for row in qs]

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return the relations of many items in one ORM query, by direction.

        ``"both"`` is one ``source OR target`` query, ``Q(...) | Q(...)``, and not two, so every
        direction reads the relations in one query, or in one for each part of ``item_ids`` that
        the database accepts in one query. The relation types are not cut: a caller passes a few.
        """
        from django.db.models import Q  # noqa: PLC0415

        require_relation_types(relation_types)
        id_list = list(item_ids)
        if not id_list:
            return []
        types = list(relation_types or ())
        queries: dict[str, tuple[tuple[str, ...], Callable[[list[object]], Q]]] = {
            "outgoing": (
                ("source_item_id", "relation_type", "sort_index", "target_item_id"),
                lambda ids: Q(source_item_id__in=ids),
            ),
            "incoming": (
                ("target_item_id", "relation_type", "sort_index", "source_item_id"),
                lambda ids: Q(target_item_id__in=ids),
            ),
            "both": (
                ("sort_index", "source_item_id", "target_item_id"),
                lambda ids: Q(source_item_id__in=ids) | Q(target_item_id__in=ids),
            ),
        }
        order, matching = queries[direction]
        with _storage_errors():
            qs = self._relations.order_by(*order)
            if types:
                qs = qs.filter(relation_type__in=types)
            batches = self._batches({"ids": id_list}, fixed=len(types), uses=2 if direction == "both" else 1)
            links = [_row(ItemRelationLink, row) for part in batches for row in qs.filter(matching(part["ids"]))]
        if len(batches) > 1:
            # The parts are read apart, and "both" reads a relation between two parts in each of them.
            unique = {(link.source_item_id, link.target_item_id, link.relation_type): link for link in links}
            links = sorted(unique.values(), key=attrgetter(*order))
        return links

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
        return self._delete(
            self._relations, source_item_id=source_item_id, target_item_id=target_item_id, relation_type=relation_type
        )

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
        return self._categories.filter(enabled=True).exclude(name=ROOT_CATEGORY_NAME)
