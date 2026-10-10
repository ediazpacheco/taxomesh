"""The ``TypedDict`` types of the admin's graph views.

They are here, and not in ``admin.py``, because ``admin.py`` and ``graph_sort.py`` both need
``GraphEntry``, and each one importing the other would be a circular import.
"""

from typing import TypedDict


class GraphEntry(TypedDict):
    """One entry of the graph page, as the template renders it: a category or an item."""

    depth: int
    kind: str
    name: str
    uuid: str
    enabled: bool
    external_id: str | None
    linked_url: str | None
    has_descendants: bool
    depth_limited: bool
    initially_collapsed: bool
    sort_index: int
    parent_uuid: str


class RelationEntry(TypedDict):
    """One outgoing relation of an item, as the template renders it."""

    relation_type: str
    target_name: str
    target_uuid: str
