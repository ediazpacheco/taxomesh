"""The public types of the taxomesh API, and the conversions behind them.

These are exported from ``taxomesh``:

* :data:`ExternalId`: what a parameter accepts as an external id.
* :data:`UNSET` and :class:`UnsetType`: the marker that keeps the stored value of a field in an
  update, and its type. The signatures of the update methods use both, so both are exported.
* :class:`Direction`: the names of the relation directions. A relation read takes a member or
  its string value.

``CategoryRef``, ``ItemRef`` and ``TagRef`` are public types too, in :mod:`taxomesh.domain.refs`,
because they name the models, and the models import this module.

These are not exported, because no caller writes them in an annotation:

* :func:`normalise_external_id` is the one rule that converts an :data:`ExternalId` to the stored
  form: the conversion behind the type.
* :data:`Metadata`, :class:`FrozenDict` and :class:`FrozenList` make the ``metadata`` of a row
  immutable all the way down. The field's type is ``dict[str, Any]``, and its value is a ``dict``:
  a :class:`FrozenDict` is a ``dict`` that refuses every change.
"""

from enum import Enum, StrEnum
from numbers import Integral
from typing import Annotated, Any, Final, NoReturn, Self
from uuid import UUID

from pydantic import AfterValidator

type ExternalId = str | int | UUID | None
"""What every external-id parameter accepts.

It is wider than the stored type, ``str | None``, on purpose. An external id is often the integer
primary key of a record in another system. One conversion here saves each caller a ``str(pk)`` at
each call. :func:`normalise_external_id` is that conversion, and the *only* one: its docstring
gives the cost of this choice.
"""


def normalise_external_id(value: ExternalId) -> str | None:
    """Convert an external id to the form that taxomesh stores.

    This is the one conversion rule, and writes and lookups both use it. If a write and a lookup
    converted a value in different ways, a stored value could never be found again.

    Args:
        value: The external id as the caller gives it: text, an integer, a UUID, or ``None`` for
            no external id.

    Returns:
        The stored form: ``None`` when ``value`` is ``None``, otherwise its string form.
        ``None`` is never converted to the string ``"None"``.

    Example::

        normalise_external_id(42)      # -> "42"
        normalise_external_id("42")    # -> "42"   <- the same row as above
        normalise_external_id(None)    # -> None

    Raises:
        TypeError: If ``value`` is not text, an integer, a UUID or ``None``. An integer is any
            ``numbers.Integral``, so a numpy integer is one, but not a ``bool``: ``True`` would be
            stored as ``"True"`` while comparing equal to ``1``.

    Note:
        The accepted type is wider than the stored one, so values with the same string form
        address the **same** row: ``42`` and ``"42"`` are one external id, not two, and so are a
        ``UUID`` and its lowercase text with hyphens. An external id is unique within its kind,
        so creating both raises a conflict, and no second row is created.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, Integral, UUID)):
        raise TypeError(f"An external id is text, an integer or a UUID, not {type(value).__name__}")
    return str(value)


class Direction(StrEnum):
    """Which way an item-to-item relation is read.

    A ``StrEnum`` and not a plain ``Enum``, so the string form is valid too: each member *is* its
    string value. A call that passes ``"outgoing"`` works, and a value stored or serialized as text
    is the same value.

    Attributes:
        OUTGOING: Relations where the queried item is the source.
        INCOMING: Relations where the queried item is the target.
        BOTH: Either. Each stored link is read at most once, so a relation stored as two links,
            ``A→B`` and ``B→A``, is read as two links, one for each direction.
    """

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class UnsetType(Enum):
    """The type of :data:`UNSET`.

    An ``Enum`` with one member, and not a singleton class written by hand. Python makes an enum
    member unique, so ``is UNSET`` is always a correct test. There is no ``__new__`` to write, and
    no claim that a type checker cannot check. A type checker also narrows it exactly:
    ``str | None | UnsetType`` resolves under ``mypy --strict`` without a cast.

    Public because the annotations of the update methods use it, and a caller may need to write
    the same type.
    """

    UNSET = "UNSET"

    def __repr__(self) -> str:
        """Render as ``UNSET``, with no memory address.

        The public-surface ledger shows the default of each parameter with ``repr``, and this is
        the default of the fields of every ``update``. An address, or the default
        ``<UnsetType.UNSET: 'UNSET'>``, would make the ledger harder to read.
        """
        return "UNSET"

    def __str__(self) -> str:
        """Render as ``UNSET`` when formatted."""
        return "UNSET"


UNSET: Final[UnsetType] = UnsetType.UNSET
"""The default of each ``update`` field: it keeps the stored value.

An update method tells three things apart: set a value, set ``None`` (clear the field), or keep
the stored value. ``None`` already means the second, so the third needs its own marker::

    svc.items.update(item_id, external_id=None)   # clear the external id
    svc.items.update(item_id, name="New")         # keep the external id (UNSET)
"""


_FROZEN_MESSAGE: Final[str] = "metadata is frozen: change a copy, made with dict() or list(), and save the copy"


# Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
class FrozenDict(dict[str, Any]):
    """A ``dict`` that refuses every change: one level of the ``metadata`` of a row.

    To a reader it is a plain ``dict``: it compares equal to a literal, passes
    ``isinstance(…, dict)``, and serializes with ``json.dumps``. Every method that would change it
    raises ``TypeError``. So a caller cannot change the metadata of a row that it holds, which the
    cache and the file repositories share with other callers. ``dict(…)`` and ``.copy()`` return a
    plain ``dict``, which the caller can change.

    Pickling and copying build it again through :meth:`__reduce__`, because the default protocol
    fills a new instance by item assignment.
    """

    __slots__ = ()

    def _refuse(self, *args: object, **kwargs: object) -> NoReturn:
        """Raise, whatever the change."""
        raise TypeError(_FROZEN_MESSAGE)

    __setitem__ = __delitem__ = __ior__ = clear = pop = popitem = setdefault = update = _refuse

    # Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
    def __reduce__(self) -> tuple[type[Self], tuple[dict[str, Any]]]:
        """Rebuild from a plain copy, so pickling and copying never assign an item."""
        return type(self), (dict(self),)


# Any: the elements of a JSON array in the caller's metadata.
class FrozenList(list[Any]):
    """A ``list`` that refuses every change: an array in the ``metadata`` of a row.

    As :class:`FrozenDict` is, it is a plain ``list`` to a reader, and every method that would
    change it raises ``TypeError``. ``list(…)``, ``.copy()``, slicing and ``+`` return a plain
    ``list``, which the caller can change.
    """

    __slots__ = ()

    def _refuse(self, *args: object, **kwargs: object) -> NoReturn:
        """Raise, whatever the change."""
        raise TypeError(_FROZEN_MESSAGE)

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _refuse
    append = extend = insert = pop = remove = clear = sort = reverse = _refuse

    # Any: the elements of a JSON array in the caller's metadata.
    def __reduce__(self) -> tuple[type[Self], tuple[list[Any]]]:
        """Rebuild from a plain copy, so pickling and copying never append."""
        return type(self), (list(self),)


def _freeze(value: object) -> object:
    """Return a JSON-like value with every ``dict`` and ``list`` in it made immutable.

    Builds new containers and does not wrap the given ones, so the caller can still change its own
    dicts and lists. A tuple becomes a FrozenList, because every backend reads it back as a list. A
    value of a ``str``, ``int`` or ``float`` subclass, such as an enum member, becomes the plain
    value, because every backend reads back the plain value. Any other value is returned as it is.
    """
    if isinstance(value, dict):
        return _freeze_dict(value)
    if isinstance(value, list | tuple):
        return FrozenList(_freeze(item) for item in value)
    return _plain(value)


def _plain(value: object) -> object:
    """Return a ``str``, ``int`` or ``float`` subclass's value as the plain type; ``bool`` stays."""
    if isinstance(value, bool) or type(value) in (str, int, float):
        return value
    if isinstance(value, str):
        return str.__str__(value)
    if isinstance(value, int):
        return int.__int__(value)
    if isinstance(value, float):
        return float.__float__(value)
    return value


# Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
def _freeze_dict(mapping: dict[str, Any]) -> dict[str, Any]:
    """Return a :class:`FrozenDict` of these items, each frozen: the validator behind :data:`Metadata`.

    A key is text, and one of a ``str`` subclass becomes plain text as a value does.
    """
    return FrozenDict({str.__str__(key): _freeze(item) for key, item in mapping.items()})


# Any: metadata is the caller's own JSON — arbitrary keys, heterogeneous values.
type Metadata = Annotated[dict[str, Any], AfterValidator(_freeze_dict)]
"""A row's ``metadata`` field: the caller's own JSON, immutable all the way down.

Validated as ``dict[str, Any]``, then built again with a :class:`FrozenDict` for each dict and a
:class:`FrozenList` for each list in it. Use it with ``Field(default_factory=FrozenDict)``, because
pydantic does not validate a default.
"""
