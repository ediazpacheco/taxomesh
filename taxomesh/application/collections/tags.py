"""The ``service.tags`` collection."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Any, ClassVar
from uuid import UUID, uuid4

from taxomesh.application.collections.base import (
    EntityCollectionBase,
    _as_validation_error,
    _changed,
    _given,
    _require_collection,
    _require_plain_json,
)
from taxomesh.domain.models import Tag
from taxomesh.domain.refs import ItemRef, TagRef, item_id_of, tag_id_of
from taxomesh.domain.types import UNSET, UnsetType
from taxomesh.exceptions import TaxomeshNotFoundError, TaxomeshTagNotFoundError
from taxomesh.utils.memoize import memoize


class TagCollection(EntityCollectionBase[Tag, TagRef]):
    """Tags, reached as a container on the service.

    The tag reads and writes are here: subscript and :meth:`get`, :meth:`get_many`, ``in`` and
    ``len()``, listing, creation, update and deletion. Subscript and :meth:`get` read one tag
    through the port's ``find_tag``.

    No member here takes an ``enabled`` filter, on purpose: ``Tag`` has no ``enabled`` field and
    the port's ``list_tags()`` takes no filter, so a signature with the filter would promise a
    choice that does not exist.

    Reached as ``service.tags`` and never constructed directly: its memoized reads keep their
    entries in the service's cache, which the service gives to this collection when it builds it.
    """

    _not_found: ClassVar[type[TaxomeshNotFoundError]] = TaxomeshTagNotFoundError
    _namespace: ClassVar[str] = "tags"

    def __getitem__(self, key: TagRef, /) -> Tag:
        """Return the tag this names, or raise.

        Args:
            key: The tag, or its identifier. Only the identifier is read.

        Returns:
            The stored Tag.

        Raises:
            TaxomeshTagNotFoundError: If no tag with this identifier is stored.
            TypeError: If ``key`` is neither a ``Tag`` nor a ``UUID``.

        Note:
            This calls the port's ``find_tag`` directly, with no cache, and turns its ``None`` into
            the error.
        """
        tag_id = tag_id_of(key)
        found = self._service.repository.find_tag(tag_id)
        if found is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        return found

    def _all(self) -> Sequence[Tag]:
        """Return every stored tag — the set ``len`` counts."""
        return tuple(self._service.repository.list_tags())

    def get_many(self, tags: TagRef | Collection[TagRef], /) -> Mapping[UUID, Tag]:
        """Return the tags these name, keyed by identifier.

        Args:
            tags: The tag or identifier to look up, or a collection of them. An absent key is left
                out of the result: it does not raise, and it does not appear with a ``None`` value.

        Returns:
            A mapping of tag identifier to ``Tag``, with only the tags that were found. Any number
            of identifiers costs one storage read, and an empty request none. The answer is cached,
            and calls that name the same tags share one entry, in any order and with any repeats.

        Raises:
            TypeError: If ``tags`` is neither one key nor a collection, or a key is neither a
                ``Tag`` nor a ``UUID``.
        """
        keys = (tags,) if isinstance(tags, (Tag, UUID)) else tags
        _require_collection("tags", keys)
        tag_ids = frozenset(tag_id_of(tag) for tag in keys)
        if not tag_ids:
            return {}
        return dict(self._fetch(tag_ids))

    @memoize
    def _fetch(self, tag_ids: frozenset[UUID], /) -> dict[UUID, Tag]:
        """The cached read behind :meth:`get_many`, keyed by the set of identifiers."""
        return dict(self._service.repository.map_tags_by_id(tag_ids))

    def delete(self, key: TagRef, /) -> None:
        """Delete a tag, and remove it from every item that carries it.

        Args:
            key: The tag to delete, or its identifier.

        Raises:
            TaxomeshTagNotFoundError: If no tag with this identifier is stored.
            TypeError: If ``key`` is neither a ``Tag`` nor a ``UUID``.
        """
        tag_id = tag_id_of(key)
        found = self._service.repository.delete_tag(tag_id)
        if not found:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        self._cache.clear()

    def list(self, *, item: ItemRef | None = None) -> Sequence[Tag]:
        """Return tags — every one, or those an item carries.

        Args:
            item: When given, only the tags this item carries, ordered by name, then by
                identifier: a tag link carries no sort index.

        Returns:
            The matching tags, empty when there are none. Without ``item``, every stored tag, in no
            promised order.

        Raises:
            TaxomeshItemNotFoundError: If ``item`` is given and names an item that is not stored.
            TaxomeshTagNotFoundError: If a tag link names a tag that is not stored.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``.

        Example::

            svc.tags.list(item=song)
            # the song's tags, by name
        """
        return self._listing(None if item is None else item_id_of(item))

    @memoize
    def _listing(self, item_id: UUID | None, /) -> Sequence[Tag]:
        """The cached read behind :meth:`list`, keyed by the item's identifier."""
        if item_id is None:
            return tuple(self._service.repository.list_tags())
        self._service.items[item_id]
        links = self._service.repository.list_item_tag_links(item_ids=[item_id])
        if not links:
            return ()
        found = self._service.repository.map_tags_by_id({link.tag_id for link in links})
        missing = next((link.tag_id for link in links if link.tag_id not in found), None)
        if missing is not None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {missing}")
        return tuple(sorted(found.values(), key=lambda tag: (tag.name, str(tag.tag_id))))

    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    def create(self, name: str, *, metadata: dict[str, Any] | None = None) -> Tag:
        """Create a tag.

        Args:
            name: The name of the tag.
            metadata: Optional data of your own, stored with the tag.

        Returns:
            The newly created Tag.

        Raises:
            TaxomeshValidationError: If the model refuses a value, such as a name over its maximum
                length, or ``metadata`` is not plain JSON: a mapping whose keys are text and whose
                values are text, finite numbers, booleans, ``None``, lists or tuples, and such
                dicts. A tuple is taken as a list, and an enum member as its value.
            TypeError: If an argument is of a type the model does not take.
        """
        _require_plain_json(metadata)
        with _as_validation_error():
            tag = Tag(
                tag_id=uuid4(),
                name=name,
                metadata=metadata if metadata is not None else {},
            )
        self._service.repository.save_tag(tag)
        self._cache.clear()
        return tag

    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    def update(
        self, tag: TagRef, *, name: str | UnsetType = UNSET, metadata: dict[str, Any] | UnsetType = UNSET
    ) -> Tag:
        """Update a tag, and keep every field that the call does not give.

        Both fields default to ``UNSET``, which keeps the field as it is, and any other value
        replaces it. Neither is nullable, so ``None`` is refused. The repository replaces the row
        with a new one, which this method returns; a row that a caller already holds keeps the
        values it was read with.

        Args:
            tag: The tag to update, or its identifier. Only the identifier is read.
            name: New name.
            metadata: New metadata. Replaces the stored dict rather than merging into it.

        Returns:
            The updated Tag, a new row.

        Raises:
            TaxomeshTagNotFoundError: If no tag with this identifier is stored.
            TaxomeshValidationError: If the model refuses a new value, such as a name over its
                maximum length, or ``metadata`` is not plain JSON.
            TypeError: If ``tag`` is neither a ``Tag`` nor a ``UUID``, a field is ``None``, or a new
                value is of a type the model does not take.
        """
        changes = _given({"name": name, "metadata": metadata})
        _require_plain_json(metadata)
        changed = _changed(self[tag], changes)
        self._service.repository.save_tag(changed)
        self._cache.clear()
        return changed
