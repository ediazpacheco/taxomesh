"""The read cache: one ``ReadCache`` for each service, and a decorator that keeps its entries there.

A service builds one :class:`ReadCache` with its lifetime and gives it to its collections, and
each of them keeps it as ``_cache``. ``@memoize`` on a method of such an object returns a
:class:`MemoizedFunction`. That class has ``__get__``, so it is a descriptor and binds as a
method. So ``prime`` and ``cached`` are typed methods of the bound member, and not a module-level
helper that reads a closure.

The rest of the library depends on five invariants:

* **The entries belong to the cache.** They are keyed by the member and the arguments, so
  ``ReadCache.clear()`` reaches every entry of every member, and nothing outside the objects that
  hold the cache keeps one alive.
* **``cached`` never writes**: not the value, and not the timestamp. The lifetime of an entry
  starts at the read that made it, and a later lookup never extends it. So a lookup that runs
  often cannot turn the lifetime into a sliding expiry.
* **An expired entry is dropped when its member stores the next one.** So a member holds the keys
  of one lifetime at most, however many keys it is asked about over time.
* **A lifetime of zero stores nothing.** Every call is computed, ``prime`` stores nothing and
  ``cached`` answers :data:`MISS`.
* **``time`` is read through the module global at call time**, so a test can replace the clock.
"""

import threading
import time
from collections.abc import Callable, Hashable
from types import MethodType
from typing import Any, Concatenate, Protocol, Self, overload


class Miss:
    """The one object that marks the absence of a fresh cache entry.

    :meth:`MemoizedMethod.cached` returns it instead of ``None``, so that a cached ``None``, or
    any other falsy value, is not taken for a miss.
    """

    _instance: "Miss | None" = None

    def __new__(cls) -> "Miss":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISS"


MISS = Miss()


class ReadCache:
    """The memoized reads of one service: their lifetime, and one clear that reaches them all.

    The service builds it and gives it to each of its collections, so a write through any of
    them clears every read the service cached, and no other service's.
    """

    def __init__(self, ttl: float) -> None:
        """Start empty.

        Args:
            ttl: Seconds an entry is served from memory. Zero or less stores nothing.
        """
        self._ttl = ttl
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
        """Return the seconds an entry is served from memory."""
        return self._ttl

    @property
    def enabled(self) -> bool:
        """Return whether this cache stores anything: ``False`` when the lifetime is not positive."""
        return self._ttl > 0

    def now(self) -> float:
        """Return the clock reading an entry is stamped with."""
        return time.monotonic()

    def is_fresh(self, stamp: float) -> bool:
        """Return whether a value stamped at ``stamp`` is still within the lifetime."""
        return self.now() - stamp < self._ttl

    # Any: the member's owner and parameters; only its return type reaches the store.
    def entries[R](self, member: "MemoizedFunction[Any, ..., R]", /) -> dict[Hashable, tuple[float, R]]:
        """Return this member's entries, keyed by its arguments, each with the time it was stored.

        Args:
            member: The memoized member, as its class holds it.

        Returns:
            The member's own store, created empty the first time it is asked for, in the order its
            entries were stored.
        """
        return self._entries.setdefault(member, {})

    # Any: the member's owner and parameters; only its return type reaches the store.
    def store[R](self, member: "MemoizedFunction[Any, ..., R]", key: Hashable, value: R, /) -> None:
        """Store ``value`` as this member's entry for ``key``, and drop the member's expired entries.

        The entry goes to the end of the member's store, so the store stays in the order of its
        stamps, and every expired entry is at the front, where this method drops it.

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

    Holds no entries of its own: they are in the instance's :class:`ReadCache`, under the member
    of this view.

    It shows the method it wraps, as a bound method does: its ``__name__``, ``__qualname__`` and
    ``__doc__``, and as ``__wrapped__`` the function bound to the instance, through which
    ``inspect.signature`` reports the method's parameters without ``self``. ``help()``, an IDE and
    ``inspect.signature`` get this view and not the class member, so without these attributes
    each would describe the cache class.
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
        """Render as a bound method does, naming the method and the instance it is bound to."""
        return f"<memoized bound method {self.__qualname__} of {self._instance!r}>"

    def _key(self, args: tuple[object, ...], kwargs: dict[str, object]) -> Hashable | None:
        """Build the entry's key, or ``None`` when nothing may be stored for these arguments.

        The one place that builds the key: a call, an insert and a lookup must agree on the key,
        and a disagreement would cost a read and raise no error. Nothing is stored when the
        cache's lifetime is not positive, or when the arguments cannot be hashed.
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

        A caller that read rows in one batch puts them in the cache of the per-row accessor, so
        a later lookup of one of those rows is served from memory and does not read storage.

        The entry is the same as one that a call would store: the same key, the same lifetime,
        cleared by the same :meth:`ReadCache.clear`, and stored the same way, so it also drops
        the member's expired entries. So priming makes no read staler than a call does, and
        stores nothing where a call would store nothing.

        Args:
            value: The value to cache. Type-checked against this method's return type.
            *args: The positional arguments that identify the entry, as a call would pass them.
            **kwargs: The keyword arguments that identify the entry.
        """
        key = self._key(args, kwargs)
        if key is not None:
            self._cache.store(self._member, key, value)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        """Return the fresh cached value for these arguments, or :data:`MISS`.

        Read-only: it never writes, refreshes or drops an entry, so a lookup cannot extend the
        lifetime of an entry. An expired entry is a miss, and so are arguments that the cache
        cannot use as a key.

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
        """Discard this member's entries in the instance's cache, leaving every other member's."""
        self._cache.entries(self._member).clear()


class MemoizedFunction[S: CacheOwnerBase, **P, R]:
    """A method whose results are held in its instance's :class:`ReadCache`.

    Returned by :func:`memoize`. Read on an instance, it returns a :class:`MemoizedMethod` bound
    to that instance. Read on the class, it returns this object, which is the key of the member's
    entries in the instance's cache.
    """

    def __init__(self, func: Callable[Concatenate[S, P], R]) -> None:
        self.__wrapped__ = func
        # Copied here because ``functools.wraps`` does not apply to a class instance. Without
        # these, a decorated method would report the name and the docstring of the cache class
        # to ``help()``, every IDE and ``inspect.signature``.
        self.__name__: str = getattr(func, "__name__", "memoized")
        self.__qualname__: str = getattr(func, "__qualname__", self.__name__)
        self.__module__ = getattr(func, "__module__", __name__)
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

    The instance keeps the cache as ``_cache``. Entries are keyed by the positional and keyword
    arguments; a call with arguments that cannot be hashed is computed and not cached. Each entry
    is served for the cache's lifetime, which is read when the call is made.

    The bound member gets :meth:`~MemoizedMethod.prime`, :meth:`~MemoizedMethod.cached` and
    :meth:`~MemoizedMethod.clear_cache`, and keeps its own name, docstring and signature.

    Args:
        func: The method to decorate.

    Returns:
        A :class:`MemoizedFunction`.
    """
    return MemoizedFunction(func)
