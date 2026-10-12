"""The check that the two relation reads of every repository make on ``relation_types``."""

from collections.abc import Collection


def require_relation_types(relation_types: Collection[str] | None) -> None:
    """Refuse one ``str`` for ``relation_types``, which Python reads as a collection of its letters.

    Raises:
        TypeError: If ``relation_types`` is a ``str``.
    """
    if isinstance(relation_types, str):
        raise TypeError("relation_types must be a collection of str, not str")
