"""The read cache: one ``ReadCache`` for each service, and a decorator that keeps its entries there.

A service builds one :class:`ReadCache` with its lifetime and gives it to its collections. Each
of them keeps it as ``_cache``. ``@memoize`` on a method of such an object returns a
:class:`MemoizedFunction`. That class has ``__get__``, so it is a descriptor and binds as a
method. So ``prime`` and ``cached`` are typed methods of the bound member, and not a module-level
helper that reads a closure.

The rest of the library depends on six invariants:

* **The entries belong to the cache.** The cache keys them by the member and the arguments. So
  ``ReadCache.clear()`` reaches every entry of every member. Nothing outside the objects that
  hold the cache keeps an entry alive.
* **``cached`` never writes**: not the value, and not the timestamp. The lifetime of an entry
  starts at the read that made it, and a later lookup never extends it. So a lookup that runs
  often cannot turn the lifetime into a sliding expiry.
* **The cache drops an expired entry when its member stores the next one.** So a member holds the
  keys of one lifetime at most, however many keys its callers ask it about over time.
* **A lifetime of zero stores nothing.** Every call computes its result, ``prime`` stores nothing
  and ``cached`` answers :data:`MISS`.
* **A suspended cache stores and serves nothing.** While the predicate that the owner gives the
  cache answers ``True``, the cache behaves as one with a lifetime of zero. It keeps its entries
  for later.
* **The cache reads ``time`` through the module global at call time**, so a test can replace the
  clock.
"""

import threading
import time
from collections.abc import Callable, Hashable
from enum import Enum
from types import MethodType
from typing import Any, Concatenate, Final, Protocol, Self, overload


class Miss(Enum):
    """The type of :data:`MISS`, the one object that marks the absence of a fresh cache entry.

    :meth:`MemoizedMethod.cached` returns it instead of ``None``. So a caller does not read a
    cached ``None``, or any other falsy value, as a miss. It is an ``Enum`` with one member, for
    the reasons that :class:`~taxomesh.domain.types.UnsetType` gives.
    """

    MISS = "MISS"

    def __repr__(self) -> str:
        return "MISS"

    def __str__(self) -> str:
        return "MISS"


MISS: Final[Miss] = Miss.MISS


class ReadCache:
    """The memoized reads of one service: their lifetime, and one clear that reaches them all.

    The service builds it and gives it to each of its collections. So a write through any of
    them clears every read that the service cached, and no other service's.
    """

    def __init__(self, ttl: float, *, suspended: Callable[[], bool] = lambda: False) -> None:
        """Start empty.

        Args:
            ttl: Seconds that the cache serves an entry from memory. Zero or less stores nothing.
            suspended: The cache asks it at each read. While it answers ``True``, the cache neither
                stores nor serves an entry. A service passes its repository's ``in_transaction``.
        """
        self._ttl = ttl
        self._suspended = suspended
        # Every store walks its member's entries, and a service may be shared across threads. The
        # lock is reentrant: a store hashes its key while holding it, and hashing a key may run code
        # that reads through this cache again, on the same thread. functools' own pure-Python
        # lru_cache takes an RLock too.
        self._storing = threading.RLock()
        # Any: one store per member. A member reads back only what it stored under its own key, so
        # each store's values are that member's return type; the map across members is
        # heterogeneous, which no static type states. ``entries`` recovers the type from the key.
        self._entries: dict[MemoizedFunction[Any, ..., Any], dict[Hashable, tuple[float, Any]]] = {}

    @property
    def ttl(self) -> float:
        """Return the seconds that the cache serves an entry from memory."""
        return self._ttl

    @property
    def enabled(self) -> bool:
        """Return whether this cache stores and serves entries now.

        ``False`` when the lifetime is not positive, and while the cache is suspended.
        """
        return self._ttl > 0 and not self._suspended()

    def now(self) -> float:
        """Return the clock reading that the cache stamps an entry with."""
        return time.monotonic()

    def is_fresh(self, stamp: float) -> bool:
        """Return whether a value stamped at ``stamp`` is still within the lifetime."""
        return self.now() - stamp < self._ttl

    # Any: the member's owner and parameters; only its return type reaches the store.
    def entries[R](self, member: "MemoizedFunction[Any, ..., R]", /) -> dict[Hashable, tuple[float, R]]:
        """Return this member's entries, keyed by its arguments, each with the time when the cache stored it.

        Args:
            member: The memoized member, as its class holds it.

        Returns:
            The member's own store, in the order in which the cache stored its entries. The cache
            creates the store empty at the first call for that member.
        """
        return self._entries.setdefault(member, {})

    # Any: the member's owner and parameters; only its return type reaches the store.
    def store[R](self, member: "MemoizedFunction[Any, ..., R]", key: Hashable, value: R, /) -> None:
        """Store ``value`` as this member's entry for ``key``, and drop the member's expired entries.

        The entry goes to the end of the member's store, so the store stays in the order of its
        stamps. Every expired entry is therefore at the front, where this method drops it.

        Args:
            member: The memoized member, as its class holds it.
            key: The entry's key, built from the call's arguments.
            value: The value to serve for the lifetime.
        """
        entries = self.entries(member)
        with self._storing:
            stamp = self.now()
            entries.pop(key, None)
            while entries:
                oldest = next(iter(entries))
                if stamp - entries[oldest][0] < self._ttl:
                    break
                del entries[oldest]
            entries[key] = (stamp, value)

    def clear(self) -> None:
        """Discard every entry of every member."""
        self._entries.clear()


class CacheOwnerBase(Protocol):
    """An object whose memoized reads live in a :class:`ReadCache`: a service, or a collection."""

    @property
    def _cache(self) -> ReadCache: ...


class MemoizedMethod[S: CacheOwnerBase, **P, R]:
    """A :class:`MemoizedFunction` seen through an instance.

    It holds no entries of its own. They are in the instance's :class:`ReadCache`, under the
    member of this view.

    It shows the method that it wraps, as a bound method does. It has the ``__name__``,
    ``__qualname__`` and ``__doc__`` of that method. Its ``__wrapped__`` is the function bound to
    the instance, through which ``inspect.signature`` reports the method's parameters without
    ``self``. ``help()``, an IDE and ``inspect.signature`` get this view and not the class member.
    So without these attributes each would describe the cache class.
    """

    def __init__(self, member: "MemoizedFunction[S, P, R]", instance: S) -> None:
        self._member = member
        self._instance = instance
        self._cache = instance._cache
        self.__name__ = member.__name__
        self.__qualname__ = member.__qualname__
        self.__doc__ = member.__doc__
        self.__wrapped__ = MethodType(member.__wrapped__, instance)

    def __repr__(self) -> str:
        """Return a text like that of a bound method, which names the method and the instance it is bound to."""
        return f"<memoized bound method {self.__qualname__} of {self._instance!r}>"

    def _key(self, args: tuple[object, ...], kwargs: dict[str, object]) -> Hashable | None:
        """Build the entry's key, or ``None`` when the cache may store nothing for these arguments.

        This is the one place that builds the key. A call, an insert and a lookup must agree on the
        key. A disagreement would cost a read and raise no error. The cache stores nothing when its
        lifetime is not positive, while it is suspended, or when the arguments cannot be hashed.
        """
        if not self._cache.enabled:
            return None
        try:
            key = (args, tuple(sorted(kwargs.items())))
            hash(key)
        except TypeError:
            return None
        return key

    def _fresh_value(self, key: Hashable) -> R | Miss:
        """Return the entry's value if it exists and has not expired, else :data:`MISS`."""
        entry = self._cache.entries(self._member).get(key)
        if entry is None:
            return MISS
        stored_at, value = entry
        return value if self._cache.is_fresh(stored_at) else MISS

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        key = self._key(args, kwargs)
        if key is None:
            return self._member.__wrapped__(self._instance, *args, **kwargs)
        hit = self._fresh_value(key)
        if not isinstance(hit, Miss):
            return hit
        result = self._member.__wrapped__(self._instance, *args, **kwargs)
        self._cache.store(self._member, key, result)
        return result

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        """Insert ``value`` as the cached result of calling this method with these arguments.

        A caller that read rows in one batch puts them in the cache of the per-row accessor. The
        cache then serves a later lookup of one of those rows from memory, with no storage read.

        The entry is the same as one that a call would store. It has the same key and the same
        lifetime, and the same :meth:`ReadCache.clear` clears it. The cache stores it the same way,
        so the insert also drops the member's expired entries. So priming makes no read staler than
        a call does, and stores nothing where a call would store nothing.

        Args:
            value: The value to cache. The type checker checks it against this method's return type.
            *args: The positional arguments that identify the entry, as a call would pass them.
            **kwargs: The keyword arguments that identify the entry.
        """
        key = self._key(args, kwargs)
        if key is not None:
            self._cache.store(self._member, key, value)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        """Return the fresh cached value for these arguments, or :data:`MISS`.

        The method is read-only. It never writes, refreshes or drops an entry, so a lookup cannot
        extend the lifetime of an entry. An expired entry is a miss, and so are arguments that the
        cache cannot use as a key.

        Args:
            *args: The positional arguments that identify the entry.
            **kwargs: The keyword arguments that identify the entry.

        Returns:
            The cached value, or :data:`MISS` when there is no fresh entry. Test the result with
            ``isinstance(hit, Miss)``, not with its truth value: ``None`` and other falsy values
            are valid cached results.
        """
        key = self._key(args, kwargs)
        return MISS if key is None else self._fresh_value(key)

    def clear_cache(self) -> None:
        """Discard this member's entries in the instance's cache, and leave every other member's."""
        self._cache.entries(self._member).clear()


class MemoizedFunction[S: CacheOwnerBase, **P, R]:
    """A method whose results are held in its instance's :class:`ReadCache`.

    :func:`memoize` returns it. Read on an instance, it returns a :class:`MemoizedMethod` bound
    to that instance. Read on the class, it returns this object, which is the key of the member's
    entries in the instance's cache.
    """

    def __init__(self, func: Callable[Concatenate[S, P], R]) -> None:
        self.__wrapped__ = func
        # Assigned one by one, and not with ``functools.update_wrapper``, so that the type checker
        # knows each attribute. Without them, a decorated method would report the name and the
        # docstring of this class to ``help()``, every IDE and ``inspect.signature``.
        self.__name__ = func.__name__
        self.__qualname__ = func.__qualname__
        self.__module__ = func.__module__
        self.__doc__ = func.__doc__

    def __call__(self, instance: S, /, *args: P.args, **kwargs: P.kwargs) -> R:
        """Call the method on ``instance``, through that instance's cache."""
        return MemoizedMethod(self, instance)(*args, **kwargs)

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...
    @overload
    def __get__(self, instance: S, owner: type[object]) -> MemoizedMethod[S, P, R]: ...
    def __get__(self, instance: S | None, owner: type[object]) -> "Self | MemoizedMethod[S, P, R]":
        if instance is None:
            return self
        return MemoizedMethod(self, instance)


def memoize[S: CacheOwnerBase, **P, R](func: Callable[Concatenate[S, P], R], /) -> MemoizedFunction[S, P, R]:
    """Decorate a method so its results are held in its instance's :class:`ReadCache`.

    The instance keeps the cache as ``_cache``. The cache keys the entries by the positional and
    keyword arguments. A call with arguments that cannot be hashed runs the method, and the cache
    does not store its result. The cache serves each entry for the cache's lifetime, and reads that
    lifetime at the time of the call.

    The bound member gets :meth:`~MemoizedMethod.prime`, :meth:`~MemoizedMethod.cached` and
    :meth:`~MemoizedMethod.clear_cache`, and keeps its own name, docstring and signature.

    Args:
        func: The method to decorate.

    Returns:
        A :class:`MemoizedFunction`.
    """
    return MemoizedFunction(func)
