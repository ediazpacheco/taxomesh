"""The cycle check and the depth-first walk of the category graph.

The parent links of the categories form a directed acyclic graph (DAG). This module has the cycle
check that the category collection runs before it stores a new parent link: the domain owns that
check, and no adapter repeats it. It also has the one depth-first walk. ``svc.graph(root=…)``, a
recursive item listing, the graph's ``walk()``, and a node's ``ancestors()`` and ``descendants()``
run it, and so does the cycle check.

The walk is **iterative**, and it keeps a set of the categories it visited. Neither is an
optimisation. Without them, a chain deeper than the interpreter's recursion limit would raise
``RecursionError``, a builtin that a caller who catches only this library's errors does not catch.
And stored data can contain a cycle, because ``check_no_cycle`` guards only the writes: rows also
come from direct SQL, a migration or a restored backup.
"""

from collections.abc import Iterable, Iterator, Mapping, Sequence
from uuid import UUID

from taxomesh.domain.models import CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError


def check_not_own_parent(category_id: UUID, parent_id: UUID) -> None:
    """Raise TaxomeshCyclicDependencyError if a category would be its own parent.

    The shortest cycle, and the one refusal that needs no stored link. :func:`check_no_cycle` runs
    it first, so every entry point refuses it in the same words.

    Args:
        category_id: The child category.
        parent_id: The proposed parent.

    Raises:
        TaxomeshCyclicDependencyError: If both identifiers are the same.
    """
    if category_id == parent_id:
        raise TaxomeshCyclicDependencyError(f"Category {category_id} cannot be its own parent")


def check_no_cycle(
    category_id: UUID,
    parent_id: UUID,
    existing_links: Sequence[CategoryParentLink],
    names: Mapping[UUID, str] | None = None,
) -> None:
    """Raise TaxomeshCyclicDependencyError if the link category_id → parent_id makes a cycle.

    Builds the parent graph from ``existing_links``, and checks whether ``category_id`` can be
    reached from ``parent_id``. If it can, the new link would close a cycle.

    Args:
        category_id: The child category that would get a new parent.
        parent_id: The new parent category.
        existing_links: Every parent link that the repository stores now.
        names: The names of the two categories, when the caller has read them: the message then
            names each as ``'Jazz' (<id>)``.

    Raises:
        TaxomeshCyclicDependencyError: If the proposed link would introduce a cycle.
    """
    check_not_own_parent(category_id, parent_id)
    parents_map: dict[UUID, list[UUID]] = {}
    for link in existing_links:
        parents_map.setdefault(link.category_id, []).append(link.parent_category_id)

    if category_id in depth_first([parent_id], parents_map):
        known = names or {}

        def label(key: UUID) -> str:
            return f"'{known[key]}' ({key})" if key in known else str(key)

        raise TaxomeshCyclicDependencyError(
            f"Category {label(category_id)} cannot have the parent {label(parent_id)}: the parent link makes a cycle"
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
