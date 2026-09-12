"""Prototype: a class-based memoized-method descriptor, checked under mypy --strict.

Question: does mypy bind a generic descriptor class correctly (unlike the Protocol
return type recorded as a dead end in 061 research.md R2), and does it type-check
prime/lookup against the decorated method's own signature and return type?
"""

import time
from collections.abc import Callable, Hashable
from typing import Concatenate, Self, overload


class BoundMemoized[**P, R]:
    def __init__(self, cache: dict[Hashable, tuple[float, R]], func: Callable[P, R], ttl: float) -> None:
        self._cache = cache
        self._func = func
        self._ttl = ttl

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        key = (args, tuple(sorted(kwargs.items())))
        hit = self._cache.get(key)
        if hit is not None and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        value = self._func(*args, **kwargs)
        self._cache[key] = (time.monotonic(), value)
        return value

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        self._cache[(args, tuple(sorted(kwargs.items())))] = (time.monotonic(), value)


class MemoizedMethod[S, **P, R]:
    def __init__(self, func: Callable[Concatenate[S, P], R], ttl: float) -> None:
        self._func = func
        self._ttl = ttl
        self._caches: dict[int, dict[Hashable, tuple[float, R]]] = {}

    @overload
    def __get__(self, instance: None, owner: type[S]) -> Self: ...
    @overload
    def __get__(self, instance: S, owner: type[S]) -> BoundMemoized[P, R]: ...
    def __get__(self, instance: S | None, owner: type[S]) -> Self | BoundMemoized[P, R]:
        if instance is None:
            return self
        cache = self._caches.setdefault(id(instance), {})

        def bound(*args: P.args, **kwargs: P.kwargs) -> R:
            return self._func(instance, *args, **kwargs)

        return BoundMemoized(cache, bound, self._ttl)


def memoized[S, **P, R](ttl: float) -> Callable[[Callable[Concatenate[S, P], R]], MemoizedMethod[S, P, R]]:
    def decorate(func: Callable[Concatenate[S, P], R]) -> MemoizedMethod[S, P, R]:
        return MemoizedMethod(func, ttl)

    return decorate


class Service:
    @memoized(5.0)
    def get_category(self, category_id: int) -> str:
        return f"cat-{category_id}"

    def use(self) -> str:
        self.get_category.prime("primed", 7)
        return self.get_category(7)


svc = Service()
assert svc.use() == "primed"
value: str = svc.get_category(1)
reveal_type(svc.get_category)
