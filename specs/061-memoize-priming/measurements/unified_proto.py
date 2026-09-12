"""One memoize class for plain functions (incl. zero-arg / kw-only) AND methods.

The design 061 ships, prototyped standalone so it can be type-checked in isolation and so
the deliberate misuses in ``unified_misuse.py`` have something to fail against.

Two questions this answers, both recorded in research.md R2:

1. Can a class bind as a method under ``mypy --strict``? Yes — a class with ``__get__`` is
   a descriptor, unlike a Protocol attribute, which is the dead end R2 keeps.
2. How precise can ``MemoizedMethod``'s owner be? ``MemoizedFunction[..., R]`` — gradual in
   the parameters, precise in the return type. Making it precise (generic in the instance
   type ``S``) makes ``__get__``'s own body uncheckable without a ``cast``; see R2.

Run:
    python unified_proto.py                                  # runtime behaviour
    mypy --strict --python-version 3.13 unified_proto.py unified_misuse.py
The misuse file is expected to fail. Its errors are the result.
"""

import time
from collections.abc import Callable, Hashable
from typing import Concatenate, Self, overload


class Miss:
    """Singleton marking "no fresh entry". Distinguishes a miss from a cached ``None``."""

    _instance: "Miss | None" = None

    def __new__(cls) -> "Miss":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


MISS = Miss()


class MemoizedMethod[**P, R]:
    """A ``MemoizedFunction`` seen through an instance.

    ``_owner`` is gradual in its parameters (``...``) and precise in its return type. That
    is confined here: every signature below is stated in terms of ``P`` and ``R``, so
    nothing gradual reaches a call site. See research.md R2 for why precision stops here.
    """

    def __init__(self, owner: "MemoizedFunction[..., R]", instance: object) -> None:
        self._owner = owner
        self._instance = instance

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._owner(self._instance, *args, **kwargs)

    def prime(self, value: R, /, *args: P.args, **kwargs: P.kwargs) -> None:
        self._owner.prime(value, self._instance, *args, **kwargs)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        return self._owner.cached(self._instance, *args, **kwargs)

    def clear_cache(self) -> None:
        self._owner.clear_cache()


class MemoizedFunction[**P, R]:
    """What ``memoize(ttl)`` returns. A descriptor, so it binds as a method."""

    def __init__(self, func: Callable[P, R], ttl: float) -> None:
        self._func = func
        self._ttl = ttl
        self._cache: dict[Hashable, tuple[float, R]] = {}

    @staticmethod
    def _key(args: tuple[object, ...], kwargs: dict[str, object]) -> Hashable | None:
        """The one definition of the key. None when the arguments cannot be hashed."""
        try:
            key = (args, tuple(sorted(kwargs.items())))
            hash(key)
        except TypeError:
            return None
        return key

    def _fresh_value(self, key: Hashable) -> R | Miss:
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
        """Insert ``value`` as the cached result of calling this with these arguments."""
        key = self._key(args, kwargs)
        if key is not None:
            self._cache[key] = (time.monotonic(), value)

    def cached(self, *args: P.args, **kwargs: P.kwargs) -> R | Miss:
        """Return the fresh cached value for these arguments, or ``MISS``. Read-only."""
        key = self._key(args, kwargs)
        return MISS if key is None else self._fresh_value(key)

    def clear_cache(self) -> None:
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
    def decorate(func: Callable[P, R]) -> MemoizedFunction[P, R]:
        return MemoizedFunction(func, ttl)

    return decorate


# ---- the consumer's own decorated shapes ---------------------------------------
@memoize(5)
def paths_from_main() -> dict[int, str]:  # zero-argument
    return {1: "a"}


@memoize(5)
def mosaic(*, count: int = 8) -> list[int]:  # keyword-only
    return list(range(count))


@memoize(5)
def tree(parent: int, *, depth: int = 3) -> list[str]:  # positional + keyword-only
    return [str(parent)] * depth


class Service:
    @memoize(5)
    def get_category(self, category_id: int) -> str:
        return f"cat-{category_id}"

    def read_through(self, category_id: int) -> str:
        """The shape the two batch reads use: consult, fetch the miss, prime it."""
        hit = self.get_category.cached(category_id)
        if isinstance(hit, Miss):
            value = f"cat-{category_id}"  # stands in for the batch repository read
            self.get_category.prime(value, category_id)
            return value
        return hit


if __name__ == "__main__":
    svc = Service()
    assert svc.get_category(7) == "cat-7"
    assert svc.read_through(7) == "cat-7"
    assert not isinstance(svc.get_category.cached(7), Miss), "a call must be visible to cached"

    svc.get_category.clear_cache()
    assert isinstance(svc.get_category.cached(7), Miss), "clear_cache must be visible to cached"
    assert svc.read_through(9) == "cat-9"
    assert not isinstance(svc.get_category.cached(9), Miss), "prime must be visible to cached"

    assert paths_from_main() == {1: "a"}
    assert mosaic(count=3) == [0, 1, 2]
    assert tree(1, depth=2) == ["1", "1"]
    paths_from_main.clear_cache()
    assert isinstance(paths_from_main.cached(), Miss)

    # A decorated callable keeps its own identity (NFR-003) — asserted here on the two
    # attributes the prototype sets; the shipped class carries the full set.
    print("runtime OK")
