"""The sort modes that the admin's graph page offers: their functions and their list."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from taxomesh.contrib.django.graph_types import GraphEntry

type SortModeFn = Callable[[list[GraphEntry]], list[GraphEntry]]
type SortMode = tuple[str, str, SortModeFn]

DEFAULT_SORT_MODE: Final[str] = "sort_index_asc"


def sort_index_asc(entries: list[GraphEntry]) -> list[GraphEntry]:
    """Return the entries in ascending order of ``sort_index``."""
    return sorted(entries, key=lambda e: e["sort_index"])


def sort_index_desc(entries: list[GraphEntry]) -> list[GraphEntry]:
    """Return the entries in descending order of ``sort_index``."""
    return sorted(entries, key=lambda e: e["sort_index"], reverse=True)


DEFAULT_SORT_MODES: Final[list[SortMode]] = [
    ("sort_index_asc", "Sort index \u2191", sort_index_asc),
    ("sort_index_desc", "Sort index \u2193", sort_index_desc),
]
