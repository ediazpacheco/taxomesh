"""What a parameter naming a category, an item or a tag accepts: the row, or its identifier.

These are exported from ``taxomesh``:

* :data:`CategoryRef`, :data:`ItemRef` and :data:`TagRef` — a row or its ``UUID``, the way
  ``str | os.PathLike`` stands for a path.

These are not, because no caller annotates with them:

* :func:`category_id_of`, :func:`item_id_of` and :func:`tag_id_of` — the one conversion behind
  each type, as ``os.fspath`` is behind a path. Of a row passed in, only its identifier is read, so
  a stale row and a fresh one address the same stored row. Anything else raises ``TypeError``.

They are not in :mod:`taxomesh.domain.types`, because they name the models, and the models
import that module.
"""

from uuid import UUID

from taxomesh.domain.models import Category, Item, Tag

type CategoryRef = Category | UUID
"""A category, or its identifier: what every parameter naming a category accepts."""

type ItemRef = Item | UUID
"""An item, or its identifier: what every parameter naming an item accepts."""

type TagRef = Tag | UUID
"""A tag, or its identifier: what every parameter naming a tag accepts."""


def category_id_of(ref: CategoryRef, /) -> UUID:
    """Return the identifier a category parameter names.

    Args:
        ref: A category, or its identifier.

    Returns:
        The identifier, unchecked against storage.

    Raises:
        TypeError: If ``ref`` is neither a ``Category`` nor a ``UUID``.
    """
    if isinstance(ref, UUID):
        return ref
    if isinstance(ref, Category):
        return ref.category_id
    raise TypeError(f"Expected a Category or a UUID, not {type(ref).__name__}")


def item_id_of(ref: ItemRef, /) -> UUID:
    """Return the identifier an item parameter names.

    Args:
        ref: An item, or its identifier.

    Returns:
        The identifier, unchecked against storage.

    Raises:
        TypeError: If ``ref`` is neither an ``Item`` nor a ``UUID``.
    """
    if isinstance(ref, UUID):
        return ref
    if isinstance(ref, Item):
        return ref.item_id
    raise TypeError(f"Expected an Item or a UUID, not {type(ref).__name__}")


def tag_id_of(ref: TagRef, /) -> UUID:
    """Return the identifier a tag parameter names.

    Args:
        ref: A tag, or its identifier.

    Returns:
        The identifier, unchecked against storage.

    Raises:
        TypeError: If ``ref`` is neither a ``Tag`` nor a ``UUID``.
    """
    if isinstance(ref, UUID):
        return ref
    if isinstance(ref, Tag):
        return ref.tag_id
    raise TypeError(f"Expected a Tag or a UUID, not {type(ref).__name__}")
