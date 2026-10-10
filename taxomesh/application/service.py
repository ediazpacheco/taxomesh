"""The application service of taxomesh.

``TaxomeshService`` is the one class that a caller builds. The operations on categories, items and
tags are on the three collections that it builds: ``svc.categories``, ``svc.items`` and
``svc.tags``. The graph snapshot and the diagnostic information stay on the service, because they
do not belong to one kind of entity. The service owns the repository and the state that the
collections share, and it holds no storage logic.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from taxomesh.application.collections.base import _require_enabled
from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.collections.tags import TagCollection
from taxomesh.application.search import SearchCorpus
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.dag import collect_subtree
from taxomesh.domain.graph import TaxomeshGraph
from taxomesh.domain.info import TaxomeshInfo
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink
from taxomesh.domain.refs import CategoryRef, category_id_of
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshValidationError
from taxomesh.ports.repository import TaxomeshRepositoryBase
from taxomesh.utils.memoize import ReadCache, memoize

__all__ = ["DEFAULT_CACHE_TTL", "TaxomeshService"]

DEFAULT_CACHE_TTL: Final[float] = 5.0
"""Seconds a service serves a cached read from memory, unless it is built with another ``cache_ttl``."""


@dataclass(frozen=True, slots=True)
class _GraphRows:
    """The flat rows and links that one graph is assembled from.

    The service caches these, and not the assembled graph. A graph limited by ``root`` is assembled
    again from the same rows, so the cache holds one copy of the taxonomy, and not one snapshot for
    each category that a caller asks for.

    Every field is declared ``Sequence``, not ``list``, and the code depends on it. Every assembly
    within one cache lifetime reads the same instance, so an assembler that sorted or filtered a
    field in place would change what the next caller reads. With the annotation, mypy refuses such
    a change; a comment could only ask for care.

    Attributes:
        categories: Every category row that the ``enabled`` filter selects. It includes the implicit
            root when the filter selects it, and the assembler leaves the implicit root out.
        category_links: Every parent link, unfiltered.
        item_links: The item placements, or empty when the graph is built without items.
        items: The item rows that the ``enabled`` filter selects, or empty when the graph is built
            without items.
    """

    categories: Sequence[Category]
    category_links: Sequence[CategoryParentLink]
    item_links: Sequence[ItemParentLink]
    items: Sequence[Item]


class TaxomeshService:
    """The one entry point for the categories, items and tags of taxomesh.

    The operations on one kind of entity are on the three collections that the service builds:
    ``svc.categories``, ``svc.items`` and ``svc.tags``. What does not belong to one kind of entity
    stays on the service: the graph snapshot (:meth:`graph`), the diagnostic information
    (:attr:`info`) and the repository (:attr:`repository`).

    The service caches its reads for ``cache_ttl`` seconds, in a cache of its own: a write
    through it clears that cache, and no other service's.
    """

    def __init__(
        self,
        repository: TaxomeshRepositoryBase | None = None,
        *,
        config_path: Path | str | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
    ) -> None:
        """Build the service over one repository, and store the implicit root if it is absent.

        Building a service reads every stored category once, to find the implicit root by its
        reserved name. When no root is stored, the service stores one. So build one service and
        share it, rather than one for each request.

        Args:
            repository: The repository to use. When it is given, the service reads no config file
                and ignores ``config_path``.
            config_path: The ``taxomesh.toml`` to read when no repository is given. When it is
                ``None``, the service reads ``taxomesh.toml`` in the working directory. Without the
                file, or without a ``[repository]`` section in it, the repository is a
                ``YamlRepository`` at its default path, which creates the file and its directory
                when they are absent.
            cache_ttl: How many seconds the service serves a read from memory: a lookup, a batch
                lookup, a listing, the rows a graph is built from, and each search corpus. ``0``
                caches nothing, so every read reaches storage.

        Raises:
            TypeError: If ``cache_ttl`` is not a number.
            TaxomeshValidationError: If ``cache_ttl`` is negative or NaN. The service checks it
                before it reads the config file or storage.
            TaxomeshConfigError: If the config file exists but cannot be read or parsed, or names a
                repository type that taxomesh does not support.
            TaxomeshRepositoryError: If the service builds the repository and the build fails, or
                if the write that stores the implicit root fails.
        """
        if not isinstance(cache_ttl, (int, float)):
            raise TypeError(f"cache_ttl must be a number of seconds, not {type(cache_ttl).__name__}")
        # Written as a negation so that NaN, which compares false with everything, is refused too.
        if not cache_ttl >= 0:
            raise TaxomeshValidationError(f"cache_ttl must be ≥ 0, got {cache_ttl!r}")
        self._config_name: str | None = None
        if repository is None:
            # Resolving a repository reaches the adapters, so the module that does it is imported
            # only on the path that needs it.
            from taxomesh._config import resolve_repository  # noqa: PLC0415

            repository, self._config_name = resolve_repository(config_path)
        self._repo = repository
        self._root_id: UUID = self._ensure_root()
        self._cache = ReadCache(cache_ttl)
        self._item_corpus: SearchCorpus[Item] = SearchCorpus(self._cache)
        self._category_corpus: SearchCorpus[Category] = SearchCorpus(self._cache)
        # Built once, here, and not on each access. Building them does no I/O. The service owns the
        # identifier of the implicit root, the cache and the corpora, and gives them to the
        # collections, so a collection never reads a private attribute of the service, and a write
        # through any collection clears the one cache that they share.
        self.categories = CategoryCollection(
            self, cache=self._cache, root_id=self._root_id, corpus=self._category_corpus
        )
        self.items = ItemCollection(self, cache=self._cache, corpus=self._item_corpus)
        self.tags = TagCollection(self, cache=self._cache)

    def __repr__(self) -> str:
        """Render as the constructor call over this service's repository, reading no storage.

        ``cache_ttl`` is shown only when it is not the default.
        """
        lifetime = "" if self._cache.ttl == DEFAULT_CACHE_TTL else f", cache_ttl={self._cache.ttl!r}"
        return f"{type(self).__name__}({self._repo!r}{lifetime})"

    @property
    def repository(self) -> TaxomeshRepositoryBase:
        """Return the repository that this service reads and writes."""
        return self._repo

    @property
    def info(self) -> TaxomeshInfo:
        """Return diagnostic information about this service, its repository and the installed version.

        Returns:
            A :class:`~taxomesh.domain.info.TaxomeshInfo` snapshot: the installed version, the
            config name, the size of each search corpus, and the repository's own
            :class:`~taxomesh.domain.info.RepositoryInfo`, which names the repository class and
            its path. A corpus size is ``None`` when the service holds no corpus of that kind.
        """
        import importlib.metadata  # noqa: PLC0415

        try:
            version: str = importlib.metadata.version("taxomesh")
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        return TaxomeshInfo(
            version=version,
            config_name=self._config_name,
            item_corpus_size=self._item_corpus.size,
            category_corpus_size=self._category_corpus.size,
            repository=self._repo.describe(),
        )

    def _ensure_root(self) -> UUID:
        """Make sure that the implicit root is stored, and return its identifier.

        Reads every stored category to find the implicit root by its reserved name, and stores one
        when none is found. ``__init__`` calls it once. It is the one read of the repository that
        building a service makes, because the port has no lookup by name.
        """
        for cat in self._repo.list_categories(enabled=None):
            if cat.name == ROOT_CATEGORY_NAME:
                return cat.category_id
        root = Category(category_id=uuid4(), name=ROOT_CATEGORY_NAME)
        self._repo.save_category(root)
        return root.category_id

    @memoize
    def _load_graph_rows(self, *, enabled: bool | None, include_items: bool) -> _GraphRows:
        """Read the flat rows a graph is assembled from, and cache them.

        The cached half of the graph read. Its key is ``(enabled, include_items)``, so it holds at
        most six entries, however many graphs are assembled from them.

        Neither parameter has a default. ``memoize`` builds the key from the arguments as the call
        passes them, and adds no defaults. So a call that omitted one would store the same read
        under a second key, and would not find the entry that a call of the other form stored.

        Args:
            enabled: ``True`` enabled only, ``False`` disabled only, ``None`` all.
            include_items: Whether to read the item placements and the items. When it is ``False``,
                the method makes neither read: the purpose is to save the two reads, not to return
                empty fields.

        Returns:
            The rows, with the item fields empty when ``include_items`` is ``False``.

        Raises:
            TaxomeshRepositoryError: If the repository cannot read its storage.
        """
        categories = self._repo.list_categories(enabled=enabled)
        category_links = self._repo.list_category_parent_links()
        if not include_items:
            return _GraphRows(
                categories=categories,
                category_links=category_links,
                item_links=(),
                items=(),
            )
        # The order of these reads matters outside this method: the read-count tests compare the
        # ordered list of calls, not only its length.
        item_links = self._repo.list_item_parent_links()
        items = self._repo.list_items(enabled=enabled)
        return _GraphRows(
            categories=categories,
            category_links=category_links,
            item_links=item_links,
            items=items,
        )

    def graph(
        self,
        *,
        root: CategoryRef | None = None,
        enabled: bool | None = True,
        include_items: bool = True,
    ) -> TaxomeshGraph:
        """Build and return a graph snapshot of the whole taxonomy, or of one category and its descendants.

        The service reads, from the repository, the categories and items that the ``enabled``
        filter selects, every parent link and every item placement. With ``include_items=False``,
        it reads no item and no placement. With ``root``, it first reads the row of that category,
        whatever its state. The snapshot holds each of its categories as one node, however many
        paths reach it. The implicit root is never one of them.

        The assembly is **not** cached; the flat rows behind it are (:meth:`_load_graph_rows`). So
        a repeated call reads no storage, but builds the nodes again: it uses a bounded amount of
        CPU on each call, and not an unbounded amount of memory. For the same reason, a graph
        limited by ``root`` costs no more memory: every such graph is assembled from the same
        cached rows, so the cache holds one copy of the taxonomy, and not one snapshot for each
        category that a caller asks for.

        Args:
            root: When it is given, the snapshot holds only that category and its descendants, and
                that category is the only node in ``roots``. The category or its identifier: the
                result is the same for both. When it is ``None`` (the default), the snapshot holds
                the whole taxonomy.
            enabled: ``True`` (the default) includes only enabled categories and items, ``False``
                only disabled ones, and ``None`` all of them.
            include_items: ``True`` (the default) gives each node its items. ``False`` reads no item
                row, which suits a caller that draws a navigation menu. Every node's ``items`` is
                then empty, as it is for a category that has no items.

        Returns:
            A ``TaxomeshGraph`` snapshot. Its ``roots`` is empty when no category is stored. The
            nodes in ``roots`` are ordered by the ``sort_index`` of their link to the implicit root,
            then by identifier. In a graph limited by ``root``, the only node in ``roots`` is
            ``root``.

        Raises:
            TaxomeshCategoryNotFoundError: If ``root`` names a category that is not stored, names
                the implicit root, or names a category that the ``enabled`` filter of this
                snapshot leaves out.
            TaxomeshRepositoryError: If the repository cannot read its storage.
            TypeError: If ``root`` is neither a ``Category`` nor a ``UUID``, or ``enabled`` neither
                a ``bool`` nor ``None``.

        Example::

            g = svc.graph(root=music, include_items=False)
            len(g)                      # the subtree, not the taxonomy
            [n.category.name for n in g.roots]   # ['Music']
        """
        _require_enabled(enabled)
        root_id = None if root is None else category_id_of(root)
        if root_id is not None:
            # Checked through subscript, which raises for an identifier that names no stored
            # category and for the implicit root. Checked here, before the loader runs, so that
            # this read is first in the ordered list of calls that the read-count tests compare.
            self.categories[root_id]
        rows = self._load_graph_rows(enabled=enabled, include_items=include_items)
        all_cats = {c.category_id: c for c in rows.categories if c.category_id != self._root_id}
        all_links = rows.category_links

        # Keep the links between two categories that the snapshot holds, after the enabled filter.
        # The links to the implicit root are kept apart, below.
        explicit_links = [
            lnk
            for lnk in all_links
            if lnk.parent_category_id != self._root_id
            and lnk.category_id in all_cats
            and lnk.parent_category_id in all_cats
        ]
        root_child_links = [
            lnk for lnk in all_links if lnk.parent_category_id == self._root_id and lnk.category_id in all_cats
        ]
        # The top level is what ``categories.roots()`` lists: the categories linked to the implicit root.
        root_sort = {lnk.category_id: lnk.sort_index for lnk in root_child_links}

        children_by_parent: dict[UUID, list[tuple[int, UUID]]] = {}
        for lnk in explicit_links:
            children_by_parent.setdefault(lnk.parent_category_id, []).append((lnk.sort_index, lnk.category_id))
        for bucket in children_by_parent.values():
            bucket.sort(key=lambda t: t[0])

        items_map = {i.item_id: i for i in rows.items}
        items_pairs_by_cat: dict[UUID, list[tuple[int, Item]]] = {}
        for ilnk in rows.item_links:
            if ilnk.item_id in items_map:
                items_pairs_by_cat.setdefault(ilnk.category_id, []).append((ilnk.sort_index, items_map[ilnk.item_id]))
        sorted_items_by_cat: dict[UUID, list[Item]] = {
            cid: [item for _, item in sorted(pairs, key=lambda t: t[0])] for cid, pairs in items_pairs_by_cat.items()
        }

        # Both adjacency maps are built from ``explicit_links``, which keeps a link only when the
        # snapshot holds both of its categories. So every identifier here names a node: when the
        # enabled filter leaves out a parent, it leaves out the link to its child too, and no child
        # names a category that the snapshot does not hold.
        children_by_id = {parent_id: [cid for _, cid in bucket] for parent_id, bucket in children_by_parent.items()}
        parents_by_id: dict[UUID, list[UUID]] = {}
        for lnk in explicit_links:
            parents_by_id.setdefault(lnk.category_id, []).append(lnk.parent_category_id)

        if root_id is not None:
            return self._subtree_graph(root_id, all_cats, children_by_id, parents_by_id, sorted_items_by_cat)

        return TaxomeshGraph(
            categories=all_cats,
            children=children_by_id,
            parents=parents_by_id,
            items=sorted_items_by_cat,
            # The identifier breaks a tie. On ordinary data every top-level category is a tie:
            # ``create`` writes ``sort_index=0`` on each link to the implicit root. With the
            # identifier, the order does not depend on the order in which the repository lists the
            # links: it is the port's ``(parent, sort_index, category_id)`` order, which
            # ``categories.roots()`` also gives.
            roots=sorted(root_sort, key=lambda cid: (root_sort[cid], str(cid))),
        )

    def _subtree_graph(
        self,
        root_id: UUID,
        categories: Mapping[UUID, Category],
        children: Mapping[UUID, Sequence[UUID]],
        parents: Mapping[UUID, Sequence[UUID]],
        items: Mapping[UUID, Sequence[Item]],
    ) -> TaxomeshGraph:
        """Assemble a snapshot of one category and its descendants.

        To change ``roots`` alone is not enough. ``len()`` counts the flat maps and ``walk()``
        goes through all of them, so a graph that kept them whole would report the size of the
        whole taxonomy and walk out of the subtree, while every assertion about ``roots`` still
        passed.

        Args:
            root_id: The category that the snapshot starts at. The caller checked that it is
                stored; the check below decides whether this snapshot holds it.
            categories: Every category that the snapshot would hold without ``root``, keyed by
                identifier.
            children: The child identifiers of each category, in display order.
            parents: The parent identifiers of each category.
            items: The items of each category, in placement order.

        Returns:
            A snapshot that holds ``root_id`` and its descendants, with ``root_id`` as the only
            node in ``roots``.

        Raises:
            TaxomeshCategoryNotFoundError: If the ``enabled`` filter left out ``root_id``.
        """
        # The second of two checks, and a necessary one. The first, subscript before the loader,
        # reads the stored row and applies no ``enabled`` filter, so a disabled category passes it
        # and is then absent from these rows. Without this check, the caller would get a bare
        # ``KeyError`` that names a UUID: a built-in error, which a caller that catches
        # ``TaxomeshError`` does not catch. The check reads nothing.
        if root_id not in categories:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {root_id}")

        subtree = collect_subtree(root_id, children)
        kept = set(subtree)
        return TaxomeshGraph(
            categories={cid: categories[cid] for cid in subtree},
            # Copied, never shared: every assembly within one cache lifetime reads the same
            # ``_GraphRows``, and each assembly builds these maps from it again.
            children={cid: list(children.get(cid, ())) for cid in subtree},
            # The parents are filtered and the children are not, and the difference is needed. A
            # child of a category in the subtree is always in the subtree, by the definition of a
            # subtree, so the children are copied without a filter. A parent can be outside the
            # subtree: a category in the subtree can have a parent that is not in it, and that
            # identifier is not a node here. If it stayed, the assembly would not fail, but the
            # first read of ``node.parents`` would raise a bare ``KeyError``. Keep this filter,
            # although the children have none.
            parents={cid: [pid for pid in parents.get(cid, ()) if pid in kept] for cid in subtree},
            items={cid: list(items[cid]) for cid in subtree if cid in items},
            roots=[root_id],
        )
