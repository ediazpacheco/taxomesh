"""TTL read cache: a memoize decorator with a typed insert and lookup path.

``memoize(ttl)`` returns a :class:`MemoizedFunction`. Because that is a class with
``__get__`` it is a descriptor, so it binds as a method and ``prime`` and ``cached`` are
ordinary typed methods on the decorated callable rather than a module-level helper
reaching into a closure. (A ``Protocol`` return type cannot do this: a Protocol attribute
is not a descriptor, so method binding stops working. See spec 061 research.md R2.)

Three invariants the rest of the library depends on:

* **``cached`` never writes.** Not the value, not the timestamp. An entry's lifetime is
  measured from the fetch that produced it and is never extended by a later lookup, so
  consulting the cache on a hot path cannot turn the TTL into sliding expiry.
* **One cache per decorated function, registered once.** A bound instance is part of the
  *key*, never a separate store, so ``clear_all_caches()`` reaches every entry.
* **``time`` is read through the module global at call time**, so a test can substitute
  the clock.
"""

import time
from collections.abc import Callable, Hashable
from typing import Concatenate, Self, overload

_cache_registry: list[Callable[[], None]] = []


def clear_all_caches() -> None:
    """Clear all memoized caches in the registry."""
    for clear_fn in _cache_registry:
        clear_fn()


class Miss:
    """Singleton marking the absence of a fresh cache entry.

    Returned by :meth:`MemoizedFunction.cached` instead of ``None``, so that a genuinely
    cached ``None`` — or any other falsy value — stays distinguishable from a miss.
    """

    _instance: "Miss | None" = None

    def __new__(cls) -> "Miss":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISS"


MISS = Miss()


class MemoizedMethod[**P, R]:
    """A :class:`MemoizedFunction` seen through an instance.

    Holds no cache of its own: it supplies the bound instance as the leading argument, so
    every entry lives in the owner's single cache and ``clear_all_caches()`` reaches it.
    """

    # ``owner`` is gradual in its PARAMETERS and precise in its return type. It cannot be
    # made precise: a bound view generic in the instance type would need a ``cast`` inside
    # ``MemoizedFunction.__get__``, whose body mypy checks once and generically, and the
    # instance type appears in no signature below — it would be a phantom parameter. The
    # gradualness stops here: ``__call__``, ``prime``, ``cached`` and ``clear_cache`` are
    # all stated in ``P`` and ``R``, so nothing gradual reaches a call site. See spec 061
    # research.md R2 and the plan's Complexity Tracking.
    def __init__(self, owner: "MemoizedFunction[..., R]", instance: object) -> None:
        self._owner = owner
        self._instance = instance

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._owner(self._instance, *args, **kwargs)

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        """Insert ``value`` as the cached result of calling this method with these arguments."""
        self._owner.prime(value, self._instance, *args, **kwargs)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        """Return the fresh cached value for these arguments, or :data:`MISS`."""
        return self._owner.cached(self._instance, *args, **kwargs)

    def clear_cache(self) -> None:
        """Clear the whole cache of the underlying callable."""
        self._owner.clear_cache()


class MemoizedFunction[**P, R]:
    """A callable that caches its results for ``ttl`` seconds.

    Returned by :func:`memoize`. Accessing it on an instance yields a
    :class:`MemoizedMethod` bound to that instance.
    """

    def __init__(self, func: Callable[P, R], ttl: float) -> None:
        self._func = func
        self._ttl = ttl
        self._cache: dict[Hashable, tuple[float, R]] = {}
        # Carried deliberately: ``functools.wraps`` does not apply to a class instance, and
        # without these a decorated method would report the cache class's name and
        # docstring to ``help()``, every IDE, and ``inspect.signature``.
        self.__name__ = getattr(func, "__name__", "memoized")
        self.__qualname__ = getattr(func, "__qualname__", self.__name__)
        self.__module__ = getattr(func, "__module__", __name__)
        self.__doc__ = func.__doc__
        self.__wrapped__ = func
        _cache_registry.append(self.clear_cache)

    @staticmethod
    def _key(args: tuple[object, ...], kwargs: dict[str, object]) -> Hashable | None:
        """Build the cache key, or ``None`` when the arguments cannot be hashed.

        Single source of truth: the call path, the insert path and the lookup path must
        agree on the key, and a silent disagreement would cost a read rather than raise.
        """
        try:
            key = (args, tuple(sorted(kwargs.items())))
            hash(key)
        except TypeError:
            return None
        return key

    def _fresh_value(self, key: Hashable) -> R | Miss:
        """Return the entry's value if it exists and has not expired, else :data:`MISS`."""
        entry = self._cache.get(key)
        if entry is None:
            return MISS
        stored_at, value = entry
        return value if time.monotonic() - stored_at < self._ttl else MISS

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        key = self._key(args, kwargs)
        if key is None:
            return self._func(*args, **kwargs)
        hit = self._fresh_value(key)
        if not isinstance(hit, Miss):
            return hit
        result = self._func(*args, **kwargs)
        self._cache[key] = (time.monotonic(), result)
        return result

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        """Insert ``value`` as the cached result of calling with these arguments.

        Lets a caller that has already fetched rows in one batch populate the cache of the
        per-row accessor, so a later lookup of one of those rows is served from memory
        instead of going back to storage.

        The entry written is indistinguishable from one a call would have stored: same key,
        same lifetime, cleared by the same :func:`clear_all_caches`. Priming therefore
        introduces no staleness window a normal call does not already have.

        Args:
            value: The value to cache. Type-checked against this callable's return type.
            *args: Positional arguments identifying the entry, as they would be passed in.
            **kwargs: Keyword arguments identifying the entry.
        """
        key = self._key(args, kwargs)
        if key is not None:
            self._cache[key] = (time.monotonic(), value)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        """Return the fresh cached value for these arguments, or :data:`MISS`.

        Strictly read-only — it never writes, refreshes or evicts an entry, so consulting
        the cache cannot extend an entry's lifetime. An expired entry reports as a miss, as
        do arguments the cache cannot key.

        Args:
            *args: Positional arguments identifying the entry.
            **kwargs: Keyword arguments identifying the entry.

        Returns:
            The cached value, or :data:`MISS` when there is no fresh entry. Compare with
            ``isinstance(hit, Miss)`` rather than truthiness — ``None`` and other falsy
            values are legitimate cached results.
        """
        key = self._key(args, kwargs)
        return MISS if key is None else self._fresh_value(key)

    def clear_cache(self) -> None:
        """Discard every entry of this callable's cache."""
        self._cache.clear()

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...
    @overload
    def __get__[S, **Q](
        self: "MemoizedFunction[Concatenate[S, Q], R]", instance: S, owner: type[S]
    ) -> MemoizedMethod[Q, R]: ...
    def __get__(self, instance: object, owner: type[object]) -> "Self | MemoizedMethod[..., R]":
        if instance is None:
            return self
        return MemoizedMethod(self, instance)


def memoize[**P, R](ttl: float) -> Callable[[Callable[P, R]], MemoizedFunction[P, R]]:
    """Decorator that caches function results for ``ttl`` seconds.

    Cache keys are derived from positional and keyword arguments. If arguments are
    unhashable the function is called without caching.

    The decorated callable gains :meth:`~MemoizedFunction.prime`,
    :meth:`~MemoizedFunction.cached` and :meth:`~MemoizedFunction.clear_cache`, and keeps
    its own name, docstring and signature.

    Args:
        ttl: Time-to-live in seconds for cached entries.

    Returns:
        A decorator producing a :class:`MemoizedFunction`.
    """

    def decorator(func: Callable[P, R]) -> MemoizedFunction[P, R]:
        return MemoizedFunction(func, ttl)

    return decorator
