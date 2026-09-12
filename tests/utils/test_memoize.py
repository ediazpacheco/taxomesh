"""Tests for the memoize cache (spec 061).

``memoize(ttl)`` returns a ``MemoizedFunction`` — a descriptor, so it binds as a method
and exposes ``prime`` and ``cached`` as typed methods on the decorated callable itself.

Two properties here are load-bearing elsewhere and are tested directly rather than
inferred:

* **``cached`` never writes.** Read-through consults the cache on every batch read; if a
  lookup refreshed the timestamp, a hot row would never expire and the 5-second TTL would
  silently become sliding expiry (spec 061 FR-003/FR-004).
* **One cache per decorated function, registered once.** ``clear_all_caches()`` has to
  reach every live cache — the Django query gates measure cold, and a cache it could not
  clear would make them report zero queries.
"""

import inspect
import time
from types import ModuleType
from typing import Any

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.utils import memoize as memoize_module
from taxomesh.utils.memoize import MISS, MemoizedFunction, Miss, clear_all_caches, memoize


class FakeClock:
    """Stands in for the ``time`` module inside ``memoize``.

    The production code must read ``time.monotonic()`` through the module global at call
    time — ``from time import monotonic`` or a clock captured in ``__init__`` would make
    this substitution silently ineffective, and would also break the two
    ``patch("taxomesh.utils.memoize.time")`` sites in ``tests/service/test_service_cache.py``.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(memoize_module, "time", fake)
    return fake


class TestMemoizeCacheHit:
    def test_same_args_returns_cached_result(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter(1)
        counter(1)
        assert call_count == 1

    def test_different_args_calls_function_again(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: str) -> str:
            nonlocal call_count
            call_count += 1
            return x.upper()

        counter("a")
        counter("b")
        assert call_count == 2

    def test_a_decorated_method_caches_per_instance_key(self) -> None:
        """The instance is part of the key, so two instances do not share an entry."""

        class Svc:
            def __init__(self) -> None:
                self.calls = 0

            @memoize(ttl=5)
            def get(self, x: int) -> str:
                self.calls += 1
                return f"{id(self)}-{x}"

        a, b = Svc(), Svc()
        assert a.get(1) == a.get(1)
        assert a.calls == 1
        b.get(1)
        assert b.calls == 1


class TestMemoizeTTLExpiry:
    def test_cache_expires_after_ttl(self) -> None:
        call_count = 0

        @memoize(ttl=0.1)
        def counter() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        counter()
        time.sleep(0.2)
        counter()
        assert call_count == 2


class TestMemoizeUnhashableArgs:
    def test_unhashable_args_skip_cache(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(items: list[int]) -> int:
            nonlocal call_count
            call_count += 1
            return sum(items)

        result1 = counter([1, 2, 3])
        result2 = counter([1, 2, 3])
        assert result1 == 6
        assert result2 == 6
        # Cache skipped for unhashable args — function called twice
        assert call_count == 2


class TestClearAllCaches:
    def test_clear_all_caches_resets_all_decorated_functions(self) -> None:
        count_a = 0
        count_b = 0

        @memoize(ttl=5)
        def func_a() -> int:
            nonlocal count_a
            count_a += 1
            return count_a

        @memoize(ttl=5)
        def func_b() -> int:
            nonlocal count_b
            count_b += 1
            return count_b

        func_a()
        func_b()
        clear_all_caches()
        func_a()
        func_b()
        assert count_a == 2
        assert count_b == 2

    def test_clear_all_caches_reaches_a_decorated_method(self) -> None:
        """A method's cache lives on the descriptor, not the instance, so one clear covers both."""

        class Svc:
            def __init__(self) -> None:
                self.calls = 0

            @memoize(ttl=5)
            def get(self, x: int) -> int:
                self.calls += 1
                return x

        a, b = Svc(), Svc()
        a.get(1)
        b.get(1)
        clear_all_caches()
        a.get(1)
        b.get(1)
        assert (a.calls, b.calls) == (2, 2)


class TestClearCachePerFunction:
    def test_clear_cache_resets_single_function(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        counter()
        counter.clear_cache()
        counter()
        assert call_count == 2

    def test_clear_cache_through_an_instance_clears_the_shared_cache(self) -> None:
        class Svc:
            def __init__(self) -> None:
                self.calls = 0

            @memoize(ttl=5)
            def get(self, x: int) -> int:
                self.calls += 1
                return x

        a, b = Svc(), Svc()
        a.get(1)
        b.get(1)
        a.get.clear_cache()
        a.get(1)
        b.get(1)
        assert (a.calls, b.calls) == (2, 2)


class TestPrime:
    def test_primed_value_is_served_without_calling(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter.prime(999, 7)
        assert counter(7) == 999
        assert call_count == 0

    def test_priming_one_key_does_not_serve_another(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        counter.prime(999, 7)
        assert counter(8) == 16

    def test_priming_unhashable_args_is_a_noop(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: list[int]) -> int:
            nonlocal call_count
            call_count += 1
            return sum(x)

        counter.prime(999, [1, 2])
        assert counter([1, 2]) == 3
        assert call_count == 1

    def test_priming_keyword_args(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(*, x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter.prime(999, x=7)
        assert counter(x=7) == 999
        assert call_count == 0

    def test_priming_twice_keeps_the_latest_value(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        counter.prime(111, 7)
        counter.prime(222, 7)
        assert counter(7) == 222

    def test_primed_entry_expires_on_ttl(self, clock: FakeClock) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter.prime(999, 7)
        assert counter(7) == 999
        clock.now = 6.0
        assert counter(7) == 14
        assert call_count == 1

    def test_clear_all_caches_clears_a_primed_entry(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter.prime(999, 7)
        clear_all_caches()
        assert counter(7) == 14
        assert call_count == 1

    def test_primed_entry_is_bound_to_the_instance(self) -> None:
        """The cache key includes ``self``; priming one instance must not serve another."""

        class Svc:
            @memoize(ttl=5)
            def get(self, x: int) -> str:
                return f"real-{x}"

        a, b = Svc(), Svc()
        a.get.prime("primed", 1)
        assert a.get(1) == "primed"
        assert b.get(1) == "real-1"

    def test_priming_through_the_class_keys_on_the_explicit_instance(self) -> None:
        """Class-level access exposes the same cache; the instance is then an argument."""

        class Svc:
            @memoize(ttl=5)
            def get(self, x: int) -> str:
                return f"real-{x}"

        a, b = Svc(), Svc()
        Svc.get.prime("primed", a, 1)
        assert a.get(1) == "primed"
        assert b.get(1) == "real-1"


class TestCached:
    def test_cached_returns_the_value_after_a_call(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        assert counter.cached(7) is MISS
        counter(7)
        assert counter.cached(7) == 14

    def test_cached_returns_the_value_after_priming(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        counter.prime(999, 7)
        assert counter.cached(7) == 999

    def test_cached_reports_an_expired_entry_as_a_miss(self, clock: FakeClock) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        counter(7)
        clock.now = 4.0
        assert counter.cached(7) == 14
        clock.now = 6.0
        assert counter.cached(7) is MISS

    def test_cached_reports_a_miss_for_unhashable_args(self) -> None:
        @memoize(ttl=5)
        def counter(x: list[int]) -> int:
            return sum(x)

        counter([1, 2])
        assert counter.cached([1, 2]) is MISS

    def test_cached_does_not_extend_an_entrys_lifetime(self, clock: FakeClock) -> None:
        """The invariant read-through depends on: a lookup must not refresh the timestamp.

        Without this, every batch read would push its rows' expiry forward and a
        frequently-read row would never expire — sliding expiry, which nothing asked for.
        """
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        counter(7)
        assert call_count == 1

        # Consult it repeatedly while it is fresh.
        for moment in (1.0, 2.0, 3.0, 4.0):
            clock.now = moment
            assert counter.cached(7) == 14

        # It must still expire 5s after the FETCH, not 5s after the last lookup.
        clock.now = 6.0
        assert counter.cached(7) is MISS
        assert counter(7) == 14
        assert call_count == 2

    def test_cached_through_an_instance_uses_that_instances_entry(self) -> None:
        class Svc:
            @memoize(ttl=5)
            def get(self, x: int) -> str:
                return f"real-{x}"

        a, b = Svc(), Svc()
        a.get(1)
        assert a.get.cached(1) == "real-1"
        assert b.get.cached(1) is MISS


class TestMiss:
    def test_miss_is_a_singleton(self) -> None:
        assert Miss() is Miss()
        assert Miss() is MISS

    def test_miss_reprs_as_its_name(self) -> None:
        """So an assertion failure reads ``== MISS`` rather than an object address."""
        assert repr(MISS) == "MISS"

    def test_a_cached_none_is_distinguishable_from_a_miss(self) -> None:
        """Why the sentinel exists: ``None`` is a legitimate cached value."""
        call_count = 0

        @memoize(ttl=5)
        def maybe(x: int) -> int | None:
            nonlocal call_count
            call_count += 1
            return None

        assert maybe.cached(7) is MISS
        assert maybe(7) is None
        assert maybe.cached(7) is None
        assert maybe.cached(7) is not MISS
        maybe(7)
        assert call_count == 1

    def test_a_cached_falsy_value_is_distinguishable_from_a_miss(self) -> None:
        @memoize(ttl=5)
        def zero(x: int) -> int:
            return 0

        zero(7)
        hit = zero.cached(7)
        assert hit is not MISS
        assert hit == 0


class TestDecoratedShapes:
    """Every parameter shape the one production consumer decorates.

    It decorates six of its own functions this way — two zero-argument, three
    keyword-only — so a break here costs it more than this feature saves it.
    """

    def test_zero_argument_function(self) -> None:
        calls = 0

        @memoize(ttl=5)
        def paths() -> dict[int, str]:
            nonlocal calls
            calls += 1
            return {1: "a"}

        assert paths() == {1: "a"}
        assert paths() == {1: "a"}
        assert calls == 1
        assert paths.cached() == {1: "a"}
        paths.prime({2: "b"})
        assert paths() == {2: "b"}
        paths.clear_cache()
        assert paths.cached() is MISS

    def test_keyword_only_function(self) -> None:
        calls = 0

        @memoize(ttl=5)
        def mosaic(*, count: int = 8) -> list[int]:
            nonlocal calls
            calls += 1
            return list(range(count))

        assert mosaic(count=3) == [0, 1, 2]
        assert mosaic(count=3) == [0, 1, 2]
        assert calls == 1
        assert mosaic.cached(count=3) == [0, 1, 2]
        assert mosaic.cached(count=4) is MISS
        mosaic.prime([9], count=4)
        assert mosaic(count=4) == [9]

    def test_positional_and_keyword_only_function(self) -> None:
        @memoize(ttl=5)
        def tree(parent: int, *, depth: int = 3) -> list[str]:
            return [str(parent)] * depth

        assert tree(1, depth=2) == ["1", "1"]
        assert tree.cached(1, depth=2) == ["1", "1"]
        assert tree.cached(1, depth=3) is MISS
        tree.prime(["x"], 1, depth=3)
        assert tree(1, depth=3) == ["x"]

    def test_default_argument_keys_separately_from_an_explicit_one(self) -> None:
        """A default filled in by Python is not part of ``args``, so it keys differently.

        Pre-existing behaviour, unchanged by the rewrite — recorded so it is not mistaken
        for a regression.
        """
        calls = 0

        @memoize(ttl=5)
        def f(x: int = 1) -> int:
            nonlocal calls
            calls += 1
            return x

        f()
        f(1)
        assert calls == 2

    def test_method_shape(self) -> None:
        class Svc:
            def __init__(self) -> None:
                self.calls = 0

            @memoize(ttl=5)
            def get(self, x: int) -> str:
                self.calls += 1
                return f"real-{x}"

        svc = Svc()
        assert svc.get(1) == "real-1"
        assert svc.get(1) == "real-1"
        assert svc.calls == 1
        assert svc.get.cached(1) == "real-1"
        svc.get.prime("primed", 2)
        assert svc.get(2) == "primed"
        assert svc.calls == 1


class TestIntrospection:
    """A decorated callable keeps its own identity (spec 061 NFR-003).

    ``functools.wraps`` does not apply to a class instance, so these attributes have to be
    carried deliberately. Sixteen public service methods are memoized and the constitution
    requires each to carry a Google-style docstring; without this, ``help()`` and every IDE
    would show the cache class's docstring instead.
    """

    def test_a_decorated_function_reports_its_own_identity(self) -> None:
        @memoize(ttl=5)
        def paths_from_main(x: int) -> int:
            """Return the thing."""
            return x

        assert paths_from_main.__name__ == "paths_from_main"
        assert paths_from_main.__doc__ == "Return the thing."
        assert paths_from_main.__module__ == __name__
        assert "paths_from_main" in paths_from_main.__qualname__

    def test_a_decorated_function_reports_its_own_signature(self) -> None:
        @memoize(ttl=5)
        def tree(parent: int, *, depth: int = 3) -> list[str]:
            return []

        params = inspect.signature(tree).parameters
        assert list(params) == ["parent", "depth"]
        assert params["depth"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_a_decorated_service_method_reports_its_own_identity(self) -> None:
        """The real thing: a memoized method on the public facade."""
        accessor = TaxomeshService.get_category
        assert accessor.__name__ == "get_category"
        assert accessor.__doc__ is not None
        assert accessor.__doc__.startswith("Retrieve a category by its identifier.")
        assert "category_id" in inspect.signature(accessor).parameters

    def test_wrapped_points_at_the_undecorated_callable(self) -> None:
        def original(x: int) -> int:
            return x

        decorated = memoize(ttl=5)(original)
        assert decorated.__wrapped__ is original


class TestTypeSurface:
    def test_memoize_returns_a_memoized_function(self) -> None:
        @memoize(ttl=5)
        def f(x: int) -> int:
            return x

        assert isinstance(f, MemoizedFunction)

    def test_the_module_level_prime_helper_is_gone(self) -> None:
        """Priming is a method now.

        The module-level ``prime(func, value, ...)`` helper existed only on this branch and
        was never released. It reached the cache through ``getattr`` plus a ``cast``, which
        defeated the argument checking it existed to provide, and a module-level function
        with side effects is what NFR-005 forbids. Priming a non-memoized callable is now a
        static error rather than a silent no-op.
        """
        module: ModuleType = memoize_module
        assert not hasattr(module, "prime")
        assert not hasattr(module, "_PRIME_ATTR")

    def test_a_memoized_callable_exposes_exactly_the_documented_operations(self) -> None:
        @memoize(ttl=5)
        def f(x: int) -> int:
            return x

        for name in ("prime", "cached", "clear_cache"):
            assert callable(getattr(f, name)), name

        bound: Any = TestTypeSurface._Svc().get
        for name in ("prime", "cached", "clear_cache"):
            assert callable(getattr(bound, name)), name

    class _Svc:
        @memoize(ttl=5)
        def get(self, x: int) -> int:
            return x
