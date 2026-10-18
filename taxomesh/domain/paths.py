"""The walk that draws the category graph once for each path.

The graph holds one node for each category, but a drawing is a *tree*: a category that several
parents reach is drawn once **for each path**, because a nested ``children`` document or a branch of
a tree means that. So the guard of :func:`walk_paths` is **path-local**, not global: it holds the
ancestors of the category that it visits, and nothing else. A global set would stop the second visit
of a shared subtree, and change the drawing that the tests pin. :func:`~taxomesh.domain.dag.depth_first`
and ``TaxomeshGraph.walk`` use a global set for the opposite reason: they yield each category exactly
once. One guard cannot replace the other.

The walk is iterative, as :func:`~taxomesh.domain.dag.depth_first` is, for the reason that
:mod:`taxomesh.domain.dag` gives.

The HTTP serializer and the ``graph`` command each draw in their own form, and both use this walk.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from uuid import UUID

from taxomesh.domain.graph import CategoryNode


@dataclass(eq=False, slots=True)
class PathVisit[S]:
    """One category on one path: where to draw it, and where to draw what is below it.

    The consumer draws the category into :attr:`outer`. To go down from it, the consumer sets
    :attr:`inner` to where its children go before it asks for the next visit. When it sets none, the
    walk goes no deeper on this path.

    Attributes:
        node: The category to draw.
        depth: How many categories are above it on this path; ``0`` for a top-level category.
        repeated: ``True`` when the category is already on this path, which only a cycle in stored
            data causes. The walk does not go down from a repeated category, whatever the consumer sets.
        outer: Where the parent put its children, or the ``top`` that the walk was given.
        inner: Where the children of this category go. ``None`` until the consumer sets it.
    """

    node: CategoryNode
    depth: int
    repeated: bool
    outer: S
    inner: S | None = None


@dataclass(frozen=True, slots=True)
class _Enter[S]:
    """A category to visit, where to draw it, and its depth."""

    node: CategoryNode
    outer: S
    depth: int


@dataclass(frozen=True, slots=True)
class _Leave:
    """A marker that the descent has finished with a category, so it leaves the current path."""

    category_id: UUID


def walk_paths[S](roots: Sequence[CategoryNode], top: S) -> Iterator[PathVisit[S]]:
    """Visit the categories below ``roots`` once for each path, depth-first, in stored order.

    A category that several parents reach is visited under each of them. A category already on the
    path being visited is visited again with ``repeated`` set, and the walk does not go down from it.
    So the walk ends on any stored shape. The count of visits grows exponentially with shared
    parents, so the consumer counts them and stops the walk at its limit.

    Args:
        roots: The categories to start from, in order.
        top: Where the drawing of the roots goes; it is the ``outer`` of each root's visit.

    Yields:
        One visit for each category on each path.
    """
    path: set[UUID] = set()
    stack: list[_Enter[S] | _Leave] = [_Enter(node, top, 0) for node in reversed(roots)]
    while stack:
        frame = stack.pop()
        if isinstance(frame, _Leave):
            # One _Leave is pushed for each path entry, and it pops before a sibling can enter that
            # identifier again, so remove() finds it. A later defect in that order raises KeyError here.
            path.remove(frame.category_id)
            continue

        category_id = frame.node.category.category_id
        visit = PathVisit(frame.node, frame.depth, category_id in path, frame.outer)
        yield visit
        if visit.repeated or visit.inner is None:
            continue

        path.add(category_id)
        # Pushed BEFORE the children so that it pops AFTER them: the path must stay whole for the
        # whole descent. Pushed after them, it would pop first and clear the path before any child
        # was visited, and the guard would then stop nothing.
        stack.append(_Leave(category_id))
        # Reversed, so that popping restores the children's stored order.
        stack.extend(_Enter(child, visit.inner, frame.depth + 1) for child in reversed(frame.node.children))
