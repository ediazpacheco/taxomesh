"""Read-model aggregates for the taxonomy graph snapshot.

These dataclasses are produced exclusively by ``TaxomeshService.get_graph()``
and represent a point-in-time snapshot of the full taxonomy structure.
They are never constructed directly by callers.
"""

from __future__ import annotations

from dataclasses import dataclass

from taxomesh.domain.models import Category, Item


@dataclass
class CategoryNode:
    """A single node in the taxonomy tree snapshot.

    Represents one category together with the items assigned to it and its
    child categories.  A category with multiple explicit parents appears as
    a separate ``CategoryNode`` under each parent (repeated, not deduplicated).

    Attributes:
        category: The full Category domain entity.
        items: Items placed in this category, sorted by sort_index ascending.
        children: Child categories, sorted by sort_index ascending on the
            explicit parent link.
    """

    category: Category
    items: list[Item]
    children: list[CategoryNode]


@dataclass
class TaxomeshGraph:
    """Top-level read-only snapshot of the full taxonomy.

    Produced exclusively by ``TaxomeshService.get_graph()``.

    Attributes:
        roots: Top-level categories (those whose only parent is the implicit
            root), sorted by sort_index ascending.  Empty list when no
            user-created categories exist.
    """

    roots: list[CategoryNode]
