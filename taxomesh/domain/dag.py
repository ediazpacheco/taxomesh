"""The cycle check and the depth-first walk of the category graph.

The parent links of the categories form a directed acyclic graph (DAG). This module has the cycle
check that the category collection runs before it stores a new parent link: the domain owns that
check, and no adapter repeats it. It also has the one depth-first walk. ``svc.graph(root=…)``, a
recursive item listing, the graph's ``walk()``, and a node's ``ancestors()`` and ``descendants()``
run it.

Both traversals are **iterative**, and both keep a set of the categories they visited. Neither is
an optimisation. Without them, a chain deeper than the interpreter's recursion limit would raise
``RecursionError``, a builtin that a caller who catches only this library's errors does not catch.
And stored data can contain a cycle, because ``check_no_cycle`` guards only the writes: rows also
come from direct SQL, a migration or a restored backup.
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from uuid import UUID

from taxomesh.domain.models import CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError


def _can_reach(start: UUID, target: UUID, parents_map: dict[UUID, list[UUID]]) -> bool:
    """Return True if ``target`` can be reached from ``start`` through parent links.

    Args:
        start: The identifier to start the traversal from.
        target: The identifier to search for.
        parents_map: The parent identifiers of each category identifier.

    Returns:
        True if ``target`` is reachable from ``start``; False otherwise.
    """
    visited: set[UUID] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(parents_map.get(node, []))
    return False


def check_no_cycle(
    category_id: UUID,
    parent_id: UUID,
    existing_links: Sequence[CategoryParentLink],
) -> None:
    """Raise TaxomeshCyclicDependencyError if the link category_id → parent_id makes a cycle.

    Builds the parent graph from ``existing_links``, and checks whether ``category_id`` can be
    reached from ``parent_id``. If it can, the new link would close a cycle.

    Args:
        category_id: The child category that would get a new parent.
        parent_id: The new parent category.
        existing_links: Every parent link that the repository stores now.

    Raises:
        TaxomeshCyclicDependencyError: If the proposed link would introduce a cycle.
    """
    parents_map: dict[UUID, list[UUID]] = {}
    for link in existing_links:
        parents_map.setdefault(link.category_id, []).append(link.parent_category_id)

    if _can_reach(parent_id, category_id, parents_map):
        raise TaxomeshCyclicDependencyError(
            f"Category {category_id} cannot have the parent {parent_id}: the parent link makes a cycle"
        )


def depth_first(seeds: Iterable[UUID], neighbours: Mapping[UUID, Sequence[UUID]]) -> Iterator[UUID]:
    """Yield the seeds and every category they reach, depth-first, each exactly once.

    The one walk of the category graph. ``svc.graph(root=…)``, a recursive item listing,
    ``TaxomeshGraph.walk`` and a node's ``ancestors()`` and ``descendants()`` all run it, over the
    children or over the parents. So they cannot disagree about cycles or about the order.

    One visited set is shared by every seed. A category that a seed reached is not yielded again
    from a later seed, and a later seed that was already reached is skipped. So a stored cycle
    ends the walk.

    Args:
        seeds: The categories to walk from, in order. Each is yielded before what it reaches.
        neighbours: The identifiers to go on to from each category, in their stored order: its
            children to walk down, or its parents to walk up. A category with none may be absent
            rather than mapped to an empty sequence.

    Yields:
        Each identifier once, a category's neighbours in their stored order.

    Example::

        list(depth_first([alpha, beta], {alpha: [gamma], beta: [gamma, delta]}))
        # [alpha, gamma, beta, delta]
    """
    visited: set[UUID] = set()
    for seed in seeds:
        stack = [seed]
        while stack:
            category_id = stack.pop()
            # Skipping on arrival rather than before pushing is what makes a diamond cost one
            # visit and a stored cycle terminate, with no separate bookkeeping for either.
            if category_id in visited:
                continue
            visited.add(category_id)
            yield category_id
            # Reversed, so that popping restores the neighbours' stored order.
            stack.extend(reversed(neighbours.get(category_id, ())))


def collect_subtree(root_id: UUID, children_map: Mapping[UUID, Sequence[UUID]]) -> list[UUID]:
    """Return ``root_id`` and every category below it, each exactly once.

    The traversal of ``svc.graph(root=…)`` and of a recursive item listing: :func:`depth_first`
    from one seed, over the children.

    Returns a **list, not a set**, because the caller needs the order. The caller builds its node
    map from this list. With a set, the key order of that map would depend on the stored
    identifiers, and would be the same from one run to the next only by chance.

    Args:
        root_id: The category to go down from. It is in the result, so a leaf yields ``[leaf]``.
            This function does not check it: the caller checks whether it is stored, and whether
            the snapshot holds it, and that check costs the caller a read.
        children_map: Child identifiers per category. A category with no children may be absent
            rather than mapped to an empty sequence.

    Returns:
        The subtree's identifiers, depth-first, children in their stored order.

    Example::

        collect_subtree(alpha, {alpha: [gamma], gamma: [delta]})
        # [alpha, gamma, delta]
    """
    return list(depth_first([root_id], children_map))
