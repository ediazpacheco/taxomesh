"""The container base that the collection of each kind of entity inherits, and its shared checks."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from numbers import Integral
from typing import TYPE_CHECKING, ClassVar, overload
from uuid import UUID

from pydantic import BaseModel, ValidationError

from taxomesh.domain.types import UNSET, ExternalId, normalise_external_id
from taxomesh.exceptions import TaxomeshNotFoundError, TaxomeshValidationError
from taxomesh.utils.memoize import ReadCache

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for type checking only
    from taxomesh.application.service import TaxomeshService


def _normalise_external_ids(external_ids: ExternalId | Collection[ExternalId]) -> frozenset[str]:
    """Convert each external id by the one rule, remove duplicates, and leave out ``None``.

    One external id, as text, an integer, a UUID or ``None``, is one key. The function applies
    :func:`~taxomesh.domain.types.normalise_external_id` and nothing else: a write and a lookup use
    the same conversion, so a value written and a value looked up are always converted the same
    way. So the surrounding whitespace and the empty string are kept, as a write keeps them.
    ``None`` means *no match*, and the rule never gives the text ``"None"``, so it adds no key.

    Raises:
        TypeError: If ``external_ids`` is ``bytes``, a ``bytearray`` or a ``memoryview``, each a
            collection of integers that would be looked up as their digits, is neither one external
            id nor a collection, or an external id is not text, an integer, a UUID or ``None``.
    """
    if isinstance(external_ids, (bytes, bytearray, memoryview)):
        raise TypeError(
            f"external_ids must be an external id or a collection of them, not {type(external_ids).__name__}"
        )
    if external_ids is None or isinstance(external_ids, (str, int, Integral, UUID)):
        external_ids = (external_ids,)
    _require_collection("external_ids", external_ids)
    return frozenset(text for text in map(normalise_external_id, external_ids) if text is not None)


@contextmanager
def _as_validation_error() -> Iterator[None]:
    """Raise the error that Python and this library use for what the model refuses, chained to pydantic's.

    Wraps the collection code that builds a row or a link from a caller's values, so that no
    public member lets pydantic's own error out. An argument of the wrong type, such as
    a name that is not text, raises ``TypeError``, as ``int(None)`` does; a value of the right type
    that the model refuses, such as a name over its maximum length or a sort index reading
    ``"sarasa"``, raises ``TaxomeshValidationError``, as ``int("sarasa")`` raises ``ValueError``.
    pydantic's lax coercion decides what the right type is, so ``"5"`` is a sort index of 5. A
    check the model makes itself with one of this library's validation errors, as a relation's
    checks do, reaches the caller as that error: pydantic reports it as its own, since every
    taxomesh validation error is a ``ValueError``, and carries the original in the error's context.

    Raises:
        TypeError: If an argument is of a type the model does not take.
        TaxomeshValidationError: If the model refuses a value, or the error its own check raised.
    """
    try:
        yield
    except ValidationError as exc:
        raise _refusal(exc) from exc


def _refusal(exc: ValidationError) -> TaxomeshValidationError | TypeError:
    """Return the error a model's refusal stands for, naming each refused field.

    The taxomesh error a model's own check raised wins. Otherwise an argument of the wrong type
    makes it a ``TypeError``: pydantic names such an error ``…_type``, and only the argument itself
    counts, so a key of the wrong type inside a ``metadata`` dict is a value the dict holds.
    """
    details = exc.errors(include_url=False, include_input=False)
    for detail in details:
        raised = detail.get("ctx", {}).get("error")
        if isinstance(raised, TaxomeshValidationError):
            return raised
    reasons = "; ".join(
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}" if detail["loc"] else detail["msg"]
        for detail in details
    )
    if any(len(detail["loc"]) == 1 and detail["type"].endswith("_type") for detail in details):
        return TypeError(reasons)
    return TaxomeshValidationError(reasons)


def _require_plain_json(metadata: object, /) -> None:
    """Refuse metadata that is not plain JSON, before anything is built or written.

    Plain JSON is, at any depth, a dict with ``str`` keys, a list or tuple, a ``str``, an ``int``,
    a finite ``float``, a ``bool`` or ``None``: what every backend can store, a tuple as a list.
    The model takes any mapping as a dict, so a mapping's contents are checked as a dict's are;
    a ``metadata`` that is no mapping at all is the wrong type, which the model refuses. Checked
    where a caller's metadata comes in, not on the model, so a store already holding another value
    still loads.

    Raises:
        TaxomeshValidationError: Naming the first value, or key, that is not plain JSON.
    """
    if isinstance(metadata, Mapping):
        problem = _not_json(dict(metadata), "metadata", {})
        if problem is not None:
            raise TaxomeshValidationError(problem)


def _not_json(value: object, where: str, open_containers: dict[int, str], /) -> str | None:
    """Return why ``value``, found at ``where``, is not plain JSON, or ``None`` when it is.

    ``open_containers`` maps each dict and list on the path down to ``value`` to where it was
    found, as ``json.dumps`` keeps its markers: a container met again on its own path contains
    itself. One held twice side by side is not on its own path, and is plain JSON twice.
    """
    children: list[tuple[str, object]] = []
    if isinstance(value, float) and not math.isfinite(value):
        return f"{where} is {value!r}, which JSON cannot hold"
    if isinstance(value, dict | list | tuple) and id(value) in open_containers:
        return f"{open_containers[id(value)]} contains itself, which JSON cannot hold"
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                return f"{where} has the key {key!r}, which is not text"
            children.append((f"{where}[{key!r}]", item))
    elif isinstance(value, (list, tuple)):
        children = [(f"{where}[{index}]", item) for index, item in enumerate(value)]
    elif value is not None and not isinstance(value, (str, int, float)):
        return f"{where} is of type {type(value).__name__}, which is not JSON"
    if not children:
        return None
    open_containers[id(value)] = where
    try:
        return next(
            (problem for path, item in children if (problem := _not_json(item, path, open_containers)) is not None),
            None,
        )
    finally:
        del open_containers[id(value)]


def _require_enabled(enabled: object, /) -> None:
    """Refuse an ``enabled`` filter that is not ``True``, ``False`` or ``None``.

    A filter compares each row's state with the value, so any other value would match nothing and
    answer an empty result rather than raise.

    Raises:
        TypeError: If ``enabled`` is neither a ``bool`` nor ``None``.
    """
    if enabled is not None and not isinstance(enabled, bool):
        raise TypeError(f"enabled must be True, False or None, not {type(enabled).__name__}")


def _require_text(name: str, value: object, /) -> None:
    """Refuse an argument that must be text, before it is compared with what is stored.

    Raises:
        TypeError: If ``value`` is not a ``str``.
    """
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, not {type(value).__name__}")


def _require_version(expected_version: object, /) -> None:
    """Refuse an expected version that is neither an integer from 0 nor ``None``.

    Storage compares it with the stored row's version, so any other value would read as a
    conflict rather than as the mistake it is. ``True`` is the integer 1, as it is for ``limit``.

    Raises:
        TypeError: If ``expected_version`` is neither an ``int`` nor ``None``.
        TaxomeshValidationError: If ``expected_version`` is below 0, which no stored row is at.
    """
    if expected_version is None:
        return
    if not isinstance(expected_version, int):
        raise TypeError(f"expected_version must be an int or None, not {type(expected_version).__name__}")
    if expected_version < 0:
        raise TaxomeshValidationError(f"expected_version must be ≥ 0, got {expected_version}")


def _require_sequence(name: str, value: object, /) -> None:
    """Refuse an order that is not a sequence, before any element of it is read.

    A set or a mapping holds no order of the caller's, so storing its iteration order would store
    an order nobody gave, as ``random.sample`` refuses a set.

    Raises:
        TypeError: If ``value`` is not a ``Sequence``.
    """
    if not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a sequence, not {type(value).__name__}")


def _require_collection(name: str, value: object, /) -> None:
    """Refuse a batch argument that is neither one value nor a collection of them.

    A batch lookup takes one value as a one-item collection before this check, so what reaches it
    is meant as a collection. Anything Python cannot iterate would otherwise fail inside the
    lookup, with a message naming no argument.

    Raises:
        TypeError: If ``value`` is not iterable.
    """
    if not isinstance(value, Iterable):
        raise TypeError(f"{name} must be one value or a collection of them, not {type(value).__name__}")


def _require_limit(limit: object, /) -> None:
    """Refuse a result limit that is not an integer of at least 1.

    A float is the wrong type however many rows match. ``NaN``, which compares false with
    everything, would otherwise pass a range check and cap nothing.

    Raises:
        TypeError: If ``limit`` is not an ``int``.
        TaxomeshValidationError: If ``limit`` is less than 1.
    """
    if not isinstance(limit, int):
        raise TypeError(f"limit must be an int, not {type(limit).__name__}")
    if limit < 1:
        raise TaxomeshValidationError(f"limit must be ≥ 1, got {limit}")


def _given(fields: Mapping[str, object], /) -> dict[str, object]:
    """Return the fields an update was given a value for.

    ``UNSET`` keeps a field as it is, so it is left out. ``None`` is not a value of any field passed
    here: each ``update`` handles ``external_id``, the one nullable field, itself. The check is
    here, and not in the model, because the model reads a stored ``None`` description as empty.

    Args:
        fields: Each field's argument, by name.

    Returns:
        The fields to change, with their new values.

    Raises:
        TypeError: If a field is ``None``, the wrong type for it, naming each such field.
    """
    refused = [name for name, value in fields.items() if value is None]
    if refused:
        raise TypeError("; ".join(f"{name} cannot be None: UNSET keeps the stored value" for name in refused))
    return {name: value for name, value in fields.items() if value is not UNSET}


def _changed[R: BaseModel](row: R, changes: Mapping[str, object], /) -> R:
    """Return a new row with these fields changed, checked as a new row would be.

    ``model_copy(update=…)`` checks nothing, so a name past its limit would pass it. The new row
    is validated from the original's fields instead, with the changes laid over them, so every
    check the model makes runs again. The original is left as it was.

    Args:
        row: The row to change. It is not modified.
        changes: The new value of each field that changes.

    Returns:
        A new row of the same model.

    Raises:
        TypeError: If a change is of a type the model does not take, chained to pydantic's error.
        TaxomeshValidationError: If the model refuses a value, chained to pydantic's error.
    """
    with _as_validation_error():
        return type(row).model_validate({**row.model_dump(), **changes})


class EntityCollectionBase[T, K](ABC):
    """The stored rows of one kind of entity, reached as a Python container is reached.

    This base makes the law part of the structure:

        Subscript raises. Anything named ``get*`` never does.

    ``get`` and ``__contains__`` are written **once, here**, both through the subclass's
    ``__getitem__``. So they cannot come to disagree, as three lookups written apart could:
    ``key in coll`` is true exactly when ``coll[key]`` does not raise, because it is the same call.

    It is **not** a ``collections.abc.Mapping``, on purpose. ``Mapping`` requires an ``__iter__``
    that yields keys, and builds ``keys()``, ``items()``, ``values()`` and ``==`` on it: to iterate
    a view, or to compare with another mapping, reads every row, and the call does not show that
    cost. ``__iter__`` and ``__reversed__`` are ``None``, not left undefined. Through Python's old
    sequence protocol, a class with ``__getitem__`` is iterable all the same, and with ``__len__``
    it is also reversible. Then ``iter()`` succeeds, and ``reversed()`` succeeds after it reads
    every row to take the length. The first ``next()`` calls ``coll[0]`` or ``coll[len(coll) - 1]``,
    which raises ``TypeError`` for an integer key that the caller did not give; over an empty
    store, ``reversed()`` yields nothing. ``None`` makes ``iter()`` and ``reversed()`` raise
    ``TypeError`` at once, as ``Mapping`` itself does for ``reversed()``.

    ``T`` is the row and ``K`` what names one: ``CategoryRef``, ``ItemRef`` or ``TagRef``, the row
    or its identifier. ``T`` is only in **return** positions and ``K`` only in parameters, so the
    class is covariant in ``T`` and contravariant in ``K``: every concrete collection is a subtype
    of ``EntityCollectionBase[object, UUID]``, so one parametrized test can state the law for the
    three kinds of entity with no ``Any``, no cast and no ``type: ignore``. A ``T`` in a parameter
    would reverse that inference, which is also why :meth:`_all` returns ``Sequence[T]`` and not
    the invariant ``list[T]``.

    A subclass sets :attr:`_not_found` to its own ``TaxomeshNotFoundError`` subclass, so a caller
    that catches the error of one kind never gets the error of another kind, and
    :attr:`_namespace` to the service attribute that it is reached through.
    """

    _not_found: ClassVar[type[TaxomeshNotFoundError]]
    _namespace: ClassVar[str]
    __iter__: ClassVar[None] = None
    __reversed__: ClassVar[None] = None

    def __init__(self, service: TaxomeshService, *, cache: ReadCache) -> None:
        """Bind the collection to the service that owns it.

        ``TaxomeshService.__init__`` builds the collections once, and a caller never constructs
        one, because the cache that a collection reads through is the service's.

        Args:
            service: The service that owns the collection. The collection reaches storage through
                its public ``repository`` property, never through a private attribute.
            cache: The service's cache, which holds this collection's memoized reads and which
                a write through this collection clears.
        """
        self._service = service
        self._cache = cache

    def __repr__(self) -> str:
        """Render as the expression that reaches this collection, reading no storage.

        The attribute path, and not a constructor call, because a collection is never
        constructed directly.
        """
        return f"{self._service!r}.{self._namespace}"

    @abstractmethod
    def __getitem__(self, key: K, /) -> T:
        """Return the row this names, or raise.

        Each subclass implements it over the port's lookup of one row, and turns a miss (and, for
        categories, the implicit root) into its own not-found error. The rest of the law is built
        on this one method.

        Args:
            key: The row, or its identifier. Only the identifier is read.

        Returns:
            The stored row.

        Raises:
            TaxomeshNotFoundError: The subclass's own subclass of it, when the row is not stored.
            TypeError: If ``key`` is neither a row of this kind nor a ``UUID``.
        """

    @abstractmethod
    def _all(self) -> Sequence[T]:
        """Return every stored row, unfiltered."""

    @contextmanager
    def _atomic(self, *, then: Callable[[], None] | None = None) -> Iterator[None]:
        """Run a member's storage writes in one ``atomic()`` block, then clear the service's cache.

        The method clears the service's cache, and calls ``then``, whether the writes end or fail:
        a store that cannot roll back keeps the writes made before a failure, and the next read
        must see them.

        Args:
            then: Called last. A member that changes rows passes the method that drops its search
                corpus.
        """
        try:
            with self._service.repository.atomic():
                yield
        finally:
            self._cache.clear()
            if then is not None:
                then()

    @abstractmethod
    def get_many(self, keys: K | Collection[K], /) -> Mapping[UUID, T]:
        """Return the rows these name, keyed by identifier.

        One row or identifier is one key, as ``str.startswith`` takes one prefix or a tuple of
        them.

        An absent key is **left out of the result**: it does not raise, and it does not appear with
        a ``None`` value. Either of those would make every caller write the same check, and
        ``get_many`` exists to remove that check.

        Args:
            keys: The row or identifier to look up, or a collection of them. A duplicate or an
                absent key causes no error.

        Returns:
            A mapping of identifier to row, with only the keys that were found.

        Raises:
            TypeError: If ``keys`` is neither one key nor a collection, or a key is neither a row
                of this kind nor a ``UUID``.
        """

    @abstractmethod
    def delete(self, key: K, /) -> None:
        """Delete the row this names.

        Args:
            key: The row to delete, or its identifier.

        Raises:
            TaxomeshNotFoundError: The subclass's own subclass of it, when the row is not stored.
            TypeError: If ``key`` is neither a row of this kind nor a ``UUID``.
        """

    @overload
    def get(self, key: K, /) -> T | None: ...

    @overload
    def get[D](self, key: K, default: D, /) -> T | D: ...

    def get[D](self, key: K, default: D | None = None, /) -> T | D | None:
        """Return the row this names, or a default instead of raising.

        The other half of subscript, and the reason that both forms exist: ``coll[key]`` asks for
        a row that must be stored, and ``coll.get(key)`` asks *whether* it is stored. Both
        parameters are positional-only, as on ``dict``.

        Args:
            key: The row, or its identifier.
            default: Returned when the row is absent. Defaults to ``None``.

        Returns:
            The stored row, or ``default`` when the row is not stored.

        Raises:
            TypeError: If ``key`` is neither a row of this kind nor a ``UUID``: a wrong type is
                not an absence.
        """
        try:
            return self[key]
        except self._not_found:
            return default

    def __contains__(self, key: K) -> bool:
        """Return whether the row this names is stored.

        Args:
            key: The row, or its identifier.

        Returns:
            ``True`` exactly when ``self[key]`` would not raise a not-found error.

        Raises:
            TypeError: If ``key`` is neither a row of this kind nor a ``UUID``.
        """
        try:
            self[key]
        except self._not_found:
            return False
        return True

    def __len__(self) -> int:
        """Return how many rows are stored, counting the same rows that ``in`` finds.

        Note:
            **This reads every stored row.** The port has no count method, so the only correct
            implementation reads every row and counts them. Use ``len(coll.list(...))`` only when
            you need the rows too. A truth test, ``if coll:``, calls this method as well.

        Returns:
            The number of stored rows, unfiltered by enabled state.
        """
        return len(self._all())

    def __delitem__(self, key: K, /) -> None:
        """Delete the row this names: the same operation as :meth:`delete`.

        Args:
            key: The row to delete, or its identifier.

        Raises:
            TaxomeshNotFoundError: The subclass's own subclass of it, when the row is not stored.
            TypeError: If ``key`` is neither a row of this kind nor a ``UUID``.
        """
        self.delete(key)
