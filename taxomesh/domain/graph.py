"""The graph snapshot and its nodes: the read models of the category graph.

A graph is an immutable snapshot of the category graph at one moment, and it builds **one node
for each category that it holds**. A ``CategoryNode`` is a *view* over the flat maps of the graph,
and not a value object. A category that several parents reach is the same node object from each
parent, so a shared branch costs one node and not one for each path.

The graph keeps its data apart from the navigation. It holds flat maps: the categories, the
child identifiers, the parent identifiers and the items. A node reads ``children``, ``parents``
and ``items`` from those maps each time they are read. So a node keeps no copy of the structure,
and cannot disagree with it.

``TaxomeshService`` builds both types from those flat maps. A test builds a graph by hand with the
same constructor, so there is one way to build a graph, and no way that only tests use.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from itertools import chain, islice
from typing import ClassVar, overload
from uuid import UUID

from taxomesh.domain.dag import depth_first
from taxomesh.domain.models import Category, Item
from taxomesh.domain.refs import CategoryRef, category_id_of
from taxomesh.exceptions import TaxomeshCategoryNotFoundError


class CategoryNode:
    """A view of one category in a graph snapshot.

    It is **not** a value object: it defines neither ``__eq__`` nor ``__hash__``, so two nodes are
    equal only when they are the same object. Two views of the same category from two *different*
    graphs are different objects, because they are views of different snapshots.

    ``__repr__`` shows the identifier and the name of the category, and never its children, so
    printing a node does not walk the graph. On a deep graph, or on one with shared categories,
    that walk would print too much to be useful.
    """

    __slots__ = ("_category", "_graph")

    def __init__(self, graph: TaxomeshGraph, category: Category) -> None:
        """Bind a view to its graph and to the category it shows.

        :class:`TaxomeshGraph` builds the nodes once, and returns the same node on every lookup. A
        node is not built directly, because a node outside a graph has no parents or children to
        read.

        Args:
            graph: The snapshot this node belongs to.
            category: The category this node shows.
        """
        self._graph = graph
        self._category = category

    @property
    def category(self) -> Category:
        """The category row that this node shows."""
        return self._category

    @property
    def children(self) -> Sequence[CategoryNode]:
        """The child categories, ordered by the sort index of their parent links."""
        return self._graph._child_nodes(self._category.category_id)

    @property
    def parents(self) -> Sequence[CategoryNode]:
        """The parent categories.

        Empty for a top-level category. Its parent link to the implicit root is stored, but the
        implicit root is not a node of this graph, as it is not a row that a collection returns.

        In a graph limited by ``root``, only the parents in that subtree are here: a parent outside
        the subtree is not a node of this graph, so it is left out. So the parents of the ``root``
        category are empty too, for a different reason than those of a top-level category.
        """
        return self._graph._parent_nodes(self._category.category_id)

    @property
    def items(self) -> Sequence[Item]:
        """The items placed in this category, ordered by sort index.

        Empty when the graph was built without items. That looks the same as a category that
        holds no items.
        """
        return self._graph._category_items(self._category.category_id)

    def ancestors(self) -> Sequence[CategoryNode]:
        """Return every category above this one: its parents, their parents, and so on up.

        Depth-first in stored order: the first parent, then every ancestor of that parent, then the
        next parent. Each category comes once, however many paths reach it. The node itself is
        left out, and a cycle in stored data that leads back to it ends the walk there.

        In a graph limited by ``root``, these are the ancestors that the graph holds: a parent
        outside the subtree is not a node of this graph.

        Returns:
            The ancestor nodes; empty for a top-level category.
        """
        return self._graph._ancestor_nodes(self._category.category_id)

    def descendants(self) -> Sequence[CategoryNode]:
        """Return every category below this one: its children, their children, and so on down.

        Depth-first in stored order: the first child, then every descendant of that child, then
        the next child. Each category comes once, however many paths reach it. The node itself is
        left out, and a cycle in stored data that leads back to it ends the walk there.

        Returns:
            The descendant nodes; empty for a leaf.
        """
        return self._graph._descendant_nodes(self._category.category_id)

    def __repr__(self) -> str:
        """Render the node as the identifier and the name of its category, never its children."""
        return f"CategoryNode(category_id={self._category.category_id}, name={self._category.name!r})"


class TaxomeshGraph:
    """A read-only snapshot of the category graph, addressed by category identifier.

    ``TaxomeshService.graph()`` returns it. Subscript raises and ``get`` does not, as everywhere
    else in the library.

    :meth:`walk` is the only enumerator, so ``len()`` and the number of nodes it yields cannot
    disagree. There is no second one, on purpose, so ``__iter__`` and ``__reversed__`` are
    ``None``. If they were not defined, Python's old sequence protocol would let ``iter(graph)`` and
    ``reversed(graph)`` succeed. Their first ``next()`` would call ``graph[0]`` or
    ``graph[len(graph) - 1]`` and raise a not-found error, but ``reversed()`` over an empty graph
    would yield nothing. ``None`` makes both raise ``TypeError``.

    The graph is a **snapshot**: the categories it holds, and the links of its nodes to each other
    and to their items, are fixed when it is built. Rows are frozen, so the ``category`` and the
    ``items`` of a node are the rows that the graph was built from, on every backend.
    """

    __slots__ = ("_children", "_items", "_nodes", "_parents", "_root_ids")
    __iter__: ClassVar[None] = None
    __reversed__: ClassVar[None] = None

    def __init__(
        self,
        *,
        categories: Mapping[UUID, Category],
        children: Mapping[UUID, Sequence[UUID]],
        parents: Mapping[UUID, Sequence[UUID]],
        items: Mapping[UUID, Sequence[Item]],
        roots: Sequence[UUID],
    ) -> None:
        """Assemble a snapshot from flat maps.

        Args:
            categories: Every category in the snapshot, keyed by identifier. The graph builds one
                node for each entry, so ``len()`` counts these.
            children: The child identifiers of each category, in the order that the graph returns
                them. A category with no children may be left out, instead of mapped to an empty
                sequence.
            parents: The parent identifiers of each category, in the same way. The implicit root
                is never one of them.
            items: The items placed in each category, ordered by the sort index of their
                placements. Empty for every category in a graph built without items.
            roots: The identifiers of :attr:`roots`, in order: the top-level categories, or the one
                category that ``svc.graph(root=…)`` starts at.

        Note:
            Every identifier in ``children``, ``parents`` or ``roots`` must also be a key of
            ``categories``. The service makes sure of this: it keeps a parent link only when
            **both** of its ends are in ``categories``, so an ``enabled`` filter that removes one
            end also removes the link. An identifier that is not a key would fail when a node is
            read, with an error that does not tell the caller what to do.
        """
        self._children = children
        self._parents = parents
        self._items = {category_id: tuple(group) for category_id, group in items.items()}
        self._root_ids = roots
        # Built once, here. So "the same node object from each parent" is true because of how the
        # graph stores its nodes, and no accessor has to keep it true.
        self._nodes: dict[UUID, CategoryNode] = {
            category_id: CategoryNode(self, category) for category_id, category in categories.items()
        }

    def __getitem__(self, key: CategoryRef, /) -> CategoryNode:
        """Return the node for this category, or raise.

        Args:
            key: The category, or its identifier. Only the identifier is read.

        Returns:
            The node for that category — the same object on every lookup.

        Raises:
            TaxomeshCategoryNotFoundError: If this graph holds no such category. A graph is a
                snapshot, so this also covers a category created after it was built, and one
                excluded by the ``enabled`` filter it was built with.
            TypeError: If ``key`` is neither a ``Category`` nor a ``UUID``.
        """
        category_id = category_id_of(key)
        node = self._nodes.get(category_id)
        if node is None:
            raise TaxomeshCategoryNotFoundError(f"Category not found: {category_id}")
        return node

    @overload
    def get(self, key: CategoryRef, /) -> CategoryNode | None: ...

    @overload
    def get[D](self, key: CategoryRef, default: D, /) -> CategoryNode | D: ...

    def get[D](self, key: CategoryRef, default: D | None = None, /) -> CategoryNode | D | None:
        """Return the node for this category, or a default instead of raising.

        The counterpart to subscript: ``g[key]`` asks for something that must be in the
        snapshot, ``g.get(key)`` asks whether it is. Both parameters are positional-only, as
        on a collection's ``get`` and on ``dict``.

        Args:
            key: The category, or its identifier. Only the identifier is read.
            default: Returned when this graph holds no such category. Defaults to ``None``.

        Returns:
            The node for that category, or ``default`` when this graph holds no such category.

        Raises:
            TypeError: If ``key`` is neither a ``Category`` nor a ``UUID``: a wrong type is
                not an absence.
        """
        return self._nodes.get(category_id_of(key), default)

    def __contains__(self, key: CategoryRef) -> bool:
        """Return whether this graph holds a node for that category.

        Args:
            key: The category, or its identifier.

        Returns:
            ``True`` exactly when ``self[key]`` would not raise a not-found error.

        Raises:
            TypeError: If ``key`` is neither a ``Category`` nor a ``UUID``.
        """
        return category_id_of(key) in self._nodes

    def __repr__(self) -> str:
        """Render the size of the snapshot, the number of categories and of ``roots``, never its contents."""
        return f"{type(self).__name__}(categories={len(self._nodes)}, roots={len(self._root_ids)})"

    def __len__(self) -> int:
        """Return how many categories the snapshot holds, each counted once.

        Returns:
            The number of nodes — one per category the snapshot holds, never one per path
            through them, and always equal to the count :meth:`walk` yields.
        """
        return len(self._nodes)

    @property
    def roots(self) -> Sequence[CategoryNode]:
        """The top-level categories, ordered by sort index and then by category identifier.

        In a graph of the whole taxonomy, these are the categories that have no parent: the same
        categories, in the same order, as ``service.categories.roots()`` with the same ``enabled``
        value. The identifier orders two categories with the same sort index, as the ordering
        contract of the repository port does, and ``create`` gives the same sort index to every
        new category at the top level.

        In a graph limited by ``root``, ``service.graph(root=…)``, this is that one category, and
        the paragraph above does not apply to it. The graph leaves out its parents with the rest
        of the taxonomy outside the subtree, so its place here says nothing about its stored
        parents.
        """
        return tuple(self._nodes[category_id] for category_id in self._root_ids)

    def walk(self) -> Iterator[CategoryNode]:
        """Yield the nodes of this snapshot, each exactly once.

        The only enumerator of the graph, so ``len(self)`` and the number of nodes it yields can
        never disagree. It is **iterative**, so it enumerates a chain deeper than the interpreter's
        recursion limit and does not raise ``RecursionError``, a builtin that a caller who catches
        only this library's errors does not catch. The categories below one node are that node's
        :meth:`CategoryNode.descendants`.

        The walk starts at the categories of :attr:`roots`, depth-first, and **then takes every
        node that it did not reach**. A category that no top-level category reaches can be in the
        graph: for example, a category whose only parent the ``enabled`` filter left out. The walk
        enumerates it; a traversal from the top level would not.

        One visited set does two things: a category that several parents share appears once, and
        a cycle in stored data ends the walk. ``check_no_cycle`` guards the writes, but rows also
        come from direct SQL, a migration or a restored backup.

        Returns:
            An iterator over the nodes, depth-first, children in their stored order.
        """
        # Every node is a seed after those of ``roots``. A node that the walk already reached is
        # skipped, so only a node that no category of ``roots`` reaches starts a walk of its own.
        seeds = chain(self._root_ids, self._nodes)
        return (self._nodes[category_id] for category_id in depth_first(seeds, self._children))

    def _descendant_nodes(self, category_id: UUID) -> tuple[CategoryNode, ...]:
        """Resolve every category below this one to its node, depth-first, the category left out."""
        # The walk yields its seed first and never again, so dropping the first leaves the rest.
        walk = islice(depth_first([category_id], self._children), 1, None)
        return tuple(self._nodes[descendant_id] for descendant_id in walk)

    def _ancestor_nodes(self, category_id: UUID) -> tuple[CategoryNode, ...]:
        """Resolve every category above this one to its node, depth-first, the category left out."""
        walk = islice(depth_first([category_id], self._parents), 1, None)
        return tuple(self._nodes[ancestor_id] for ancestor_id in walk)

    def _child_nodes(self, category_id: UUID) -> tuple[CategoryNode, ...]:
        """Resolve a category's child identifiers to their nodes, in order."""
        return tuple(self._nodes[child_id] for child_id in self._children.get(category_id, ()))

    def _parent_nodes(self, category_id: UUID) -> tuple[CategoryNode, ...]:
        """Resolve a category's parent identifiers to their nodes, in order."""
        return tuple(self._nodes[parent_id] for parent_id in self._parents.get(category_id, ()))

    def _category_items(self, category_id: UUID) -> tuple[Item, ...]:
        """Return a category's items, or an empty tuple when it holds none."""
        return self._items.get(category_id, ())
