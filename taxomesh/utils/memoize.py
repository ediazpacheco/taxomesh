"""Simple TTL-based memoize decorator with cache registry."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

_cache_registry: list[Callable[[], None]] = []


def clear_all_caches() -> None:
    """Clear all memoized caches in the registry."""
    for clear_fn in _cache_registry:
        clear_fn()


def memoize(ttl: float) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that caches function results for ``ttl`` seconds.

    Cache keys are derived from positional and keyword arguments. If arguments
    are unhashable the function is called without caching.

    The decorated function gains a ``clear_cache()`` attribute to manually
    invalidate its cache.

    Args:
        ttl: Time-to-live in seconds for cached entries.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        cache: dict[Any, tuple[float, R]] = {}

        def clear_cache() -> None:
            cache.clear()

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                key = (args, tuple(sorted(kwargs.items())))
                hash(key)
            except TypeError:
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
        _cache_registry.append(clear_cache)
        return wrapper

    return decorator
