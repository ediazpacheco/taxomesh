"""Shared TypedDicts for the Django admin graph views.

These types are defined here (not in admin.py) to avoid circular imports
between admin.py and graph_sort.py — both files need GraphEntry.
"""

from typing import TypedDict


class GraphEntry(TypedDict):
    """A single flattened entry for template rendering."""

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
    """A single outgoing item relation for template rendering."""

    relation_type: str
    target_name: str
    target_uuid: str
