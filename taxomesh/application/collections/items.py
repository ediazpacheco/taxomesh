"""The ``service.items`` collection."""

from __future__ import annotations

import builtins
import logging
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from uuid import UUID

from taxomesh.application.collections.base import (
    EntityCollectionBase,
    _as_validation_error,
    _changed,
    _given,
    _normalise_external_ids,
    _require_collection,
    _require_enabled,
    _require_limit,
    _require_plain_json,
    _require_sequence,
    _require_text,
    _require_version,
)
from taxomesh.application.search import DEFAULT_SEARCH_LIMIT, SearchCandidate, SearchCorpus, SearchEngine
from taxomesh.domain.constants import DEFAULT_ITEM_EXTERNAL_ID
from taxomesh.domain.dag import collect_subtree
from taxomesh.domain.models import Item, ItemParentLink, ItemRelationLink
from taxomesh.domain.refs import CategoryRef, ItemRef, TagRef, category_id_of, item_id_of, tag_id_of
from taxomesh.domain.related import RelatedItems
from taxomesh.domain.types import UNSET, Direction, ExternalId, UnsetType, normalise_external_id
from taxomesh.exceptions import (
    TaxomeshDuplicateSlugError,
    TaxomeshExternalIdConflictError,
    TaxomeshItemNotFoundError,
    TaxomeshNotFoundError,
    TaxomeshTagNotFoundError,
    TaxomeshValidationError,
)
from taxomesh.utils.memoize import ReadCache, memoize

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for type checking only
    from taxomesh.application.service import TaxomeshService

logger = logging.getLogger(__name__)


class ItemCollection(EntityCollectionBase[Item, ItemRef]):
    """Items, reached as a container on the service.

    The item reads and writes are here: subscript and the other lookups, the count, listing,
    search, creation, update, deletion, placement, tagging and relations.

    Reached as ``service.items`` and never constructed directly: every memoized read below keeps
    its entries in the service's cache, which the service gives to this collection when it builds it.
    """

    _not_found: ClassVar[type[TaxomeshNotFoundError]] = TaxomeshItemNotFoundError
    _namespace: ClassVar[str] = "items"

    def __init__(self, service: TaxomeshService, *, cache: ReadCache, corpus: SearchCorpus[Item]) -> None:
        """Bind the collection to its service and to the state that service owns.

        Args:
            service: The owning service.
            cache: The service's cache, which holds the memoized reads below.
            corpus: The item search corpus. The service holds it; this collection fills it on
                search and drops it whenever it creates, updates or deletes an item.
        """
        super().__init__(service, cache=cache)
        self._corpus = corpus

    def __getitem__(self, key: ItemRef, /) -> Item:
        """Return the item this names, or raise.

        Args:
            key: The item, or its identifier. Only the identifier is read.

        Returns:
            The stored ``Item``.

        Raises:
            TaxomeshItemNotFoundError: If no item with this identifier is stored.
            TypeError: If ``key`` is neither an ``Item`` nor a ``UUID``.
        """
        return self._lookup(item_id_of(key))

    @memoize
    def _lookup(self, item_id: UUID, /) -> Item:
        """Read one item through the cache.

        The one cached read of a single row behind subscript, ``get`` and ``in``. It is
        positional-only for the same reason as the category method: ``memoize`` builds the key
        from the arguments as the call passes them, so a keyword call would build a different key.

        **Nothing primes this method**, unlike the category one: the cache has no size bound and
        item rows are large, so a listing does not keep every row that it read.

        Args:
            item_id: The identifier of the item.

        Returns:
            The stored ``Item``.

        Raises:
            TaxomeshItemNotFoundError: If no item with this identifier is stored.
        """
        result = self._service.repository.find_item(item_id)
        if result is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        return result

    def _require_stored(self, item_id: UUID, /) -> Item:
        """Return the stored item that a write names.

        Reads storage directly, and not through the cache, because a write checks, and builds on,
        what it is about to change: a row that another service changed or deleted after this
        service read it is seen as it is stored.

        Args:
            item_id: The identifier that a write names.

        Returns:
            The stored ``Item``.

        Raises:
            TaxomeshItemNotFoundError: If no item with this identifier is stored.
        """
        found = self._service.repository.find_item(item_id)
        if found is None:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        return found

    def _all(self) -> Sequence[Item]:
        """Return every stored item, with no filter: the rows that ``len`` counts."""
        return tuple(self._service.repository.list_items(enabled=None))

    def get_many(
        self,
        items: ItemRef | Collection[ItemRef],
        /,
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Item]:
        """Return the items these name, keyed by identifier.

        Args:
            items: The item or identifier to look up, or a collection of them. An absent key is
                left out of the result: it does not raise, and it does not appear with a ``None``
                value.
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` (the default) all.
                The default agrees with subscript and :meth:`get`, which do not filter.

        Returns:
            A mapping of item identifier to ``Item``, with only the items that were found. An
            empty request is answered without a storage read. The answer is cached, and calls that
            name the same items share one entry, in any order and with any repeats.

        Raises:
            TypeError: If ``items`` is neither one key nor a collection, a key is neither an
                ``Item`` nor a ``UUID``, or ``enabled`` is neither a ``bool`` nor ``None``.
        """
        _require_enabled(enabled)
        keys = (items,) if isinstance(items, (Item, UUID)) else items
        _require_collection("items", keys)
        item_ids = frozenset(item_id_of(item) for item in keys)
        if not item_ids:
            return {}
        return dict(self._fetch(item_ids, enabled))

    @memoize
    def _fetch(self, item_ids: frozenset[UUID], enabled: bool | None, /) -> dict[UUID, Item]:
        """The cached read behind :meth:`get_many`, keyed by the set of identifiers."""
        return dict(self._service.repository.map_items_by_id(item_ids, enabled=enabled))

    def delete(self, key: ItemRef, /) -> None:
        """Delete an item, with its placements, its tags and its relations in either direction.

        The categories, tags and items it was linked to are not deleted.

        Args:
            key: The item to delete, or its identifier.

        Raises:
            TaxomeshItemNotFoundError: If no item with this identifier is stored.
            TypeError: If ``key`` is neither an ``Item`` nor a ``UUID``.
        """
        item_id = item_id_of(key)
        found = self._service.repository.delete_item(item_id)
        if not found:
            raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
        self._cache.clear()
        self._corpus.invalidate()

    def get_by_slug(self, slug: str, /) -> Item | None:
        """Return the item with this slug, or ``None``.

        Args:
            slug: The slug: a text key for URLs, unique among items.

        Returns:
            The matching ``Item``, or ``None`` when no item has this slug. An empty slug is no
            slug: it answers ``None`` without a storage read, however many items were created
            without one.

        Raises:
            TypeError: If ``slug`` is not a ``str``.
        """
        _require_text("slug", slug)
        if not slug:
            return None
        return self._by_slug(slug)

    @memoize
    def _by_slug(self, slug: str, /) -> Item | None:
        """The cached read behind :meth:`get_by_slug`, for a slug that is not empty."""
        return self._service.repository.find_item_by_slug(slug)

    def get_by_external_id(self, external_id: ExternalId, /) -> Item | None:
        """Return the item with this external id, or ``None``.

        Answers ``None`` for an external id of ``None`` without a storage read. The external id
        is converted to its stored form before the cached read, so ``42`` and ``"42"`` share one
        cache entry.

        Args:
            external_id: The external id: text, an integer or a UUID. Values with the same string
                form name the same row.

        Returns:
            The matching ``Item``, or ``None`` when no item has this external id.

        Raises:
            TypeError: If ``external_id`` is not text, an integer, a UUID or ``None``.
            TaxomeshRepositoryError: If the repository raises it.
        """
        normalised = normalise_external_id(external_id)
        if normalised is None:
            return None
        return self._by_external_id(normalised)

    @memoize
    def _by_external_id(self, external_id: str, /) -> Item | None:
        """The cached read behind :meth:`get_by_external_id`, keyed by the stored form."""
        return self._service.repository.find_item_by_external_id(external_id)

    def get_many_by_external_id(
        self,
        external_ids: ExternalId | Collection[ExternalId],
        /,
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Item]:
        """Return the items for these external ids, keyed by external id.

        Each value is converted to its stored text by the rule that writes use, and by nothing
        else: the surrounding whitespace and the empty string are kept, as a write keeps them.
        ``None`` is left out and a duplicate counts once, so calls that differ only in these
        respects share one cache entry.

        Args:
            external_ids: The external id to look up, or a collection of them. Text, integers and
                UUIDs can be mixed: values with the same string form name the same row, and a
                ``None`` adds nothing. An absent external id is left out of the result.
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` (the default) all.

        Returns:
            A mapping of external id, as stored, to ``Item``, with only the items that were found.

        Raises:
            TypeError: If an external id is not text, an integer, a UUID or ``None``,
                ``external_ids`` is bytes or neither one external id nor a collection, or
                ``enabled`` is neither a ``bool`` nor ``None``.
            TaxomeshRepositoryError: If the repository raises it.
        """
        _require_enabled(enabled)
        normalised = _normalise_external_ids(external_ids)
        if not normalised:
            return {}
        return dict(self._fetch_by_external_ids(normalised, enabled=enabled))

    @memoize
    def _fetch_by_external_ids(
        self,
        external_ids: frozenset[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Item]:
        """The cached read behind :meth:`get_many_by_external_id`, keyed by the set of stored external ids."""
        return dict(self._service.repository.map_items_by_external_id(external_ids, enabled=enabled))

    def list(
        self,
        *,
        category: CategoryRef | None = None,
        recursive: bool = False,
        tag: TagRef | None = None,
        enabled: bool | None = True,
    ) -> Sequence[Item]:
        """Return items: every one, or those in a category, or those that have a tag, or both.

        Args:
            category: When it is given, only the items placed directly in this category, ordered
                by sort index. The category or its identifier.
            recursive: When it is ``True`` and ``category`` is given, also the items of every
                descendant category: each item once, however many categories of that subtree it
                is placed in. The categories come in depth-first order from ``category``, the
                items in sort-index order in each category, and an item placed in several
                categories takes the position of its first placement. It has no effect without
                ``category``.
            tag: When it is given, only the items that have this tag. Without ``category``, they
                are ordered by name, then by identifier, as an unfiltered listing is: a tag link
                has no sort index. With ``category``, the category's listing keeps its own order
                and only the items that have the tag. The tag or its identifier.
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.

        Returns:
            The matching items, empty when there are none.

        Raises:
            TaxomeshCategoryNotFoundError: If ``category`` is given and names a category that is
                not stored, or the implicit root. Checked before the tag.
            TaxomeshTagNotFoundError: If ``tag`` is given and names a tag that is not stored.
            TaxomeshItemNotFoundError: If a placement or a tag link names an item that is not
                stored.
            TypeError: If ``category`` is neither a ``Category`` nor a ``UUID``, ``tag`` neither a
                ``Tag`` nor a ``UUID``, or ``enabled`` neither a ``bool`` nor ``None``.

        Example::

            svc.items.list(category=music, recursive=True)
            # the items of Music and of every category under it, each one once
            svc.items.list(category=music, recursive=True, tag=live)
            # the same listing, keeping only the items tagged live
        """
        _require_enabled(enabled)
        return self._listing(
            None if category is None else category_id_of(category),
            recursive,
            None if tag is None else tag_id_of(tag),
            enabled,
        )

    @memoize
    def _listing(
        self, category_id: UUID | None, recursive: bool, tag_id: UUID | None, enabled: bool | None, /
    ) -> Sequence[Item]:
        """The cached read behind :meth:`list`, keyed by identifiers."""
        if category_id is None:
            if tag_id is None:
                return tuple(self._service.repository.list_items(enabled=enabled))
            tagged = self._in_order(self._tagged_item_ids(tag_id), enabled=enabled)
            return tuple(sorted(tagged, key=lambda item: (item.name, str(item.item_id))))
        self._service.categories[category_id]
        ordered_ids: list[UUID]
        if recursive:
            ordered_ids = self._ordered_subtree_item_ids(category_id)
        else:
            links = sorted(
                self._service.repository.list_item_parent_links(category_ids=[category_id]),
                key=lambda lnk: lnk.sort_index,
            )
            ordered_ids = [lnk.item_id for lnk in links]
        if tag_id is not None:
            tagged_ids = set(self._tagged_item_ids(tag_id))
            ordered_ids = [item_id for item_id in ordered_ids if item_id in tagged_ids]
        return self._in_order(ordered_ids, enabled=enabled)

    def _tagged_item_ids(self, tag_id: UUID) -> builtins.list[UUID]:
        """Return the identifiers of the items that have this tag, in the port's link order.

        Raises:
            TaxomeshTagNotFoundError: If the tag is not stored.
        """
        self._service.tags[tag_id]
        return [link.item_id for link in self._service.repository.list_item_tag_links(tag_ids=[tag_id])]

    def _in_order(self, ordered_ids: builtins.list[UUID], *, enabled: bool | None) -> tuple[Item, ...]:
        """Read the row of each identifier, in the order given, then apply the ``enabled`` filter.

        Raises:
            TaxomeshItemNotFoundError: If an identifier names no stored item.
        """
        if not ordered_ids:
            return ()
        # Read in ONE batch, with no filter: a disabled item must stay different from a deleted
        # one, because an absent key raises below.
        item_map = self._service.repository.map_items_by_id(set(ordered_ids), enabled=None)
        items: list[Item] = []
        for item_id in ordered_ids:
            found = item_map.get(item_id)
            if found is None:
                raise TaxomeshItemNotFoundError(f"Item not found: {item_id}")
            items.append(found)
        return tuple(i for i in items if enabled is None or i.enabled == enabled)

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        category: CategoryRef | None = None,
        recursive: bool = False,
        enabled: bool | None = True,
        fuzzy: bool = True,
    ) -> Sequence[Item]:
        """Return items matching a query, best match first.

        Without ``category``, the candidates come from a corpus whose fields are normalized once.
        The service holds the corpus for ``cache_ttl``, or until it next creates, updates or
        deletes an item. With ``category``, the candidates are the items of that category: read
        from the cached listing, or, with ``recursive``, from storage.

        Args:
            query: The text to match against the name, the slug and the external id.
            limit: The maximum number of results; at least 1.
            category: When it is given, the search covers only this category. The category or its
                identifier.
            recursive: Whether to include the items of the category's descendants. It has an
                effect only with ``category``.
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.
            fuzzy: Whether to add approximate matching to the exact, prefix and substring matching.

        Returns:
            The matching items, ranked by descending score, empty when nothing matches.

        Raises:
            TaxomeshValidationError: If ``limit`` is less than 1.
            TaxomeshCategoryNotFoundError: If ``category`` is given and names a category that is
                not stored, or the implicit root.
            TaxomeshItemNotFoundError: If the query is not blank, ``category`` is given without
                ``recursive``, and a placement in that category names an item that is not stored,
                as :meth:`list` raises. The recursive form skips such a placement.
            TypeError: If ``query`` is not a ``str``, ``limit`` not an ``int``, ``category``
                neither a ``Category`` nor a ``UUID``, or ``enabled`` neither a ``bool`` nor ``None``.
        """
        _require_text("query", query)
        _require_enabled(enabled)
        category_id = None if category is None else category_id_of(category)
        _require_limit(limit)
        if not query.strip():
            # Nothing to match, but the filter still names a category: a filter that names no
            # stored category raises here, as it does for any other query.
            if category_id is not None:
                self._service.categories[category_id]
            return ()

        engine = SearchEngine()
        norm_q = SearchEngine.normalize(query)
        if category_id is None:
            corpus = self._get_item_corpus()
            filtered = [sc for sc in corpus if enabled is None or sc.obj.enabled == enabled]
            return engine._score_corpus(norm_q, filtered, fuzzy=fuzzy, limit=limit)
        candidates = self._load_item_candidates(category_id=category_id, recursive=recursive, enabled=enabled)
        return engine._score_and_rank(
            norm_q,
            candidates,
            get_name=lambda i: i.name,
            get_slug=lambda i: i.slug,
            get_ext=lambda i: i.external_id,
            fuzzy=fuzzy,
            limit=limit,
        )

    def _get_item_corpus(self) -> builtins.list[SearchCandidate[Item]]:
        """Build and hold the search candidates of every item, with their fields normalized.

        Returns the held corpus while it is held. Otherwise it reads every item from the
        repository, normalizes the fields of each candidate once, gives the result to the corpus
        that the service holds, and returns it. The corpus keeps it for the cache's lifetime; a
        create, update or delete of an item here drops it sooner.

        Returns:
            One ``SearchCandidate`` for each item.
        """
        held = self._corpus.candidates
        if held is not None:
            return held
        return self._corpus.hold(
            [
                SearchCandidate(
                    obj=item,
                    norm_name=SearchEngine.normalize(item.name),
                    norm_slug=SearchEngine.normalize(item.slug),
                    norm_ext=(SearchEngine.normalize(item.external_id) if item.external_id is not None else ""),
                )
                for item in self._service.repository.list_items(enabled=None)
            ]
        )

    def _ordered_subtree_item_ids(self, category_id: UUID) -> builtins.list[UUID]:
        """Return the identifiers of the items placed in this category or in a descendant, each once.

        The shared half of the two recursive item reads: this collection's listing and the
        candidate loader of :meth:`search`. The two do different things with a placement whose
        item is not stored, so each caller reads the rows itself. The traversal, the placement
        read and the order are here, so there is one of each.

        The order is the subtree's depth-first order, then ``sort_index`` in each category, and an
        item placed in several categories keeps the position of its first placement. The
        repository's own order would put ``category_id`` first, so the answer would depend on which
        category got the lower identifier.

        Two reads, at any depth: the parent links, then the placements.

        Args:
            category_id: The category to descend from. The caller checks it: whether it is stored,
                and whether the caller may descend from it.

        Returns:
            The item identifiers, in listing order.
        """
        children: dict[UUID, list[UUID]] = {}
        for parent_link in self._service.repository.list_category_parent_links():
            children.setdefault(parent_link.parent_category_id, []).append(parent_link.category_id)
        # The same traversal as a graph limited by ``root``, not a second one: so there is one
        # answer about cycles and one about order.
        subtree = collect_subtree(category_id, children)
        placements: dict[UUID, list[ItemParentLink]] = {}
        for placement in self._service.repository.list_item_parent_links(category_ids=subtree):
            placements.setdefault(placement.category_id, []).append(placement)
        # ``dict.fromkeys`` keeps the insertion order, so each item keeps its first placement.
        return list(
            dict.fromkeys(
                found.item_id
                for cid in subtree
                for found in sorted(placements.get(cid, []), key=lambda lnk: lnk.sort_index)
            )
        )

    def _load_item_candidates(
        self,
        *,
        category_id: UUID,
        recursive: bool,
        enabled: bool | None = True,
    ) -> Sequence[Item]:
        """Return the item candidates that a search limited to a category ranks.

        A search with no category reads its held corpus instead, so a category is always given
        here.

        Args:
            category_id: The category that the search is limited to.
            recursive: When it is ``True``, include the items of every descendant category, each
                item once.
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.
                Applied when the rows are read, not afterwards.

        Returns:
            The items, each once.
        """
        if not recursive:
            # The listing checks that the category is stored.
            return self._listing(category_id, False, None, enabled)

        # Recursive: the items of category_id and of every descendant. The category is checked
        # first, so an identifier that names no stored category fails before the traversal.
        self._service.categories[category_id]
        matched_ids = self._ordered_subtree_item_ids(category_id)
        # Unlike ``list``, an identifier that names no stored item is SKIPPED and does not raise:
        # these are search candidates, and one placement of an item that is not stored must not
        # take every result from the caller.
        item_map = self._service.repository.map_items_by_id(matched_ids, enabled=enabled)
        return [item_map[item_id] for item_id in matched_ids if item_id in item_map]

    def create(
        self,
        name: str,
        *,
        slug: str = "",
        external_id: ExternalId = DEFAULT_ITEM_EXTERNAL_ID,
        # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
        metadata: dict[str, Any] | None = None,
    ) -> Item:
        """Create an item.

        Args:
            name: The name of the item.
            slug: An optional slug: a text key for URLs, unique among items.
            external_id: The optional external id, the key of your record; unique among items
                when it is given. Text, an integer or a UUID: the string form is stored, so the
                value read back is a string even when an ``int`` or a ``UUID`` was given, and
                values with the same string form name the same row.
            metadata: Optional data of your own, stored with the item.

        Returns:
            The new ``Item``.

        Raises:
            TaxomeshDuplicateSlugError: If another item already has the slug.
            TaxomeshExternalIdConflictError: If another item already has the external id.
            TaxomeshValidationError: If the model refuses a value, such as a name over its maximum
                length, or ``metadata`` is not plain JSON: a mapping whose keys are text and whose
                values are text, finite numbers, booleans, ``None``, lists or tuples, and such
                dicts. A tuple is taken as a list, and an enum member as its value.
            TypeError: If an argument is of a type the model does not take, or ``external_id`` is
                not text, an integer, a UUID or ``None``.
        """
        _require_plain_json(metadata)
        now = datetime.now(tz=UTC)
        with _as_validation_error():
            item = Item(
                name=name,
                slug=slug,
                external_id=normalise_external_id(external_id),
                metadata=metadata if metadata is not None else {},
                created_at=now,
                updated_at=now,
            )
        if item.slug:
            existing = self._service.repository.find_item_by_slug(item.slug)
            if existing is not None:
                raise TaxomeshDuplicateSlugError(f"Slug '{item.slug}' is already used by another item")
        stored = self._service.repository.save_item(item)
        self._cache.clear()
        self._corpus.invalidate()
        return stored

    def update(
        self,
        item: ItemRef,
        *,
        name: str | UnsetType = UNSET,
        slug: str | UnsetType = UNSET,
        external_id: ExternalId | UnsetType = UNSET,
        enabled: bool | UnsetType = UNSET,
        # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
        metadata: dict[str, Any] | UnsetType = UNSET,
        expected_version: int | None = None,
    ) -> Item:
        """Update an item, and keep every field that the call does not give.

        Every field defaults to ``UNSET``, which keeps it as it is, and any other value replaces
        it. ``None`` clears ``external_id``, the one nullable field, and is refused for the others.

        The repository replaces the row with a new one, which this method returns; a row that a
        caller already holds keeps the values it was read with. Every check comes before the save:
        the slug and the external id against storage, and each new value against the model. The
        save checks the external id again, for what this check cannot see: a write by another
        caller between the check and the save, or another stored item that already has the
        external id that this item keeps. A refused update stores nothing.

        Args:
            item: The item to update, or its identifier. Only the identifier is read: the update
                applies to the stored row.
            name: The new name.
            slug: The new slug; ``""`` clears it.
            external_id: The new external id: text, an integer or a UUID, stored as its string
                form. ``None`` clears it.
            enabled: The new enabled state.
            metadata: The new metadata. It replaces the stored dict; it is not merged into it.
            expected_version: The ``version`` of the row that the caller read. When it is given,
                the update is made only if the stored row is still at that version; the repository
                compares and writes in one step. ``None`` (the default) makes no comparison.

        Returns:
            The updated ``Item`` as stored, its version one higher than the row it replaced.

        Raises:
            TaxomeshItemNotFoundError: If no item with this identifier is stored.
            TaxomeshDuplicateSlugError: If another item already has the new slug.
            TaxomeshExternalIdConflictError: If another item already has the new external id, or
                the one that this item keeps.
            TaxomeshValidationError: If the model refuses a new value, such as a name over its
                maximum length, ``metadata`` is not plain JSON, or ``expected_version`` is below 0.
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                no longer at it.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, a field other than
                ``external_id`` is ``None``, a new value is of a type the model does not take, or
                ``expected_version`` is neither an ``int`` nor ``None``.
        """
        item_id = item_id_of(item)
        _require_version(expected_version)
        changes = _given({"name": name, "slug": slug, "metadata": metadata, "enabled": enabled})
        _require_plain_json(metadata)
        stored_row = self._require_stored(item_id)
        normalised = None if external_id is UNSET else normalise_external_id(external_id)
        if external_id is not UNSET:
            changes["external_id"] = normalised
        changes["updated_at"] = datetime.now(tz=UTC)
        row = _changed(stored_row, changes)
        if slug is not UNSET and row.slug:
            existing = self._service.repository.find_item_by_slug(row.slug)
            if existing is not None and existing.item_id != item_id:
                raise TaxomeshDuplicateSlugError(f"Slug '{row.slug}' is already used by another item")
        holder = None if normalised is None else self._service.repository.find_item_by_external_id(normalised)
        if holder is not None and holder.item_id != item_id:
            raise TaxomeshExternalIdConflictError(f"External id {normalised!r} is already used by another item")
        stored = self._service.repository.save_item(row, expected_version=expected_version)
        self._cache.clear()
        self._corpus.invalidate()
        return stored

    def place_in(self, item: ItemRef, category: CategoryRef, *, sort_index: int = 0) -> ItemParentLink:
        """Place an item in a category. An item can be placed in several categories.

        Idempotent: to place an item in a category that it is already placed in updates its sort
        index.

        Args:
            item: The item to place, or its identifier.
            category: The category to place it in, or its identifier.
            sort_index: The position among the items of that category.

        Returns:
            The stored ``ItemParentLink``.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
            TaxomeshCategoryNotFoundError: If the category is not stored, or is the implicit root.
            TaxomeshValidationError: If ``sort_index`` is a value that the link refuses, such as
                text that is not a number.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, ``category`` neither a
                ``Category`` nor a ``UUID``, or ``sort_index`` of a type the link does not take. All
                three are refused before anything is read.
        """
        item_id = item_id_of(item)
        category_id = category_id_of(category)
        with _as_validation_error():
            link = ItemParentLink(item_id=item_id, category_id=category_id, sort_index=sort_index)
        self._require_stored(item_id)
        self._service.categories._require_stored(category_id)
        self._service.repository.save_item_parent_link(link)
        self._cache.clear()
        return link

    def remove_from(self, item: ItemRef, category: CategoryRef) -> None:
        """Remove an item from one category; its other placements stay.

        A no-op when the item is not placed in that category.

        Args:
            item: The item to remove, or its identifier.
            category: The category to remove it from, or its identifier.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
            TaxomeshCategoryNotFoundError: If the category is not stored, or is the implicit root.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, or ``category`` neither a
                ``Category`` nor a ``UUID``.
        """
        item_id = item_id_of(item)
        category_id = category_id_of(category)
        self._require_stored(item_id)
        self._service.categories._require_stored(category_id)
        self._service.repository.delete_item_parent_link(item_id, category_id)
        self._cache.clear()

    def move(
        self,
        item: ItemRef,
        *,
        from_category: CategoryRef,
        to_category: CategoryRef,
        before: ItemRef | None = None,
    ) -> ItemParentLink:
        """Move an item from one category to another.

        Each item and category is given as itself or as its identifier.

        Args:
            item: The item to move.
            from_category: The category that it leaves.
            to_category: The category that it joins.
            before: The item to put it before; when it is ``None``, the item goes last.

        Returns:
            The ``ItemParentLink`` in the new category.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
            TaxomeshCategoryNotFoundError: If either category is not stored, or is the implicit root.
            TaxomeshRepositoryError: If storage fails while writing the move.
            TypeError: If one of them is neither a row of its kind nor a ``UUID``.
        """
        item_id = item_id_of(item)
        from_category_id = category_id_of(from_category)
        to_category_id = category_id_of(to_category)
        before_id = None if before is None else item_id_of(before)
        self._require_stored(item_id)
        self._service.categories._require_stored(from_category_id)
        self._service.categories._require_stored(to_category_id)

        existing_siblings = sorted(
            [
                lnk
                for lnk in self._service.repository.list_item_parent_links()
                if lnk.category_id == to_category_id and lnk.item_id != item_id
            ],
            key=lambda lnk: lnk.sort_index,
        )

        if before_id is None:
            insert_pos = len(existing_siblings)
        else:
            insert_pos = next(
                (i for i, lnk in enumerate(existing_siblings) if lnk.item_id == before_id),
                len(existing_siblings),
            )

        new_link = ItemParentLink(item_id=item_id, category_id=to_category_id, sort_index=insert_pos)
        existing_siblings.insert(insert_pos, new_link)

        with self._atomic():
            self._service.repository.delete_item_parent_link(item_id, from_category_id)
            for i, lnk in enumerate(existing_siblings):
                self._service.repository.save_item_parent_link(lnk.model_copy(update={"sort_index": i}))

        return new_link

    def reorder(self, category: CategoryRef, items: Sequence[ItemRef]) -> None:
        """Set the order of a category's items.

        Args:
            category: The category whose items get the order, or its identifier.
            items: Every item placed in that category, in the new order, each the item or its
                identifier.

        Raises:
            TaxomeshCategoryNotFoundError: If the category is not stored, or is the implicit root.
            TaxomeshValidationError: If an item is not placed in that category.
            TaxomeshRepositoryError: If storage fails while writing the order.
            TypeError: If ``category`` is neither a ``Category`` nor a ``UUID``, an item neither an
                ``Item`` nor a ``UUID``, or ``items`` is not a sequence: a set, a mapping or an
                iterator.
        """
        category_id = category_id_of(category)
        _require_sequence("items", items)
        item_ids = [item_id_of(item) for item in items]
        self._service.categories._require_stored(category_id)
        existing = {
            lnk.item_id: lnk
            for lnk in self._service.repository.list_item_parent_links()
            if lnk.category_id == category_id
        }
        for uid in item_ids:
            if uid not in existing:
                raise TaxomeshValidationError(f"Item {uid} is not placed in category {category_id}")
        with self._atomic():
            for sort_index, uid in enumerate(item_ids):
                link = existing[uid].model_copy(update={"sort_index": sort_index})
                self._service.repository.save_item_parent_link(link)

    def tag(self, item: ItemRef, tag: TagRef) -> None:
        """Tag an item. Idempotent.

        Args:
            item: The item to tag, or its identifier: **the item comes first**.
            tag: The tag to add, or its identifier.

        Raises:
            TaxomeshTagNotFoundError: If the tag is not stored. Checked first, so a call with the
                two identifiers in the wrong order raises this error, and does not link the wrong
                pair.
            TaxomeshItemNotFoundError: If the item is not stored.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, or ``tag`` neither a
                ``Tag`` nor a ``UUID``.
        """
        item_id = item_id_of(item)
        tag_id = tag_id_of(tag)
        if self._service.repository.find_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        self._require_stored(item_id)
        self._service.repository.add_item_tag_link(item_id, tag_id)
        self._cache.clear()

    def untag(self, item: ItemRef, tag: TagRef) -> None:
        """Remove a tag from an item. Idempotent.

        Args:
            item: The item to untag, or its identifier: **the item comes first**.
            tag: The tag to remove, or its identifier.

        Raises:
            TaxomeshTagNotFoundError: If the tag is not stored. Checked first, as in :meth:`tag`.
            TaxomeshItemNotFoundError: If the item is not stored.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, or ``tag`` neither a
                ``Tag`` nor a ``UUID``.
        """
        item_id = item_id_of(item)
        tag_id = tag_id_of(tag)
        if self._service.repository.find_tag(tag_id) is None:
            raise TaxomeshTagNotFoundError(f"Tag not found: {tag_id}")
        self._require_stored(item_id)
        self._service.repository.delete_item_tag_link(item_id, tag_id)
        self._cache.clear()

    def relate(
        self,
        source: ItemRef,
        target: ItemRef,
        relation_type: str,
        *,
        sort_index: int = 0,
        # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
        metadata: dict[str, Any] | None = None,
    ) -> ItemRelationLink:
        """Relate one item to another, in one direction.

        To relate the same source, target and relation type again updates the sort index and the
        metadata of that relation, and does not add a second one.

        Args:
            source: The item that the relation goes from, or its identifier.
            target: The item that the relation goes to, or its identifier.
            relation_type: The caller's own name for the kind of relation, such as
                ``"related_to"``. taxomesh stores it stripped and lowercased, and gives it no
                meaning.
            sort_index: The position among the relations of that source.
            metadata: Optional data of your own, stored with the relation.

        Returns:
            The new or updated ``ItemRelationLink``.

        Raises:
            TaxomeshItemNotFoundError: If either item is not stored.
            TaxomeshRelationError: If the relation is invalid, such as an item related to itself
                or a blank relation type.
            TaxomeshValidationError: If the model refuses another value, such as a relation type
                over its maximum length, or ``metadata`` is not plain JSON.
            TypeError: If ``source`` or ``target`` is neither an ``Item`` nor a ``UUID``, or
                another argument is of a type the link does not take, such as a relation type that
                is not text. Each is refused before anything is read.
        """
        source_item_id = item_id_of(source)
        target_item_id = item_id_of(target)
        _require_plain_json(metadata)
        with _as_validation_error():
            link = ItemRelationLink(
                source_item_id=source_item_id,
                target_item_id=target_item_id,
                relation_type=relation_type,
                sort_index=sort_index,
                metadata=metadata if metadata is not None else {},
            )
        self._require_stored(source_item_id)
        self._require_stored(target_item_id)
        self._service.repository.save_item_relation_link(link)
        self._cache.clear()
        return link

    def unrelate(self, source: ItemRef, target: ItemRef, relation_type: str) -> None:
        """Remove one directed relation between two items.

        A no-op when that relation is not stored.

        Args:
            source: The item that the relation goes from, or its identifier.
            target: The item that the relation goes to, or its identifier.
            relation_type: The type of the relation to remove. Case and surrounding whitespace
                are ignored.

        Raises:
            TaxomeshItemNotFoundError: If either item is not stored.
            TypeError: If ``source`` or ``target`` is neither an ``Item`` nor a ``UUID``, or
                ``relation_type`` is not a ``str``.
        """
        source_item_id = item_id_of(source)
        target_item_id = item_id_of(target)
        _require_text("relation_type", relation_type)
        normalised = relation_type.strip().lower()
        if self._service.repository.delete_item_relation_link(source_item_id, target_item_id, normalised):
            self._cache.clear()
            return
        # A stored link names only stored items, so the two items are looked up only when no
        # link was deleted.
        for item_id in (source_item_id, target_item_id):
            self._require_stored(item_id)

    def list_relations(
        self,
        item: ItemRef,
        *,
        relation_types: str | Collection[str] | None = None,
        direction: Direction | Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> Sequence[ItemRelationLink]:
        """Return the relations of an item: the links themselves, not the items at their other end.

        Args:
            item: The item whose relations to return, or its identifier.
            relation_types: When it is given, only the relations of this type or of these types.
                Case and surrounding whitespace are ignored; ``None`` or an empty collection means
                every type.
            direction: ``"outgoing"`` (the default) where the item is the source, ``"incoming"``
                where it is the target, ``"both"`` for either, each link at most once. A relation
                stored in both directions is two links, so ``"both"`` returns both. A
                :class:`~taxomesh.domain.types.Direction` member is taken as its value.

        Returns:
            The matching relations, empty when there are none.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
            TaxomeshValidationError: If ``direction`` is text naming no direction.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, a relation type is not a
                ``str``, or ``direction`` is not text.
        """
        return self._relations(
            item_id_of(item), _normalise_relation_types(relation_types), _direction(direction).value
        )

    @memoize
    def _relations(
        self,
        item_id: UUID,
        relation_types: tuple[str, ...] | None,
        direction: Literal["outgoing", "incoming", "both"],
        /,
    ) -> Sequence[ItemRelationLink]:
        """The cached read behind :meth:`list_relations`, keyed by the normalised arguments.

        A stored link names only stored items, so the item is looked up only when the read
        returns no link, and through the cache of single items.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
        """
        links = tuple(
            self._service.repository.list_item_relation_links(
                item_id, relation_types=relation_types, direction=direction
            )
        )
        if not links:
            self[item_id]
        return links

    def list_related(
        self,
        item: ItemRef,
        *,
        relation_types: str | Collection[str] | None = None,
        direction: Direction | Literal["outgoing", "incoming", "both"] = "outgoing",
        enabled: bool | None = True,
    ) -> Sequence[Item]:
        """Return the items on the other end of an item's relations.

        The related items are read in one batch and filtered by ``enabled``, as a listing is. A
        relation whose other end is not stored is skipped, with a ``WARNING`` that names that end
        as absent. No state of a related row makes this method raise.

        Args:
            item: The item whose related items to return, or its identifier.
            relation_types: When it is given, only the relations of this type or of these types.
                Case and surrounding whitespace are ignored; ``None`` or an empty collection means
                every type.
            direction: ``"outgoing"`` (the default) returns the targets, ``"incoming"`` the
                sources, ``"both"`` the other end of every link of the item. A
                :class:`~taxomesh.domain.types.Direction` member is taken as its value.
            enabled: ``True`` (the default) enabled related items only, ``False`` disabled only,
                ``None`` all. The state of the queried item has no effect.

        Returns:
            The related items in link order, empty when there are none.

        Raises:
            TaxomeshItemNotFoundError: If the item is not stored.
            TaxomeshValidationError: If ``direction`` is text naming no direction.
            TypeError: If ``item`` is neither an ``Item`` nor a ``UUID``, a relation type is not a
                ``str``, ``direction`` is not text, or ``enabled`` is neither a ``bool`` nor ``None``.
        """
        _require_enabled(enabled)
        return self._related(
            item_id_of(item), _normalise_relation_types(relation_types), _direction(direction).value, enabled
        )

    @memoize
    def _related(
        self,
        item_id: UUID,
        relation_types: tuple[str, ...] | None,
        direction: Literal["outgoing", "incoming", "both"],
        enabled: bool | None,
        /,
    ) -> Sequence[Item]:
        """The cached read behind :meth:`list_related`, keyed by the normalised arguments."""
        links = self._relations(item_id, relation_types, direction)
        if not links:
            return ()
        # The other end of each link, whether that end is the link's target, and the link's type.
        # In "both", the other end is the end that is not the queried item.
        far: list[tuple[UUID, bool, str]] = []
        for lnk in links:
            is_target = lnk.source_item_id == item_id if direction == "both" else direction == "outgoing"
            far.append((lnk.target_item_id if is_target else lnk.source_item_id, is_target, lnk.relation_type))
        # Read in ONE batch, with no filter, and with the queried item, so that a warning can name
        # it: a disabled row must stay different from a row that is not stored.
        item_map = self._service.repository.map_items_by_id({end for end, _, _ in far} | {item_id}, enabled=None)
        result: list[Item] = []
        for related_id, is_target, relation_type in far:
            found = item_map.get(related_id)
            if found is None:
                if logger.isEnabledFor(logging.WARNING):
                    _log_absent_end("list_related", item_map, item_id, related_id, relation_type, is_target)
                continue
            if enabled is None or found.enabled == enabled:
                result.append(found)
        return tuple(result)

    def get_many_related(
        self,
        items: ItemRef | Collection[ItemRef],
        /,
        *,
        relation_types: str | Collection[str] | None = None,
        direction: Direction | Literal["outgoing", "incoming", "both"] = "outgoing",
        enabled: bool | None = True,
    ) -> Mapping[UUID, RelatedItems]:
        """Return the related items for many items at once, in two storage reads.

        One batch read of the links and one batch read of the items, in every direction and for
        any number of identifiers: never one read for each item. The related items are filtered
        by ``enabled``, as a listing is. A relation whose other end is not stored is skipped, with
        a ``WARNING`` that names that end as absent. No state of a related row makes this method
        raise.

        Args:
            items: The queried item or its identifier, or a collection of them. The order and the
                duplicates have no effect.
            relation_types: When it is given, only the relations of this type or of these types.
                Case and surrounding whitespace are ignored; ``None`` or an empty collection means
                every type.
            direction: ``"outgoing"`` (the default) returns the items that these relate to,
                ``"incoming"`` the items that relate to these, ``"both"`` the two together. A
                :class:`~taxomesh.domain.types.Direction` member is taken as its value.
            enabled: ``True`` (the default) enabled related items only, ``False`` disabled only,
                ``None`` all. The state of the queried items has no effect.

        Returns:
            A mapping of queried item identifier to its :class:`RelatedItems`. A queried item
            with no matching relation is absent, and a queried item that is not stored is absent
            too: these are keys asked about, not subjects. In one relation type, ``"outgoing"``
            items are ordered by ``(sort_index, target identifier)``, ``"incoming"`` items by
            ``(sort_index, source identifier)``, and ``"both"`` lists first the items that the
            outgoing links give.

        Raises:
            TaxomeshValidationError: If ``direction`` is text naming no direction.
            TypeError: If ``items`` is neither one item nor a collection, a queried item is neither
                an ``Item`` nor a ``UUID``, a relation type is not a ``str``, ``direction`` is not
                text, or ``enabled`` is neither a ``bool`` nor ``None``. Each is refused even when
                no item is asked about.

        Example::

            found = service.items.get_many_related([item_a])
            found[item_a.item_id].of_type("related_to")  # (item_b,)

        Note:
            Calls share one cache entry when they differ only in the order of the identifiers, the
            duplicates, an item or its identifier, one value or a collection that holds it, or
            the case and the whitespace of a relation type; ``direction`` and ``enabled`` are part
            of the key. The mapping and each ``by_type`` are new on every call, and each group is a
            tuple of frozen rows, so a change that one caller makes reaches no other call.
        """
        _require_enabled(enabled)
        normalised_types = _normalise_relation_types(relation_types)
        direction_value: Literal["outgoing", "incoming", "both"] = _direction(direction).value
        keys = (items,) if isinstance(items, (Item, UUID)) else items
        _require_collection("items", keys)
        unique_ids = frozenset(item_id_of(item) for item in keys)
        if not unique_ids:
            return {}
        found = self._fetch_related(
            unique_ids,
            relation_types=normalised_types,
            enabled=enabled,
            direction=direction_value,
        )
        return {item_id: RelatedItems(item_id=item_id, by_type=dict(by_type)) for item_id, by_type in found.items()}

    @memoize
    def _fetch_related(
        self,
        item_ids: frozenset[UUID],
        *,
        relation_types: tuple[str, ...] | None,
        enabled: bool | None,
        direction: Literal["outgoing", "incoming", "both"],
    ) -> dict[UUID, dict[str, tuple[Item, ...]]]:
        """The cached read behind :meth:`get_many_related`, keyed by the normalised arguments.

        Reads every direction with **one** batch read of the links
        (:meth:`list_item_relation_links_batch`) and one batch read of the items: two repository
        calls in all, ``"both"`` included. Each entry is
        ``(group_key_id, related_id, relation_type, sort_index, related_is_target)``, where
        ``group_key_id`` is the queried end (the key of the outer dict) and ``related_id`` is the
        end whose row is returned. For ``"both"``, the entries are sorted again, so that each group
        lists first the items that the outgoing links give, then those that the incoming links
        give.
        """
        links = self._service.repository.list_item_relation_links_batch(
            item_ids, direction=direction, relation_types=relation_types
        )
        if not links:
            return {}
        entries: list[tuple[UUID, UUID, str, int, bool]] = []
        needed_ids: set[UUID] = set()
        # One loop for every direction. The check that an end is a queried item tells the two
        # cases of "both" apart: a link can match at either end or at both. For "outgoing" and
        # "incoming", the repository already filtered the links, so the check is always true.
        for link in links:
            if direction in ("outgoing", "both") and link.source_item_id in item_ids:
                entries.append((link.source_item_id, link.target_item_id, link.relation_type, link.sort_index, True))
                needed_ids.update((link.source_item_id, link.target_item_id))
            if direction in ("incoming", "both") and link.target_item_id in item_ids:
                entries.append((link.target_item_id, link.source_item_id, link.relation_type, link.sort_index, False))
                needed_ids.update((link.target_item_id, link.source_item_id))
        if direction == "both":
            # One read returns the links of both directions in one order. Sort again, so that each
            # (group, relation_type) lists the items of the outgoing links (related_is_target is
            # True, so they sort first) before those of the incoming links.
            entries.sort(key=lambda e: (e[0], e[2], not e[4], e[3], e[1]))
        # With no filter, so a disabled row stays different from a row that is not stored.
        item_map: Mapping[UUID, Item] = self._service.repository.map_items_by_id(needed_ids, enabled=None)
        result: dict[UUID, dict[str, list[Item]]] = {}
        for group_key_id, related_id, relation_type, _sort_index, related_is_target in entries:
            found = item_map.get(related_id)
            if found is None:
                if logger.isEnabledFor(logging.WARNING):
                    _log_absent_end(
                        "get_many_related", item_map, group_key_id, related_id, relation_type, related_is_target
                    )
                continue
            if enabled is None or found.enabled == enabled:
                result.setdefault(group_key_id, {}).setdefault(relation_type, []).append(found)
        return {key: {kind: tuple(group) for kind, group in groups.items()} for key, groups in result.items()}


def _normalise_relation_types(relation_types: str | Collection[str] | None) -> tuple[str, ...] | None:
    """Strip each type and put it in lowercase, as ``relate`` stores it, and make one sorted, hashable key.

    One string is one type. ``None`` and an empty collection both mean every type, and both come
    back as ``None``; ``""`` is one type, which no relation has.

    Raises:
        TypeError: If ``relation_types`` is neither a string nor a collection, or a type in it is
            not a ``str``.
    """
    if relation_types is None:
        return None
    if isinstance(relation_types, str):
        return (relation_types.strip().lower(),)
    _require_collection("relation_types", relation_types)
    types = tuple(relation_types)
    for relation_type in types:
        if not isinstance(relation_type, str):
            raise TypeError(f"relation_types must hold only str values, not {type(relation_type).__name__}")
    return tuple(sorted({t.strip().lower() for t in types})) or None


def _direction(direction: object, /) -> Direction:
    """Return the direction a relation read was given: a :class:`Direction` or its text.

    Raises:
        TypeError: If ``direction`` is not text.
        TaxomeshValidationError: If it is text naming no direction.
    """
    if not isinstance(direction, str):
        raise TypeError(f"direction must be a Direction or its text, not {type(direction).__name__}")
    try:
        return Direction(direction)
    except ValueError:
        names = ", ".join(repr(member.value) for member in Direction)
        raise TaxomeshValidationError(f"direction must be one of {names}, not {direction!r}") from None


def _log_absent_end(
    read: str,
    item_map: Mapping[UUID, Item],
    present_id: UUID,
    absent_id: UUID,
    relation_type: str,
    absent_is_target: bool,
) -> None:
    """Log the WARNING for a relation that is skipped because its other end is not stored.

    *present_id* is the queried end, and *absent_id* the end that names no stored item. The roles
    come from the link itself, source or target, so the message is correct in every direction.
    """
    present_role = "source" if absent_is_target else "target"
    absent_role = "target" if absent_is_target else "source"
    present_item = item_map.get(present_id)
    if present_item is None:
        present_repr = f"<absent {present_role} item {present_id}>"
    else:
        try:
            present_repr = str(present_item)
        except Exception:
            present_repr = f"<item {present_id} str() failed>"
    logger.warning(
        f"{read}: relation skipped, its {absent_role} item %s is absent — {present_role}: %s, relation_type: %r",
        absent_id,
        present_repr,
        relation_type,
    )
