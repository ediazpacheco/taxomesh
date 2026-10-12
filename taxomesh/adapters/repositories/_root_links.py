"""The top-level invariant that both file repositories restore in a store when they load it."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import Category, CategoryParentLink, ItemParentLink


def normalise_root_links(
    categories: Mapping[UUID, Category],
    category_links: Sequence[CategoryParentLink],
    item_links: Sequence[ItemParentLink],
) -> tuple[list[CategoryParentLink], list[ItemParentLink]]:
    """Return a store's links with the top-level invariant restored.

    A category holds a link to the implicit root exactly when it holds no other parent link, and no
    item is placed in the root. So a root link held beside another parent is dropped, a category
    holding no parent link gains a root link at sort index 0, as ``create`` makes it, and an item
    placement in the root is dropped. Links that already keep the invariant come back equal, in
    their order.

    Args:
        categories: Every stored category, the root included, keyed by identifier.
        category_links: Every stored parent link.
        item_links: Every stored item placement.

    Returns:
        The parent links and the item placements, in that order. A store holding no category named
        as the root comes back unchanged, since nothing links to a root that is not stored.
    """
    root_id = next((cid for cid, category in categories.items() if category.name == ROOT_CATEGORY_NAME), None)
    if root_id is None:
        return list(category_links), list(item_links)
    parented = {lnk.category_id for lnk in category_links if lnk.parent_category_id != root_id}
    kept = [lnk for lnk in category_links if lnk.parent_category_id != root_id or lnk.category_id not in parented]
    linked = {lnk.category_id for lnk in kept}
    restored = [
        CategoryParentLink(category_id=cid, parent_category_id=root_id, sort_index=0)
        for cid in categories
        if cid != root_id and cid not in linked
    ]
    return kept + restored, [lnk for lnk in item_links if lnk.category_id != root_id]
