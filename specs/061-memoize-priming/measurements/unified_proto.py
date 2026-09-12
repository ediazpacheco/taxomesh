"""One memoize class for plain functions (incl. zero-arg / kw-only) AND methods."""

import time
from collections.abc import Callable, Hashable
from typing import Concatenate, Self, overload


class BoundMemoized[**P, R]:
    def __init__(self, owner: "Memoized[..., R]", instance: object) -> None:
        self._owner = owner
        self._instance = instance

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._owner(self._instance, *args, **kwargs)  # type: ignore[arg-type]

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        self._owner.prime(value, self._instance, *args, **kwargs)  # type: ignore[arg-type]


class Memoized[**P, R]:
    def __init__(self, func: Callable[P, R], ttl: float) -> None:
        self._func = func
        self._ttl = ttl
        self._cache: dict[Hashable, tuple[float, R]] = {}

    @staticmethod
    def _key(args: tuple[object, ...], kwargs: dict[str, object]) -> Hashable:
        return (args, tuple(sorted(kwargs.items())))

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        key = self._key(args, kwargs)
        hit = self._cache.get(key)
        if hit is not None and time.monotonic() - hit[0] < self._ttl:
            return hit[1]
        value = self._func(*args, **kwargs)
        self._cache[key] = (time.monotonic(), value)
        return value

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        self._cache[self._key(args, kwargs)] = (time.monotonic(), value)

    @overload
    def __get__(self, instance: None, owner: type[object]) -> Self: ...
    @overload
    def __get__[S, **Q](self: "Memoized[Concatenate[S, Q], R]", instance: S, owner: type[S]) -> BoundMemoized[Q, R]: ...
    def __get__(self, instance: object, owner: type[object]) -> "Self | BoundMemoized[..., R]":
        return self if instance is None else BoundMemoized(self, instance)


def memoize[**P, R](ttl: float) -> Callable[[Callable[P, R]], Memoized[P, R]]:
    def decorate(func: Callable[P, R]) -> Memoized[P, R]:
        return Memoized(func, ttl)
    return decorate


@memoize(5.0)
def paths_from_main() -> dict[int, str]:          # zero-arg, like the consumer's
    return {1: "a"}

@memoize(5.0)
def mosaic(*, count: int = 8) -> list[int]:        # keyword-only, like the consumer's
    return list(range(count))

@memoize(5.0)
def tree(parent: int, *, depth: int = 3) -> list[str]:
    return [str(parent)] * depth

class Service:
    @memoize(5.0)
    def get_category(self, category_id: int) -> str:
        return f"cat-{category_id}"

    def use(self) -> str:
        self.get_category.prime("primed", 7)
        return self.get_category(7)

svc = Service()
assert svc.use() == "primed"
assert Service.get_category(svc, 7) == "primed"       # unbound call shares the cache
a: dict[int, str] = paths_from_main()
b: list[int] = mosaic(count=3)
c: list[str] = tree(1, depth=2)
paths_from_main.prime({2: "b"})
assert paths_from_main() == {2: "b"}
if __name__ == "__main__":
    print("runtime OK")
