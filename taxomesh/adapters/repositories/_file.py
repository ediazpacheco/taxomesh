"""The file repository: the whole store in one file, read once and written whole on every write.

``JsonRepository`` and ``YamlRepository`` are this one store with two formats. Each says only how
its file's text becomes data and back; :class:`FileRepositoryBase` holds the rest of the port.
Writes are atomic: a sibling temporary file is flushed with ``os.fsync`` and then renamed into place
with ``os.replace``, so the file is never in a partial state.
"""

import functools
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from stat import S_ISDIR
from typing import Concatenate, Final, Literal, NamedTuple
from uuid import UUID

from taxomesh.adapters.repositories._external_id import bulk_lookup_by_external_id, check_external_id_unique
from taxomesh.adapters.repositories._root_links import normalise_root_links
from taxomesh.adapters.repositories._version import row_to_store
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
from taxomesh.exceptions import TaxomeshRepositoryError

# The encoding of every storage file.
ENCODING: Final[str] = "utf-8"

# The suffix of the temporary file a write fills before renaming it into place.
TEMP_SUFFIX: Final[str] = ".tmp"

# What identifies one version of the file: its inode, its modification time and its size. A write
# renames a new file into place, so any write by anyone changes the inode.
type FileStamp = tuple[int, int, int]


def _stamp_of(status: os.stat_result) -> FileStamp:
    """Return the stamp of the file ``status`` describes."""
    return status.st_ino, status.st_mtime_ns, status.st_size


def _reading[S: FileRepositoryBase, **P, R](method: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R]:
    """Run a read whole while holding the store's lock, so no thread changes memory under it."""

    @functools.wraps(method)
    def locked(self: S, /, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._lock:
            return method(self, *args, **kwargs)

    return locked


def _writing[S: FileRepositoryBase, **P, R](method: Callable[Concatenate[S, P], R]) -> Callable[Concatenate[S, P], R]:
    """Run a write whole while holding the store's lock, so its checks and its write are one step.

    The write is refused before it starts when another writer changed the file. When it fails,
    memory gets back a copy of what it held before, which is what the file still holds, so a later
    write does not write the failed change to disk.
    """

    @functools.wraps(method)
    def locked(self: S, /, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._lock:
            self._require_unchanged()
            before = self._contents()
            try:
                return method(self, *args, **kwargs)
            except Exception:
                self._put(before)
                raise

    return locked


class _Contents(NamedTuple):
    """What a file store holds in memory: its rows and its links, as the file holds them."""

    categories: dict[UUID, Category]
    items: dict[UUID, Item]
    tags: dict[UUID, Tag]
    item_tag_links: list[ItemTagLink]
    category_parent_links: list[CategoryParentLink]
    item_parent_links: list[ItemParentLink]
    item_relation_links: list[ItemRelationLink]


class FileRepositoryBase(ABC):
    """The repository port over one file that holds the whole store.

    The file is read once, at construction. Every read answers from memory, and every write
    changes memory and then writes the whole store back to the file. A subclass names the format:
    :meth:`_parse` turns the file's text into a document, and :meth:`_render` turns a document
    into text.

    One repository may be shared by threads. Each member runs whole, holding the repository's
    lock, before another thread's member starts.

    A file has one writer. A repository records the file it read, and refuses to write once
    another writer has changed it; a new repository reads the change. The check runs before each
    write, so a write by another process that overlaps this one can still be lost.

    Args:
        path: The path of the storage file. The repository creates the parent directories that are
            missing.

    Raises:
        TaxomeshRepositoryError: If ``path`` is a directory, if the file exists but cannot be read
            or parsed, or if a new file cannot be written.
    """

    def __init__(self, path: Path | str) -> None:
        """Open the store at ``path``, and create the file and its directories when they are not there.

        Args:
            path: The path of the storage file.

        Raises:
            TaxomeshRepositoryError: If the path is a directory, if the file exists but cannot be
                read or parsed, or if a new file cannot be written.
        """
        self._path = Path(path)
        self._lock = threading.RLock()
        self._stamp: FileStamp | None = None
        self._categories: dict[UUID, Category] = {}
        self._items: dict[UUID, Item] = {}
        self._tags: dict[UUID, Tag] = {}
        self._links: list[ItemTagLink] = []
        self._category_parent_links: list[CategoryParentLink] = []
        self._item_parent_links: list[ItemParentLink] = []
        self._item_relation_links: list[ItemRelationLink] = []

        status = self._stat()
        if status is not None and S_ISDIR(status.st_mode):
            raise TaxomeshRepositoryError(f"path is a directory, not a file: {self._path}")

        if status is not None:
            self._load()
        else:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise TaxomeshRepositoryError(f"Could not write {self._path}: {exc}") from exc
            self._flush()

    def __repr__(self) -> str:
        """Render as the constructor call that opens the same file."""
        return f"{type(self).__name__}({str(self._path)!r})"

    # ------------------------------------------------------------------
    # The format
    # ------------------------------------------------------------------

    @abstractmethod
    def _parse(self, text: str) -> object:
        """Return the document the file's text holds.

        Args:
            text: The whole file.

        Returns:
            The parsed document, which a store holds as a mapping.
        """

    @abstractmethod
    def _render(self, document: Mapping[str, object]) -> str:
        """Return the text a file holding this document reads.

        Args:
            document: The whole store, made of plain JSON values.

        Returns:
            The file's new text.
        """

    # ------------------------------------------------------------------
    # Atomicity boundary
    # ------------------------------------------------------------------

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Hold the repository's lock for the block, so no other thread reads or writes inside it.

        A file has no transactions. Each write writes the whole store to disk on its own, so the
        block rolls **nothing** back: when an operation that writes more than once fails in the
        middle, the writes made before the failure stay on disk. Use ``DjangoRepository`` where the
        writes of one operation must roll back together.
        """
        with self._lock:
            yield

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Read what the file holds into memory, and record the file's stamp.

        Raises:
            TaxomeshRepositoryError: If the file cannot be read or parsed.
        """
        try:
            with self._path.open(encoding=ENCODING) as fh:
                text = fh.read()
                stamp = _stamp_of(os.fstat(fh.fileno()))
            document = self._parse(text)
            if not isinstance(document, dict):
                raise ValueError("Expected a mapping at the top level")
            contents = _Contents(
                categories={UUID(k): Category.model_validate(v) for k, v in document.get("categories", {}).items()},
                items={UUID(k): Item.model_validate(v) for k, v in document.get("items", {}).items()},
                tags={UUID(k): Tag.model_validate(v) for k, v in document.get("tags", {}).items()},
                item_tag_links=[ItemTagLink.model_validate(lnk) for lnk in document.get("item_tag_links", [])],
                category_parent_links=[
                    CategoryParentLink.model_validate(lnk) for lnk in document.get("category_parent_links", [])
                ],
                item_parent_links=[
                    ItemParentLink.model_validate(lnk) for lnk in document.get("item_parent_links", [])
                ],
                item_relation_links=[
                    ItemRelationLink.model_validate(lnk) for lnk in document.get("item_relation_links", [])
                ],
            )
        except Exception as exc:
            raise TaxomeshRepositoryError(f"Could not load repository from {self._path}: {exc}") from exc
        self._stamp = stamp
        self._put(contents)

    def _contents(self) -> _Contents:
        """Return a copy of what memory holds, which no later write changes.

        The containers are copied and the rows shared: rows are frozen, so this is a full copy.
        """
        return _Contents(
            categories=dict(self._categories),
            items=dict(self._items),
            tags=dict(self._tags),
            item_tag_links=list(self._links),
            category_parent_links=list(self._category_parent_links),
            item_parent_links=list(self._item_parent_links),
            item_relation_links=list(self._item_relation_links),
        )

    def _put(self, contents: _Contents) -> None:
        """Make memory hold ``contents`` as a load of a file holding them does.

        A link that names a row that is not stored is dropped, and the top level is normalised, so
        contents taken between two writes of one operation read as a new repository would read
        them.
        """
        self._categories, self._items, self._tags = contents.categories, contents.items, contents.tags
        self._links = contents.item_tag_links
        self._category_parent_links = contents.category_parent_links
        self._item_parent_links = contents.item_parent_links
        self._item_relation_links = contents.item_relation_links
        self._drop_dangling_links()
        self._category_parent_links, self._item_parent_links = normalise_root_links(
            self._categories, self._category_parent_links, self._item_parent_links
        )

    def _stat(self) -> os.stat_result | None:
        """Return the status of the store file, or ``None`` when there is no file.

        Raises:
            TaxomeshRepositoryError: If the file's status cannot be read, as when its directory
                refuses a look inside.
        """
        try:
            return self._path.stat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise TaxomeshRepositoryError(f"Could not read {self._path}: {exc}") from exc

    def _require_unchanged(self) -> None:
        """Refuse to write over a file another writer changed since this repository read it.

        Raises:
            TaxomeshRepositoryError: If the file's stamp differs from the one this repository
                recorded when it last read or wrote the file, if the file is gone, or if its
                status cannot be read.
        """
        status = self._stat()
        current = None if status is None else _stamp_of(status)
        if current != self._stamp:
            raise TaxomeshRepositoryError(
                f"{self._path} changed since this repository read it; build a new repository to read the change"
            )

    def _drop_dangling_links(self) -> None:
        """Drop every link that names a row that is not stored.

        Each delete calls this after it removes its row, so the same write deletes every link that
        names that row. Loading calls it too, so a store that holds such links loads without them
        and is written without them on the next save.
        """
        self._links = [lnk for lnk in self._links if lnk.item_id in self._items and lnk.tag_id in self._tags]
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if lnk.category_id in self._categories and lnk.parent_category_id in self._categories
        ]
        self._item_parent_links = [
            lnk
            for lnk in self._item_parent_links
            if lnk.item_id in self._items and lnk.category_id in self._categories
        ]
        self._item_relation_links = [
            lnk
            for lnk in self._item_relation_links
            if lnk.source_item_id in self._items and lnk.target_item_id in self._items
        ]

    def _document(self) -> dict[str, object]:
        """Return the whole store as the document the file holds."""
        return {
            "categories": {str(k): v.model_dump(mode="json") for k, v in self._categories.items()},
            "items": {str(k): v.model_dump(mode="json") for k, v in self._items.items()},
            "tags": {str(k): v.model_dump(mode="json") for k, v in self._tags.items()},
            "item_tag_links": [lnk.model_dump(mode="json") for lnk in self._links],
            "category_parent_links": [lnk.model_dump(mode="json") for lnk in self._category_parent_links],
            "item_parent_links": [lnk.model_dump(mode="json") for lnk in self._item_parent_links],
            "item_relation_links": [lnk.model_dump(mode="json") for lnk in self._item_relation_links],
        }

    def _flush(self) -> None:
        """Write the whole store to the file atomically, or raise and leave the file as it was.

        Renders the whole store, writes it to a sibling temp file, calls ``os.fsync`` to flush OS
        buffers, then replaces the target file via ``os.replace`` (POSIX atomic rename). When any
        step fails, the file still holds the last good state, and the temp file is removed when it
        can be. The write that called this puts memory back (see ``_writing``).

        Raises:
            TaxomeshRepositoryError: If the store cannot be written.
        """
        tmp_path: Path | None = None
        try:
            payload = self._render(self._document())
            fd, tmp_path_str = tempfile.mkstemp(dir=self._path.parent, suffix=TEMP_SUFFIX)
            tmp_path = Path(tmp_path_str)
            with os.fdopen(fd, "w", encoding=ENCODING) as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
                stamp = _stamp_of(os.fstat(fh.fileno()))
            os.replace(tmp_path, self._path)
            self._stamp = stamp
        except Exception as exc:
            if tmp_path is not None:
                with suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
            raise TaxomeshRepositoryError(f"Could not write {self._path}: {exc}") from exc

    # ------------------------------------------------------------------
    # Category
    # ------------------------------------------------------------------

    @_writing
    def save_category(self, category: Category, *, expected_version: int | None = None) -> Category:
        """Store a category row: insert it, or replace the stored row with its identifier.

        The given row does not change. An update stores the version of the row that it replaces
        plus one.

        Args:
            category: The category row to store.
            expected_version: The version that the stored row must be at, or ``None`` for no
                comparison. The repository compares it before it writes anything.

        Returns:
            The row as stored, with the version that the repository assigned.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored.
            TaxomeshExternalIdConflictError: If ``category.external_id`` is not ``None`` and another
                category already has it.
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        replaced = self._categories.get(category.category_id)
        stored = row_to_store(
            category,
            replaced,
            expected_version=expected_version,
            entity_name="category",
            entity_id=category.category_id,
        )
        check_external_id_unique(category.category_id, category.external_id, self._categories, "category")
        self._categories[category.category_id] = stored
        self._flush()
        return stored

    @_reading
    def find_category(self, category_id: UUID) -> Category | None:
        """Return the category with this identifier, or ``None``.

        Args:
            category_id: The identifier of the category.

        Returns:
            The category row, or ``None`` when no category with this identifier is stored.
        """
        return self._categories.get(category_id)

    @_reading
    def list_categories(self, *, enabled: bool | None = True) -> list[Category]:
        """Return the stored categories, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled categories, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching categories, ordered by ``(name ASC, category_id ASC)``; empty when none
            match.
        """
        cats = list(self._categories.values())
        if enabled is not None:
            cats = [c for c in cats if c.enabled == enabled]
        return sorted(cats, key=lambda c: (c.name, str(c.category_id)))

    @_writing
    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category and every link that names it, in one write.

        The links deleted with it are its parent links, as child and as parent, and its
        placements.

        Args:
            category_id: The identifier of the category to delete.

        Returns:
            ``True`` if the category was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        if category_id not in self._categories:
            return False
        del self._categories[category_id]
        self._drop_dangling_links()
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Item
    # ------------------------------------------------------------------

    @_writing
    def save_item(self, item: Item, *, expected_version: int | None = None) -> Item:
        """Store an item row: insert it, or replace the stored row with its identifier.

        The given row does not change. An update stores the version of the row that it replaces
        plus one.

        Args:
            item: The item row to store.
            expected_version: The version that the stored row must be at, or ``None`` for no
                comparison. The repository compares it before it writes anything.

        Returns:
            The row as stored, with the version that the repository assigned.

        Raises:
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                not at it, or no row is stored.
            TaxomeshExternalIdConflictError: If ``item.external_id`` is not ``None`` and another item
                already has it.
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        replaced = self._items.get(item.item_id)
        stored = row_to_store(
            item,
            replaced,
            expected_version=expected_version,
            entity_name="item",
            entity_id=item.item_id,
        )
        check_external_id_unique(item.item_id, item.external_id, self._items, "item")
        self._items[item.item_id] = stored
        self._flush()
        return stored

    @_reading
    def find_item(self, item_id: UUID) -> Item | None:
        """Return the item with this identifier, or ``None``.

        Args:
            item_id: The identifier of the item.

        Returns:
            The item row, or ``None`` when no item with this identifier is stored.
        """
        return self._items.get(item_id)

    @_reading
    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        """Return the stored items, ordered by name and then by identifier.

        Args:
            enabled: ``True`` (the default) returns only the enabled items, ``False`` only the
                disabled ones, and ``None`` all of them.

        Returns:
            The matching items, ordered by ``(name ASC, item_id ASC)``; empty when none match.
        """
        items = list(self._items.values())
        if enabled is not None:
            items = [i for i in items if i.enabled == enabled]
        return sorted(items, key=lambda i: (i.name, str(i.item_id)))

    @_writing
    def delete_item(self, item_id: UUID) -> bool:
        """Delete an item and every link that names it, in one write.

        The links deleted with it are its placements, its tag links and its relations at either
        end.

        Args:
            item_id: The identifier of the item to delete.

        Returns:
            ``True`` if the item was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        if item_id not in self._items:
            return False
        del self._items[item_id]
        self._drop_dangling_links()
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Tag
    # ------------------------------------------------------------------

    @_writing
    def save_tag(self, tag: Tag) -> None:
        """Store a tag row: insert it, or replace the stored row with its identifier.

        Args:
            tag: The tag row to store.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        self._tags[tag.tag_id] = tag
        self._flush()

    @_reading
    def find_tag(self, tag_id: UUID) -> Tag | None:
        """Return the tag with this identifier, or ``None``.

        Args:
            tag_id: The identifier of the tag.

        Returns:
            The tag row, or ``None`` when no tag with this identifier is stored.
        """
        return self._tags.get(tag_id)

    @_reading
    def list_tags(self) -> list[Tag]:
        """Return every stored tag.

        Returns:
            Every tag row; empty when no tag is stored.
        """
        return list(self._tags.values())

    @_reading
    def map_tags_by_id(self, tag_ids: Collection[UUID]) -> Mapping[UUID, Tag]:
        """Return the tags whose ``tag_id`` is in ``tag_ids``.

        Args:
            tag_ids: The identifiers of the tags to look up.

        Returns:
            A dict from the identifier of each stored tag to its row. An identifier that names no
            stored tag is left out of the dict, and no error is raised.
        """
        return {tag_id: self._tags[tag_id] for tag_id in tag_ids if tag_id in self._tags}

    @_writing
    def delete_tag(self, tag_id: UUID) -> bool:
        """Delete a tag and every link that names it, in one write.

        The links deleted with it are its tag links.

        Args:
            tag_id: The identifier of the tag to delete.

        Returns:
            ``True`` if the tag was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        if tag_id not in self._tags:
            return False
        del self._tags[tag_id]
        self._drop_dangling_links()
        self._flush()
        return True

    # ------------------------------------------------------------------
    # Tag ↔ Item association
    # ------------------------------------------------------------------

    @_writing
    def add_item_tag_link(self, item_id: UUID, tag_id: UUID) -> None:
        """Store a tag link: the tag on the item. Nothing changes when the link is already stored.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        already_linked = any(lnk.tag_id == tag_id and lnk.item_id == item_id for lnk in self._links)
        if not already_linked:
            self._links.append(ItemTagLink(tag_id=tag_id, item_id=item_id))
            self._flush()

    @_writing
    def delete_item_tag_link(self, item_id: UUID, tag_id: UUID) -> bool:
        """Delete the tag link of this tag on this item.

        Args:
            item_id: The identifier of the item.
            tag_id: The identifier of the tag.

        Returns:
            ``True`` if the link was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        before = len(self._links)
        self._links = [lnk for lnk in self._links if not (lnk.tag_id == tag_id and lnk.item_id == item_id)]
        if len(self._links) < before:
            self._flush()
            return True
        return False

    @_reading
    def list_item_tag_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        tag_ids: Collection[UUID] | None = None,
    ) -> list[ItemTagLink]:
        """Return the stored tag links, filtered by either end when a filter is given.

        Args:
            item_ids: When given, only the links whose ``item_id`` is in it. An empty collection
                returns ``[]``: it is not "no filter".
            tag_ids: When given, only the links whose ``tag_id`` is in it. An empty collection
                returns ``[]``: it is not "no filter". When both filters are given, a link must
                match both.

        Returns:
            The matching tag links, ordered by ``(item_id ASC, tag_id ASC)``.
        """
        links: list[ItemTagLink] = self._links
        if item_ids is not None:
            wanted_items = set(item_ids)
            links = [lnk for lnk in links if lnk.item_id in wanted_items]
        if tag_ids is not None:
            wanted_tags = set(tag_ids)
            links = [lnk for lnk in links if lnk.tag_id in wanted_tags]
        return sorted(links, key=lambda lnk: (str(lnk.item_id), str(lnk.tag_id)))

    # ------------------------------------------------------------------
    # Category parent links
    # ------------------------------------------------------------------

    @_writing
    def save_category_parent_link(self, link: CategoryParentLink) -> None:
        """Store a parent link: insert it, or update the stored one.

        When a link with the same ``(category_id, parent_category_id)`` is stored, the given link
        takes its place, with its own ``sort_index``. No second link is created.

        Args:
            link: The parent link to store.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        for i, existing in enumerate(self._category_parent_links):
            if existing.category_id == link.category_id and existing.parent_category_id == link.parent_category_id:
                self._category_parent_links[i] = link
                self._flush()
                return
        self._category_parent_links.append(link)
        self._flush()

    @_reading
    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        """Return the stored parent links, filtered by either end when a filter is given.

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
        """
        links = self._category_parent_links
        if category_ids is not None:
            wanted_children = set(category_ids)
            links = [lnk for lnk in links if lnk.category_id in wanted_children]
        if parent_category_ids is not None:
            wanted = set(parent_category_ids)
            links = [lnk for lnk in links if lnk.parent_category_id in wanted]
        return sorted(
            links,
            key=lambda lnk: (str(lnk.parent_category_id), lnk.sort_index, str(lnk.category_id)),
        )

    # ------------------------------------------------------------------
    # Item → Category placement
    # ------------------------------------------------------------------

    @_writing
    def save_item_parent_link(self, link: ItemParentLink) -> None:
        """Store a placement: insert it, or update the stored one.

        When a placement with the same ``(item_id, category_id)`` is stored, the given placement
        takes its place, with its own ``sort_index``. No second placement is created.

        Args:
            link: The placement to store.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        for i, existing in enumerate(self._item_parent_links):
            if existing.item_id == link.item_id and existing.category_id == link.category_id:
                self._item_parent_links[i] = link
                self._flush()
                return
        self._item_parent_links.append(link)
        self._flush()

    @_reading
    def list_item_parent_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        """Return the stored placements, filtered by either end when a filter is given.

        Args:
            item_ids: When given, only the placements whose ``item_id`` is in it.
            category_ids: When given, only the placements whose ``category_id`` is in it. An empty
                collection in either filter returns ``[]``: it is not "no filter". When both
                filters are given, a placement must match both.

        Returns:
            The matching placements, ordered by ``(category_id ASC, sort_index ASC, item_id ASC)``.
        """
        links: list[ItemParentLink] = self._item_parent_links
        if item_ids is not None:
            wanted_items = set(item_ids)
            links = [lnk for lnk in links if lnk.item_id in wanted_items]
        if category_ids is not None:
            wanted = set(category_ids)
            links = [lnk for lnk in links if lnk.category_id in wanted]
        return sorted(
            links,
            key=lambda lnk: (str(lnk.category_id), lnk.sort_index, str(lnk.item_id)),
        )

    @_writing
    def delete_category_parent_link(self, category_id: UUID, parent_category_id: UUID) -> bool:
        """Delete the parent link of this category under this parent.

        Args:
            category_id: The identifier of the child category.
            parent_category_id: The identifier of the parent category.

        Returns:
            ``True`` if the link was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        before = len(self._category_parent_links)
        self._category_parent_links = [
            lnk
            for lnk in self._category_parent_links
            if not (lnk.category_id == category_id and lnk.parent_category_id == parent_category_id)
        ]
        if len(self._category_parent_links) < before:
            self._flush()
            return True
        return False

    @_writing
    def delete_item_parent_link(self, item_id: UUID, category_id: UUID) -> bool:
        """Delete the placement of this item in this category.

        Args:
            item_id: The identifier of the item.
            category_id: The identifier of the category.

        Returns:
            ``True`` if the placement was stored and is deleted; ``False`` if it was not stored.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        before = len(self._item_parent_links)
        self._item_parent_links = [
            lnk for lnk in self._item_parent_links if not (lnk.item_id == item_id and lnk.category_id == category_id)
        ]
        if len(self._item_parent_links) < before:
            self._flush()
            return True
        return False

    # ------------------------------------------------------------------
    # Item relation links
    # ------------------------------------------------------------------

    @_writing
    def save_item_relation_link(self, link: ItemRelationLink) -> None:
        """Store a relation: insert it, or update the stored one.

        When a relation with the same ``(source_item_id, target_item_id, relation_type)`` is
        stored, the given relation takes its place, with its own ``sort_index`` and ``metadata``.
        No second relation is created.

        Args:
            link: The relation to store.

        Raises:
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        for i, existing in enumerate(self._item_relation_links):
            if (
                existing.source_item_id == link.source_item_id
                and existing.target_item_id == link.target_item_id
                and existing.relation_type == link.relation_type
            ):
                self._item_relation_links[i] = link
                self._flush()
                return
        self._item_relation_links.append(link)
        self._flush()

    @_reading
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
                ``"both"`` those whose source or target is ``item_id``, each relation at most once.

        Returns:
            The matching relations, ordered by ``(sort_index ASC, source_item_id ASC,
            target_item_id ASC)``; empty when none match.
        """
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id == item_id]
        elif direction == "incoming":
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id == item_id]
        else:  # "both" — links where item_id is on either end, each link once
            result = [lnk for lnk in self._item_relation_links if item_id in (lnk.source_item_id, lnk.target_item_id)]
        if relation_types:
            type_set = set(relation_types)
            result = [lnk for lnk in result if lnk.relation_type in type_set]
        return sorted(result, key=lambda lnk: (lnk.sort_index, str(lnk.source_item_id), str(lnk.target_item_id)))

    @_reading
    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        """Return the relations of many items in one pass over the stored relations, by direction."""
        id_set = set(item_ids)
        if not id_set:
            return []
        if direction == "outgoing":
            result = [lnk for lnk in self._item_relation_links if lnk.source_item_id in id_set]
        elif direction == "incoming":
            result = [lnk for lnk in self._item_relation_links if lnk.target_item_id in id_set]
        else:
            result = [
                lnk
                for lnk in self._item_relation_links
                if lnk.source_item_id in id_set or lnk.target_item_id in id_set
            ]
        if relation_types:
            type_set = set(relation_types)
            result = [lnk for lnk in result if lnk.relation_type in type_set]
        if direction == "outgoing":
            return sorted(
                result,
                key=lambda lnk: (str(lnk.source_item_id), lnk.relation_type, lnk.sort_index, str(lnk.target_item_id)),
            )
        if direction == "incoming":
            return sorted(
                result,
                key=lambda lnk: (str(lnk.target_item_id), lnk.relation_type, lnk.sort_index, str(lnk.source_item_id)),
            )
        return sorted(result, key=lambda lnk: (lnk.sort_index, str(lnk.source_item_id), str(lnk.target_item_id)))

    @_writing
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
            TaxomeshRepositoryError: If another writer changed the file since this repository read
                it, or the file cannot be written; nothing is written.
        """
        before = len(self._item_relation_links)
        self._item_relation_links = [
            lnk
            for lnk in self._item_relation_links
            if not (
                lnk.source_item_id == source_item_id
                and lnk.target_item_id == target_item_id
                and lnk.relation_type == relation_type
            )
        ]
        if len(self._item_relation_links) < before:
            self._flush()
            return True
        return False

    # ------------------------------------------------------------------
    # External-ID lookup
    # ------------------------------------------------------------------

    @_reading
    def find_item_by_external_id(self, external_id: str) -> Item | None:
        """Return the item with this external id, or ``None``.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The item row, or ``None`` when no item has this external id.
        """
        return next((item for item in self._items.values() if item.external_id == external_id), None)

    @_reading
    def find_category_by_external_id(self, external_id: str) -> Category | None:
        """Return the category with this external id, or ``None``.

        Args:
            external_id: The external id to look up, in its stored form: a ``str``, never ``None``.

        Returns:
            The category row, or ``None`` when no category has this external id. The repository
            does not leave out the implicit root: the caller does.
        """
        return next((cat for cat in self._categories.values() if cat.external_id == external_id), None)

    @_reading
    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Item]:
        """Return the items whose ``item_id`` is in ``item_ids``.

        Args:
            item_ids: The identifiers of the items to look up, with no duplicates.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A dict from the identifier of each stored item to its row. An identifier that names no
            stored item is left out of the dict, and no error is raised.
        """
        result: dict[UUID, Item] = {}
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is not None and (enabled is None or item.enabled == enabled):
                result[item_id] = item
        return result

    @_reading
    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Category]:
        """Return the categories whose ``category_id`` is in ``category_ids``.

        Args:
            category_ids: The identifiers of the categories to look up, with no duplicates.
            enabled: ``True`` returns only the enabled categories, ``False`` only the disabled
                ones, and ``None`` (the default) every matching category.

        Returns:
            A dict from the identifier of each stored category to its row. An identifier that
            names no stored category is left out of the dict, and no error is raised.
        """
        result: dict[UUID, Category] = {}
        for category_id in category_ids:
            category = self._categories.get(category_id)
            if category is not None and (enabled is None or category.enabled == enabled):
                result[category_id] = category
        return result

    @_reading
    def map_items_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Item]:
        """Return the items whose ``external_id`` is in ``external_ids``.

        Args:
            external_ids: The external ids to look up, in stored form, with no duplicates.
            enabled: ``True`` returns only the enabled items, ``False`` only the disabled ones, and
                ``None`` (the default) every matching item.

        Returns:
            A dict from the external id of each stored item to its row. An external id that no
            stored item has is left out of the dict, and no error is raised.
        """
        return bulk_lookup_by_external_id(self._items, external_ids, enabled)

    @_reading
    def map_categories_by_external_id(
        self,
        external_ids: Collection[str],
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Category]:
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
        """
        return bulk_lookup_by_external_id(self._categories, external_ids, enabled)

    @_reading
    def find_item_by_slug(self, slug: str) -> Item | None:
        """Return the item with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The item row, or ``None`` when no item has this slug.
        """
        return next((i for i in self._items.values() if i.slug == slug), None)

    @_reading
    def find_category_by_slug(self, slug: str) -> Category | None:
        """Return the category with this slug, or ``None``.

        Args:
            slug: The slug to look up, which is not empty.

        Returns:
            The category row, or ``None`` when no category has this slug.
        """
        return next((c for c in self._categories.values() if c.slug == slug), None)

    # ------------------------------------------------------------------
    # Configuration introspection
    # ------------------------------------------------------------------

    @property
    def config_summary(self) -> str:
        """The path of the storage file, as the caller gave it.

        Returns:
            The path given when the repository was built, as text. Reading it never raises, and the
            text is never empty.
        """
        return str(self._path)

    def describe(self) -> RepositoryInfo:
        """Return what this repository reports about itself.

        Returns:
            A :class:`RepositoryInfo` with the name of the class and the path of the storage file.
            Its ``diagnostics`` is empty: a file backend has nothing to report beyond its path.
        """
        return RepositoryInfo(backend=type(self).__name__, path=str(self._path), diagnostics={})
