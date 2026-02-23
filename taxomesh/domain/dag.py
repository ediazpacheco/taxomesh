"""DAG integrity utilities for the taxomesh category hierarchy.

Category parent relationships form a Directed Acyclic Graph (DAG).
This module provides the cycle-detection logic that the service layer
invokes before persisting any new parent link, as required by
Constitution Principle VI.
"""

from uuid import UUID

from taxomesh.domain.models import CategoryParentLink
from taxomesh.exceptions import TaxomeshCyclicDependencyError


def _can_reach(start: UUID, target: UUID, parents_map: dict[UUID, list[UUID]]) -> bool:
    """Return True if ``target`` is reachable from ``start`` via parent links.

    Args:
        start: UUID to start the traversal from.
        target: UUID to search for.
        parents_map: Mapping of category_id → list of parent_category_ids.

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
    existing_links: list[CategoryParentLink],
) -> None:
    """Raise TaxomeshCyclicDependencyError if adding category_id → parent_id creates a cycle.

    Builds the current parent graph from ``existing_links`` and checks whether
    ``category_id`` is reachable from ``parent_id``. If it is, the proposed link
    would close a cycle.

    Args:
        category_id: The child category that would gain a new parent.
        parent_id: The proposed parent category.
        existing_links: All CategoryParentLink records currently in the repository.

    Raises:
        TaxomeshCyclicDependencyError: If the proposed link would introduce a cycle.
    """
    parents_map: dict[UUID, list[UUID]] = {}
    for link in existing_links:
        parents_map.setdefault(link.category_id, []).append(link.parent_category_id)

    if _can_reach(parent_id, category_id, parents_map):
        raise TaxomeshCyclicDependencyError(f"Adding {category_id} → {parent_id} creates a cyclic dependency")
