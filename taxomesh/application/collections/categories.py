"""The ``service.categories`` collection."""

from __future__ import annotations

import builtins
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID, uuid4

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
from taxomesh.domain.constants import DEFAULT_CATEGORY_EXTERNAL_ID, ROOT_CATEGORY_NAME
from taxomesh.domain.dag import check_no_cycle
from taxomesh.domain.models import Category, CategoryParentLink
from taxomesh.domain.refs import CategoryRef, ItemRef, category_id_of, item_id_of
from taxomesh.domain.types import UNSET, ExternalId, UnsetType, normalise_external_id
from taxomesh.exceptions import (
    TaxomeshCategoryNotFoundError,
    TaxomeshCyclicDependencyError,
    TaxomeshDuplicateSlugError,
    TaxomeshExternalIdConflictError,
    TaxomeshNotFoundError,
    TaxomeshRootCategoryError,
    TaxomeshValidationError,
)
from taxomesh.utils.memoize import Miss, ReadCache, memoize

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for type checking only
    from taxomesh.application.service import TaxomeshService


class CategoryCollection(EntityCollectionBase[Category, CategoryRef]):
    """Categories, reached as a container on the service.

    The category reads and writes are here: subscript and the other lookups, the count,
    listing, search, creation, update, deletion and parent links.

    Reached as ``service.categories`` and never constructed directly: every memoized read below
    keeps its entries in the service's cache, which the service gives to this collection when it
    builds it.
    """

    _not_found: ClassVar[type[TaxomeshNotFoundError]] = TaxomeshCategoryNotFoundError
    _namespace: ClassVar[str] = "categories"

    def __init__(
        self, service: TaxomeshService, *, cache: ReadCache, root_id: UUID, corpus: SearchCorpus[Category]
    ) -> None:
        """Bind the collection to its service and to the state that service owns.

        Args:
            service: The owning service.
            cache: The service's cache, which holds the memoized reads below.
            root_id: The identifier of the implicit root, which the service finds once.
            corpus: The category search corpus. The service holds it; this collection fills it on
                search and drops it whenever it creates, updates or deletes a category.
        """
        super().__init__(service, cache=cache)
        self._root_id = root_id
        self._corpus = corpus

    def _is_root(self, category_id: UUID, /) -> bool:
        """Return whether this identifier is the identifier of the implicit root.

        No member returns the implicit root, and no member places an item in it: every member of this
        collection and of the item collection that takes a category treats this identifier as that
        of a category that is not stored. Subscript, :meth:`_require_stored` and every member that
        returns a category call this method. The graph's assembler (``TaxomeshService.graph``)
        makes its own comparison.

        Args:
            category_id: The identifier to test.

        Returns:
            ``True`` when this is the implicit root.
        """
        return category_id == self._root_id

    def _require_stored(self, category_id: UUID, /) -> Category:
        """Return the stored category a write names, refusing the implicit root.

        Reads storage directly, and not through the cache, because a write checks, and builds on,
        what it is about to change: a row that another service changed or deleted after this
        service read it is seen as it is stored.

        Args:
            category_id: The identifier that a write names.

        Returns:
            The stored ``Category``.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with this identifier is stored, or if
                it is the identifier of the implicit root, which is not a row in this container.
        """
        found = None if self._is_root(category_id) else self._service.repository.find_category(category_id)
        if found is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return found

    @staticmethod
    def _require_unreserved(name: str, /) -> None:
        """Refuse the reserved name of the implicit root, on create and on rename.

        The service finds the implicit root by this name (``_ensure_root``). If a caller's category
        had the name, the next service built over the same store could take that category as the
        implicit root: no member would return the category, and members would return the real
        implicit root as a row. The check reads the name of the built row, as the model decoded
        it, so ``b"__root__"`` is refused too.

        Args:
            name: The name of a built category row.

        Raises:
            TaxomeshRootCategoryError: If the name is the reserved name of the implicit root.
        """
        if name == ROOT_CATEGORY_NAME:
            raise TaxomeshRootCategoryError(f"Category name '{ROOT_CATEGORY_NAME}' is reserved for the implicit root")

    def __getitem__(self, key: CategoryRef, /) -> Category:
        """Return the category this names, or raise.

        Args:
            key: The category, or its identifier. Only the identifier is read.

        Returns:
            The stored ``Category``.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with this identifier is stored, or if
                the identifier is that of the implicit root, which is not a row in this container.
            TypeError: If ``key`` is neither a ``Category`` nor a ``UUID``.
        """
        category_id = category_id_of(key)
        if self._is_root(category_id):
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return self._lookup(category_id)

    @memoize
    def _lookup(self, category_id: UUID, /) -> Category:
        """Read one category through the cache: the entry that every listing primes.

        The one cached read of a single row behind subscript, ``get`` and ``in``, and the one that
        :meth:`_resolve_categories` reads and primes. It is positional-only on purpose: ``memoize``
        builds the key from the arguments as the call passes them, so a keyword call would build
        a different key and miss every primed entry.

        Args:
            category_id: The identifier of the category.

        Returns:
            The stored ``Category``.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with this identifier is stored.
        """
        result = self._service.repository.find_category(category_id)
        if result is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return result

    def _all(self) -> Sequence[Category]:
        """Return every stored category except the implicit root: the rows that ``len`` counts.

        It applies no ``enabled`` filter, so the count agrees with ``in``. The implicit root is the
        one row that it does not count, because it is the one stored row for which ``in`` answers
        ``False``.
        """
        return tuple(
            row for row in self._service.repository.list_categories(enabled=None) if not self._is_root(row.category_id)
        )

    def get_many(
        self,
        categories: CategoryRef | Collection[CategoryRef],
        /,
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Category]:
        """Return the categories these name, keyed by identifier.

        Args:
            categories: The category or identifier to look up, or a collection of them. An absent
                key is left out of the result: it does not raise, and it does not appear with a
                ``None`` value. The identifier of the implicit root is an absent key here, and
                subscript raises not-found for it.
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` (the default) all.
                The default agrees with subscript and :meth:`get`, which do not filter.

        Returns:
            A mapping of category identifier to ``Category``, with only the categories that were
            found. An empty request is answered without a storage read. The answer is cached, and
            calls that name the same categories share one entry, in any order and with any repeats.

        Raises:
            TypeError: If ``categories`` is neither one key nor a collection, a key is neither a
                ``Category`` nor a ``UUID``, or ``enabled`` is neither a ``bool`` nor ``None``.
        """
        _require_enabled(enabled)
        keys = (categories,) if isinstance(categories, (Category, UUID)) else categories
        _require_collection("categories", keys)
        category_ids = frozenset(category_id_of(category) for category in keys)
        if not category_ids:
            return {}
        found = self._fetch(category_ids, enabled)
        return {k: v for k, v in found.items() if not self._is_root(k)}

    @memoize
    def _fetch(self, category_ids: frozenset[UUID], enabled: bool | None, /) -> dict[UUID, Category]:
        """The cached read behind :meth:`get_many`, keyed by the set of identifiers."""
        return dict(self._service.repository.map_categories_by_id(category_ids, enabled=enabled))

    def _top_level_link(self, category_id: UUID, /) -> CategoryParentLink:
        """Return the link that puts a category at the top level, as :meth:`create` stores it.

        A category holds this link exactly when it holds no other parent link, so every write that
        takes a category's last parent stores it again.
        """
        return CategoryParentLink(category_id=category_id, parent_category_id=self._root_id, sort_index=0)

    def delete(self, key: CategoryRef, /) -> None:
        """Delete a category, with its links to its parents and its children and its placements.

        The items that were placed in it, and the categories under it, are not deleted. A child
        left with no other parent moves to the top level, in the same write.

        Args:
            key: The category to delete, or its identifier.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with this identifier is stored, or if the
                identifier is that of the implicit root, which is not a row in this container.
            TypeError: If ``key`` is neither a ``Category`` nor a ``UUID``.
        """
        category_id = category_id_of(key)
        if self._is_root(category_id):
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        repository = self._service.repository
        with self._atomic(then=self._corpus.invalidate):
            # Read before the delete, which deletes these links too.
            children = [
                lnk.category_id for lnk in repository.list_category_parent_links(parent_category_ids=[category_id])
            ]
            if not repository.delete_category(category_id):
                raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
            if children:
                parented = {lnk.category_id for lnk in repository.list_category_parent_links(category_ids=children)}
                for child_id in children:
                    if child_id not in parented:
                        repository.save_category_parent_link(self._top_level_link(child_id))

    def get_by_slug(self, slug: str, /) -> Category | None:
        """Return the category with this slug, or ``None``.

        Args:
            slug: The slug: a text key for URLs, unique among categories.

        Returns:
            The matching ``Category``, or ``None`` when no category has this slug. An empty slug
            is no slug: it answers ``None`` without a storage read, however many categories were
            created without one. The implicit root is never returned.

        Raises:
            TypeError: If ``slug`` is not a ``str``.
        """
        _require_text("slug", slug)
        if not slug:
            return None
        return self._by_slug(slug)

    @memoize
    def _by_slug(self, slug: str, /) -> Category | None:
        """The cached read behind :meth:`get_by_slug`, for a slug that is not empty."""
        result = self._service.repository.find_category_by_slug(slug)
        if result is None or self._is_root(result.category_id):
            return None
        return result

    def get_by_external_id(self, external_id: ExternalId, /) -> Category | None:
        """Return the category with this external id, or ``None``.

        Answers ``None`` for an external id of ``None`` without a storage read. The implicit root
        is never returned. The external id is converted to its stored form before the cached
        read, so ``42`` and ``"42"`` share one cache entry.

        Args:
            external_id: The external id: text, an integer or a UUID. Values with the same string
                form name the same row.

        Returns:
            The matching ``Category``, or ``None`` when no category has this external id.

        Raises:
            TypeError: If ``external_id`` is not text, an integer, a UUID or ``None``.
            TaxomeshRepositoryError: If the repository raises it.
        """
        normalised = normalise_external_id(external_id)
        if normalised is None:
            return None
        return self._by_external_id(normalised)

    @memoize
    def _by_external_id(self, external_id: str, /) -> Category | None:
        """The cached read behind :meth:`get_by_external_id`, keyed by the stored form."""
        found = self._service.repository.find_category_by_external_id(external_id)
        if found is None or self._is_root(found.category_id):
            return None
        return found

    def get_many_by_external_id(
        self,
        external_ids: ExternalId | Collection[ExternalId],
        /,
        *,
        enabled: bool | None = None,
    ) -> Mapping[str, Category]:
        """Return the categories for these external ids, keyed by external id.

        Each value is converted to its stored text by the rule that writes use, and by nothing
        else: the surrounding whitespace and the empty string are kept, as a write keeps them.
        ``None`` is left out and a duplicate counts once, so calls that differ only in these
        respects share one cache entry. The implicit root is never in the result.

        Args:
            external_ids: The external id to look up, or a collection of them. Text, integers and
                UUIDs can be mixed: values with the same string form name the same row, and a
                ``None`` adds nothing. An absent external id is left out of the result.
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` (the default) all.

        Returns:
            A mapping of external id, as stored, to ``Category``, with only the categories that
            were found.

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
        found = self._fetch_by_external_ids(normalised, enabled=enabled)
        return {k: v for k, v in found.items() if not self._is_root(v.category_id)}

    @memoize
    def _fetch_by_external_ids(
        self,
        external_ids: frozenset[str],
        *,
        enabled: bool | None = None,
    ) -> dict[str, Category]:
        """The cached read behind :meth:`get_many_by_external_id`, keyed by the set of stored external ids."""
        return dict(self._service.repository.map_categories_by_external_id(external_ids, enabled=enabled))

    def list(
        self,
        *,
        parent: CategoryRef | None = None,
        item: ItemRef | None = None,
        enabled: bool | None = True,
    ) -> Sequence[Category]:
        """Return categories: every one, or the children of a parent, or those an item is placed in.

        Each row is primed into the cache of single rows, whatever the filter, so a category
        returned here costs no read when it is next checked through that cache: by subscript,
        ``get`` or ``in``, or as a filter or a location that a member checks by subscript. This
        method's ``parent`` is one of them, and a tree walk passes it at every level.
        :meth:`get_many`, and the members that read a stored row directly, read the row again. A
        filtered call takes the rows that the cache holds and reads the rest in one batch; an
        unfiltered call reads every row, and primes what it read.

        Args:
            parent: When given, this parent's children, ordered by sort index. The category or
                its identifier.
            item: When given, the categories this item is placed in, ordered by the sort index
                of each placement. The item or its identifier.
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.

        Returns:
            The matching categories, empty when there are none. With neither ``parent`` nor
            ``item``, every stored category that the ``enabled`` filter keeps (the enabled ones,
            by default), in no promised order: ``sort_index`` orders a category under one parent,
            and an unfiltered listing has no parent.

        Raises:
            TaxomeshValidationError: If both ``parent`` and ``item`` are given. They need
                different reads, so the method cannot apply both, and to apply only one, with no
                error, would ignore an argument that the caller gave.
            TaxomeshCategoryNotFoundError: If ``parent`` is given and names a category that is not
                stored, or the implicit root, or if a parent link or a placement names a category
                that is not stored.
            TaxomeshItemNotFoundError: If ``item`` is given and names an item that is not stored.
            TypeError: If ``parent`` is neither a ``Category`` nor a ``UUID``, ``item`` neither an
                ``Item`` nor a ``UUID``, or ``enabled`` neither a ``bool`` nor ``None``.

        Note:
            The implicit root is never returned, with any filter: it is not a row in this
            container (:meth:`_is_root`). :meth:`roots` lists the top level.
        """
        _require_enabled(enabled)
        parent_id = None if parent is None else category_id_of(parent)
        item_id = None if item is None else item_id_of(item)
        if parent_id is not None and item_id is not None:
            raise TaxomeshValidationError("Pass parent or item, not both")
        return self._listing(parent_id, item_id, enabled)

    @memoize
    def _listing(self, parent_id: UUID | None, item_id: UUID | None, enabled: bool | None, /) -> Sequence[Category]:
        """The cached read behind :meth:`list`, keyed by identifiers."""
        if item_id is not None:
            self._service.items[item_id]
            # The links of one item come ordered by category_id. This STABLE sort by sort_index
            # gives the order that callers see: sort_index, then category_id. Without it, the
            # order of the ties would change, and no error would show it.
            placements = sorted(
                self._service.repository.list_item_parent_links(item_ids=[item_id]),
                key=lambda lnk: lnk.sort_index,
            )
            # Stored data can place an item in the implicit root, and that placement is not a
            # category that the caller placed it in. It is left out before the rows are read, so
            # it is not primed either.
            ordered_ids = [lnk.category_id for lnk in placements if not self._is_root(lnk.category_id)]
        elif parent_id is not None:
            self[parent_id]
            ordered_ids = self._child_ids(parent_id)
        else:
            return self._every_category(enabled=enabled)
        return self._in_order(ordered_ids, enabled=enabled)

    def _child_ids(self, parent_id: UUID, /) -> builtins.list[UUID]:
        """Return the identifiers of a parent's children, ordered by sort index.

        It does not check the parent: :meth:`list` checks it first, and :meth:`roots` passes the
        implicit root, which the check refuses.
        """
        children = sorted(
            self._service.repository.list_category_parent_links(parent_category_ids=[parent_id]),
            key=lambda lnk: lnk.sort_index,
        )
        return [lnk.category_id for lnk in children]

    def _in_order(self, ordered_ids: builtins.list[UUID], /, *, enabled: bool | None) -> Sequence[Category]:
        """Read the row of each identifier, keep their order, and apply the ``enabled`` filter.

        The rows come from the cache of single rows, and the rows that the cache does not hold
        come from one batch read. They are primed before the ``enabled`` filter, so the cached row
        is the stored row: a caller that later asks by identifier for a category that the filter
        left out still gets it.

        Raises:
            TaxomeshCategoryNotFoundError: If an identifier names no stored row.
        """
        if not ordered_ids:
            return ()
        category_map = self._resolve_categories(set(ordered_ids))
        cats: builtins.list[Category] = []
        for category_id in ordered_ids:
            found = category_map.get(category_id)
            if found is None:
                raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
            cats.append(found)
        return tuple(c for c in cats if enabled is None or c.enabled == enabled)

    def _every_category(self, *, enabled: bool | None) -> Sequence[Category]:
        """Return every stored category except the implicit root, priming each row it returns.

        The unfiltered path of :meth:`list`. It makes one read, which returns whole rows, so they
        are primed into the cache of :meth:`_lookup` as the filtered paths prime the rows that
        they read. The read has no filter, and the ``enabled`` filter is applied here, not in the
        read: a primed row must be the stored row, so that a caller that later asks by identifier
        for a category that the filter left out still gets it. :meth:`_resolve_categories` keeps
        the same rule. The cost is that a SQL backend cannot apply the filter in its query.

        Args:
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` all.

        Returns:
            Every category except the implicit root, after the ``enabled`` filter, in the order
            that the repository listed them.
        """
        rows = self._all()
        accessor = self._lookup
        for row in rows:
            accessor.prime(row, row.category_id)
        return tuple(row for row in rows if enabled is None or row.enabled == enabled)

    def _resolve_categories(self, category_ids: set[UUID]) -> dict[UUID, Category]:
        """Read category rows through the cache of :meth:`_lookup`, and read from storage only the misses.

        The port's batch read is not memoized, so this method gives it the two things that a
        memoized read would give:

        * **Read-through.** An identifier that the cache holds is served from it. One batch read
          gets the rest, so a call with an empty cache makes exactly one, and a call with no miss
          makes none.
        * **Priming.** Each row that the batch read returns primes the entry that :meth:`_lookup`
          reads, so a row returned as a *result* is a cache hit when it is next passed as an
          *argument*. A tree walk depends on this: each child becomes the ``parent`` of the next
          call.

        Only the rows that the batch read returns are primed. A row served from the cache keeps
        its first timestamp, so repeated reads cannot extend the lifetime of an entry; the lifetime
        stays measured from the read. The entries written here are the same as those that
        :meth:`_lookup` would write itself, and every write clears both.

        This method and the method that it primes use the same cache: this collection's, which is
        its service's. The code depends on it: primed into another cache, each entry would be
        written where the lookup never reads, so priming would save no read, and no test that
        checks values would fail.

        It is for categories only: the cache has no size bound and item rows are large, so the
        item listings neither read through the cache nor prime it.

        Args:
            category_ids: The identifiers to read.

        Returns:
            The rows found, keyed by identifier, with no ``enabled`` filter: a disabled row must
            stay different from a deleted one, because the callers raise for an absent key. An
            identifier with no stored row is not in the result.
        """
        accessor = self._lookup
        found: dict[UUID, Category] = {}
        missing: set[UUID] = set()
        for category_id in category_ids:
            hit = accessor.cached(category_id)
            if isinstance(hit, Miss):
                missing.add(category_id)
            else:
                found[category_id] = hit
        if missing:
            fetched = self._service.repository.map_categories_by_id(missing, enabled=None)
            for category_id, category in fetched.items():
                accessor.prime(category, category_id)
            found.update(fetched)
        return found

    def roots(self, *, enabled: bool | None = True) -> Sequence[Category]:
        """Return the top level: the categories that have no parent.

        The same categories, in the same order, as ``service.graph(enabled=enabled).roots``. Each
        row is primed into the cache of single rows, as :meth:`list` primes it.

        Args:
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.

        Returns:
            The top-level categories, ordered by sort index.

        Raises:
            TaxomeshCategoryNotFoundError: If a link to the top level names a category that is not
                stored, which only a direct repository write can leave.
            TypeError: If ``enabled`` is neither a ``bool`` nor ``None``.

        Note:
            A category whose parents the ``enabled`` filter all leaves out still has them, so it
            is not listed here.
        """
        _require_enabled(enabled)
        return self._roots(enabled)

    @memoize
    def _roots(self, enabled: bool | None, /) -> Sequence[Category]:
        """The cached read behind :meth:`roots`, called after the filter is checked."""
        return self._in_order(self._child_ids(self._root_id), enabled=enabled)

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        parent: CategoryRef | None = None,
        enabled: bool | None = True,
        fuzzy: bool = True,
    ) -> Sequence[Category]:
        """Return categories matching a query, best match first.

        Without ``parent``, the candidates come from a corpus whose fields are normalized once.
        The service holds the corpus for ``cache_ttl``, or until it next creates, updates or
        deletes a category. With ``parent``, the candidates are the children of that parent, read
        from the cached listing. The implicit root is never a candidate.

        Args:
            query: The text to match against the name, the slug and the external id.
            limit: The maximum number of results; at least 1.
            parent: When it is given, the search covers only the direct children of this parent.
                The category or its identifier.
            enabled: ``True`` (the default) enabled only, ``False`` disabled only, ``None`` all.
            fuzzy: Whether to add approximate matching to the exact, prefix and substring matching.

        Returns:
            The matching categories, ranked by descending score, empty when nothing matches.

        Raises:
            TaxomeshValidationError: If ``limit`` is less than 1.
            TaxomeshCategoryNotFoundError: If ``parent`` is given and names a category that is not
                stored, or the implicit root; or if the query is not blank, ``parent`` is given,
                and a link to one of its children names a category that is not stored, as
                :meth:`list` raises.
            TypeError: If ``query`` is not a ``str``, ``limit`` not an ``int``, ``parent``
                neither a ``Category`` nor a ``UUID``, or ``enabled`` neither a ``bool`` nor ``None``.
        """
        _require_text("query", query)
        _require_enabled(enabled)
        parent_id = None if parent is None else category_id_of(parent)
        _require_limit(limit)
        if not query.strip():
            # Nothing to match, but the filter still names a category: a filter that names no
            # stored category raises here, as it does for any other query.
            if parent_id is not None:
                self[parent_id]
            return ()

        engine = SearchEngine()
        norm_q = SearchEngine.normalize(query)
        if parent_id is None:
            corpus = self._get_category_corpus()
            filtered = [sc for sc in corpus if enabled is None or sc.obj.enabled == enabled]
            return engine._score_corpus(norm_q, filtered, fuzzy=fuzzy, limit=limit)
        candidates = self._listing(parent_id, None, enabled)
        return engine._score_and_rank(
            norm_q,
            candidates,
            get_name=lambda c: c.name,
            get_slug=lambda c: c.slug,
            get_ext=lambda c: c.external_id,
            fuzzy=fuzzy,
            limit=limit,
        )

    def _get_category_corpus(self) -> builtins.list[SearchCandidate[Category]]:
        """Build and hold the search candidates of every category, with their fields normalized.

        Returns the held corpus while it is held. Otherwise it reads every category from the
        repository, leaves out the implicit root, normalizes the fields of each candidate once,
        gives the result to the corpus that the service holds, and returns it. The corpus keeps
        it for the cache's lifetime; a create, update or delete of a category here drops it
        sooner.

        Returns:
            One ``SearchCandidate`` for each category except the implicit root.
        """
        held = self._corpus.candidates
        if held is not None:
            return held
        return self._corpus.hold(
            [
                SearchCandidate(
                    obj=cat,
                    norm_name=SearchEngine.normalize(cat.name),
                    norm_slug=SearchEngine.normalize(cat.slug),
                    norm_ext=(SearchEngine.normalize(cat.external_id) if cat.external_id is not None else ""),
                )
                for cat in self._service.repository.list_categories(enabled=None)
                if not self._is_root(cat.category_id)
            ]
        )

    def create(
        self,
        name: str,
        *,
        description: str = "",
        slug: str = "",
        external_id: ExternalId = DEFAULT_CATEGORY_EXTERNAL_ID,
        # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
        metadata: dict[str, Any] | None = None,
    ) -> Category:
        """Create a category at the top level.

        Args:
            name: The name of the category.
            description: An optional longer description.
            slug: An optional slug: a text key for URLs, unique among categories.
            external_id: The optional external id, the key of your record; unique among
                categories when it is given. Text, an integer or a UUID: the string form is
                stored, so the value read back is a string even when an ``int`` or a ``UUID`` was
                given, and values with the same string form name the same row.
            metadata: Optional data of your own, stored with the category.

        Returns:
            The new ``Category``.

        Raises:
            TaxomeshDuplicateSlugError: If another category already has the slug.
            TaxomeshExternalIdConflictError: If another category already has the external id.
            TaxomeshRootCategoryError: If the name is the reserved name of the implicit root.
            TaxomeshValidationError: If the model refuses a value, such as a name over its maximum
                length, or ``metadata`` is not plain JSON: a mapping whose keys are text and whose
                values are text, finite numbers, booleans, ``None``, lists or tuples, and such
                dicts. A tuple is taken as a list, and an enum member as its value.
            TaxomeshRepositoryError: If storage fails while writing the category or its link to the
                top level.
            TypeError: If an argument is of a type the model does not take, ``description`` is
                ``None``, or ``external_id`` is not text, an integer, a UUID or ``None``.
        """
        if description is None:
            raise TypeError('description cannot be None: pass "" for no description')
        _require_plain_json(metadata)
        now = datetime.now(tz=UTC)
        with _as_validation_error():
            category = Category(
                category_id=uuid4(),
                name=name,
                description=description,
                slug=slug,
                metadata=metadata if metadata is not None else {},
                external_id=normalise_external_id(external_id),
                created_at=now,
                updated_at=now,
            )
        self._require_unreserved(category.name)
        if category.slug:
            existing = self._service.repository.find_category_by_slug(category.slug)
            if existing is not None:
                raise TaxomeshDuplicateSlugError(f"Slug '{category.slug}' is already used by another category")
        with self._atomic(then=self._corpus.invalidate):
            stored = self._service.repository.save_category(category)
            self._service.repository.save_category_parent_link(self._top_level_link(category.category_id))
        return stored

    def update(
        self,
        category: CategoryRef,
        *,
        name: str | UnsetType = UNSET,
        description: str | UnsetType = UNSET,
        slug: str | UnsetType = UNSET,
        external_id: ExternalId | UnsetType = UNSET,
        enabled: bool | UnsetType = UNSET,
        # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
        metadata: dict[str, Any] | UnsetType = UNSET,
        expected_version: int | None = None,
    ) -> Category:
        """Update a category, and keep every field that the call does not give.

        Every field defaults to ``UNSET``, which keeps it as it is, and any other value replaces
        it. ``None`` clears ``external_id``, the one nullable field, and is refused for the others.

        The repository replaces the row with a new one, which this method returns; a row that a
        caller already holds keeps the values it was read with. Every check comes before the save:
        the name against the reserved name of the implicit root, the slug and the external id
        against storage, and each new value against the model. The save checks the external id
        again, for what this check cannot see: a write by another caller between the check and
        the save, or another stored category that already has the external id that this category
        keeps. A refused update stores nothing.

        Args:
            category: The category to update, or its identifier. Only the identifier is read:
                the update applies to the stored row.
            name: The new name.
            description: The new description.
            slug: The new slug; ``""`` clears it.
            external_id: The new external id: text, an integer or a UUID, stored as its string
                form. ``None`` clears it.
            enabled: The new enabled state.
            metadata: The new metadata. It replaces the stored dict; it is not merged into it.
            expected_version: The ``version`` of the row that the caller read. When it is given,
                the update is made only if the stored row is still at that version; the repository
                compares and writes in one step. ``None`` (the default) makes no comparison.

        Returns:
            The updated ``Category`` as stored, its version one higher than the row it replaced.

        Raises:
            TaxomeshCategoryNotFoundError: If no category with this identifier is stored, or if the
                identifier is that of the implicit root, which is not a row in this container.
            TaxomeshRootCategoryError: If the new name is the reserved name of the implicit root.
            TaxomeshDuplicateSlugError: If another category already has the new slug.
            TaxomeshExternalIdConflictError: If another category already has the new external id,
                or the one that this category keeps.
            TaxomeshValidationError: If the model refuses a new value, such as a name over its
                maximum length, ``metadata`` is not plain JSON, or ``expected_version`` is below 0.
            TaxomeshVersionConflictError: If ``expected_version`` is given and the stored row is
                no longer at it.
            TypeError: If ``category`` is neither a ``Category`` nor a ``UUID``, a field other than
                ``external_id`` is ``None``, a new value is of a type the model does not take, or
                ``expected_version`` is neither an ``int`` nor ``None``.
        """
        category_id = category_id_of(category)
        _require_version(expected_version)
        changes = _given(
            {"name": name, "description": description, "slug": slug, "metadata": metadata, "enabled": enabled}
        )
        _require_plain_json(metadata)
        stored_row = self._require_stored(category_id)
        normalised = None if external_id is UNSET else normalise_external_id(external_id)
        if external_id is not UNSET:
            changes["external_id"] = normalised
        changes["updated_at"] = datetime.now(tz=UTC)
        row = _changed(stored_row, changes)
        if name is not UNSET:
            self._require_unreserved(row.name)
        if slug is not UNSET and row.slug:
            existing = self._service.repository.find_category_by_slug(row.slug)
            if existing is not None and existing.category_id != category_id:
                raise TaxomeshDuplicateSlugError(f"Slug '{row.slug}' is already used by another category")
        holder = None if normalised is None else self._service.repository.find_category_by_external_id(normalised)
        if holder is not None and holder.category_id != category_id:
            raise TaxomeshExternalIdConflictError(f"External id {normalised!r} is already used by another category")
        stored = self._service.repository.save_category(row, expected_version=expected_version)
        self._cache.clear()
        self._corpus.invalidate()
        return stored

    def add_parent(self, category: CategoryRef, parent: CategoryRef, *, sort_index: int = 0) -> CategoryParentLink:
        """Give a category an additional parent.

        A category with a parent is not at the top level, so a category that was at the top
        level leaves it, in the same ``atomic()`` block.

        Args:
            category: The category that gets a parent, or its identifier.
            parent: The category that becomes a parent, or its identifier.
            sort_index: The position among the children of that parent.

        Returns:
            The new ``CategoryParentLink``.

        Raises:
            TaxomeshCategoryNotFoundError: If either category is not stored, or if either
                identifier is that of the implicit root, which is not a row in this container.
            TaxomeshCyclicDependencyError: If the link would make a cycle. A category given as its
                own parent is one, and it is refused before either identifier is looked up.
            TaxomeshValidationError: If ``sort_index`` is a value the link refuses, such as text
                that is not a number.
            TypeError: If either is neither a ``Category`` nor a ``UUID``, or ``sort_index`` is of
                a type the link does not take. Both are refused before anything is read.
        """
        category_id = category_id_of(category)
        parent_id = category_id_of(parent)
        with _as_validation_error():
            link = CategoryParentLink(category_id=category_id, parent_category_id=parent_id, sort_index=sort_index)
        if self._is_root(category_id):
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        if category_id == parent_id:
            raise TaxomeshCyclicDependencyError(f"Category {category_id} cannot be its own parent")
        self._require_stored(category_id)
        self._require_stored(parent_id)
        repository = self._service.repository
        check_no_cycle(category_id, parent_id, repository.list_category_parent_links())
        with self._atomic():
            repository.save_category_parent_link(link)
            repository.delete_category_parent_link(category_id, self._root_id)
        return link

    def remove_parent(self, category: CategoryRef, parent: CategoryRef) -> None:
        """Remove one parent link from a category.

        A no-op when the link is not stored. A category that loses its last parent moves to the
        top level, in the same ``atomic()`` block.

        Args:
            category: The category that loses a parent, or its identifier.
            parent: The parent to remove, or its identifier.

        Raises:
            TaxomeshCategoryNotFoundError: If either category is not stored, or if either
                identifier is that of the implicit root, which is not a row in this container.
            TypeError: If either is neither a ``Category`` nor a ``UUID``.
        """
        category_id = category_id_of(category)
        parent_id = category_id_of(parent)
        self._require_stored(category_id)
        self._require_stored(parent_id)
        repository = self._service.repository
        with self._atomic():
            removed = repository.delete_category_parent_link(category_id, parent_id)
            if removed and not repository.list_category_parent_links(category_ids=[category_id]):
                repository.save_category_parent_link(self._top_level_link(category_id))

    def move(
        self,
        category: CategoryRef,
        *,
        from_parent: CategoryRef | None,
        to_parent: CategoryRef | None,
        before: CategoryRef | None = None,
    ) -> None:
        """Move a category from one parent to another, onto the top level, or off it.

        ``None`` on either side is the top level. Every check comes before the first write, so a
        refused move changes nothing. Each category is given as itself or as its identifier.

        Args:
            category: The category to move.
            from_parent: The parent that it leaves, or ``None`` to take it off the top level.
            to_parent: The parent that it joins, or ``None`` to put it at the top level.
            before: The sibling to put it before; when it is ``None``, the category goes last.

        Raises:
            TaxomeshCategoryNotFoundError: If the category or a given parent is not stored, or is
                the implicit root.
            TaxomeshCyclicDependencyError: If ``to_parent`` is the category or one of its
                descendants.
            TaxomeshValidationError: If ``to_parent`` is ``None`` and the category keeps another
                parent: a category with a parent is not at the top level.
            TaxomeshRepositoryError: If storage fails while writing the move.
            TypeError: If one of them is neither a ``Category`` nor a ``UUID``.

        Note:
            A category that is not under ``from_parent`` loses nothing: to remove the absent link
            is a no-op. Given a ``to_parent``, it then gets that parent, as :meth:`add_parent`
            would give it.
        """
        category_id = category_id_of(category)
        from_parent_id = None if from_parent is None else category_id_of(from_parent)
        to_parent_id = None if to_parent is None else category_id_of(to_parent)
        before_id = None if before is None else category_id_of(before)
        self._require_stored(category_id)
        for parent_id in (from_parent_id, to_parent_id):
            if parent_id is not None:
                self._require_stored(parent_id)
        leaving = self._root_id if from_parent_id is None else from_parent_id
        joining = self._root_id if to_parent_id is None else to_parent_id

        links = self._service.repository.list_category_parent_links()
        if to_parent_id is None:
            kept = {lnk.parent_category_id for lnk in links if lnk.category_id == category_id}
            if kept - {leaving, self._root_id}:
                raise TaxomeshValidationError(
                    f"Category {category_id} keeps another parent, so it cannot be at the top level"
                )
        else:
            check_no_cycle(category_id, to_parent_id, links)

        siblings = sorted(
            (lnk for lnk in links if lnk.parent_category_id == joining and lnk.category_id != category_id),
            key=lambda lnk: lnk.sort_index,
        )
        insert_pos = next((i for i, lnk in enumerate(siblings) if lnk.category_id == before_id), len(siblings))
        siblings.insert(
            insert_pos, CategoryParentLink(category_id=category_id, parent_category_id=joining, sort_index=insert_pos)
        )

        with self._atomic():
            self._service.repository.delete_category_parent_link(category_id, leaving)
            if from_parent_id is not None and to_parent_id is not None:
                self._service.repository.delete_category_parent_link(category_id, self._root_id)
            for i, lnk in enumerate(siblings):
                self._service.repository.save_category_parent_link(lnk.model_copy(update={"sort_index": i}))

    def reorder(self, parent: CategoryRef | None, categories: Sequence[CategoryRef]) -> None:
        """Set the order of a parent's children, or of the top level.

        Args:
            parent: The parent whose children get the order, or its identifier, or ``None`` for
                the top level.
            categories: Every child of that parent, in the new order, each the category or its
                identifier.

        Raises:
            TaxomeshCategoryNotFoundError: If the parent is not stored, or is the implicit root.
            TaxomeshValidationError: If a category is not a child of that parent, or, for ``None``,
                not at the top level.
            TaxomeshRepositoryError: If storage fails while writing the order.
            TypeError: If the parent or a category is neither a ``Category`` nor a ``UUID``, or
                ``categories`` is not a sequence: a set, a mapping or an iterator.
        """
        parent_id = None if parent is None else category_id_of(parent)
        _require_sequence("categories", categories)
        category_ids = [category_id_of(category) for category in categories]
        if parent_id is not None:
            self._require_stored(parent_id)
        scope = self._root_id if parent_id is None else parent_id
        existing = {
            lnk.category_id: lnk
            for lnk in self._service.repository.list_category_parent_links()
            if lnk.parent_category_id == scope
        }
        for uid in category_ids:
            if uid not in existing:
                where = "at the top level" if parent_id is None else f"a child of {parent_id}"
                raise TaxomeshValidationError(f"Category {uid} is not {where}")
        with self._atomic():
            for sort_index, uid in enumerate(category_ids):
                link = existing[uid].model_copy(update={"sort_index": sort_index})
                self._service.repository.save_category_parent_link(link)
