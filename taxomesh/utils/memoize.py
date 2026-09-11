"""Simple TTL-based memoize decorator with cache registry."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

P = ParamSpec("P")
R = TypeVar("R")

_cache_registry: list[Callable[[], None]] = []

# Attribute under which a memoized wrapper exposes its insert path. Private by
# convention: callers reach it through ``prime()``, never by getattr.
_PRIME_ATTR = "_memoize_prime"

# Signature of that attribute: (value, args, kwargs) -> None.
_Primer = Callable[[Any, tuple[Any, ...], dict[str, Any]], None]


def clear_all_caches() -> None:
    """Clear all memoized caches in the registry."""
    for clear_fn in _cache_registry:
        clear_fn()


def prime[**P, R](func: Callable[P, R], value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
    """Insert ``value`` as the cached result of calling ``func`` with these arguments.

    Lets a caller that has already fetched rows in one batch populate the cache of the
    per-row accessor, so a later lookup of one of those rows is served from memory
    instead of going back to storage.

    The entry written is indistinguishable from one the accessor itself would have
    stored: same key, same TTL, cleared by the same ``clear_all_caches()``. Priming
    therefore introduces no staleness window that a normal call does not already have.

    For a decorated *method*, pass the unbound function and the instance explicitly —
    the cache key includes ``self``::

        prime(TaxomeshService.get_category, category, self, category.category_id)

    Args:
        func: The memoized function whose cache should be populated. A function that is
            not memoized is accepted and ignored, so callers need not check.
        value: The value to cache. Type-checked against ``func``'s return type.
        *args: Positional arguments identifying the cache entry, as they would be passed
            to ``func``.
        **kwargs: Keyword arguments identifying the cache entry.
    """
    primer = getattr(func, _PRIME_ATTR, None)
    if primer is None:
        return
    cast(_Primer, primer)(value, args, kwargs)


def memoize(ttl: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that caches function results for ``ttl`` seconds.

    Cache keys are derived from positional and keyword arguments. If arguments
    are unhashable the function is called without caching.

    The decorated function gains a ``clear_cache()`` attribute to manually
    invalidate its cache, and an insert path reachable through :func:`prime`.

    Args:
        ttl: Time-to-live in seconds for cached entries.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        cache: dict[Any, tuple[float, R]] = {}

        def cache_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
            """Build the cache key, or None when the arguments cannot be hashed.

            Single source of truth: the wrapper and the insert path must agree on the
            key, and a silent disagreement would cost a read rather than raise.
            """
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
                return None
            return key

        def clear_cache() -> None:
            cache.clear()

        def prime_entry(value: R, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            key = cache_key(args, kwargs)
            if key is None:
                return
            cache[key] = (time.monotonic(), value)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = cache_key(args, kwargs)
            if key is None:
                return func(*args, **kwargs)

            now = time.monotonic()
            if key in cache:
                cached_time, cached_value = cache[key]
                if now - cached_time < ttl:
                    return cached_value

            result = func(*args, **kwargs)
            cache[key] = (now, result)
            return result

        wrapper.clear_cache = clear_cache  # type: ignore[attr-defined]
        setattr(wrapper, _PRIME_ATTR, prime_entry)
        _cache_registry.append(clear_cache)
        return wrapper

    return decorator
