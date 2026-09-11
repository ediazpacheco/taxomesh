"""Tests for the memoize decorator."""

import time

from taxomesh.utils.memoize import clear_all_caches, memoize, prime


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


class TestClearCachePerFunction:
    def test_clear_cache_resets_single_function(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        counter()
        counter.clear_cache()  # type: ignore[attr-defined]
        counter()
        assert call_count == 2


class TestPrime:
    def test_primed_value_is_served_without_calling(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        prime(counter, 999, 7)
        assert counter(7) == 999
        assert call_count == 0

    def test_priming_one_key_does_not_serve_another(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        prime(counter, 999, 7)
        assert counter(8) == 16

    def test_priming_a_plain_function_is_a_noop(self) -> None:
        call_count = 0

        def plain(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        prime(plain, 999, 7)
        assert plain(7) == 14
        assert call_count == 1

    def test_priming_unhashable_args_is_a_noop(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: list[int]) -> int:
            nonlocal call_count
            call_count += 1
            return sum(x)

        prime(counter, 999, [1, 2])
        assert counter([1, 2]) == 3
        assert call_count == 1

    def test_priming_keyword_args(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(*, x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        prime(counter, 999, x=7)
        assert counter(x=7) == 999
        assert call_count == 0

    def test_priming_twice_keeps_the_latest_value(self) -> None:
        @memoize(ttl=5)
        def counter(x: int) -> int:
            return x * 2

        prime(counter, 111, 7)
        prime(counter, 222, 7)
        assert counter(7) == 222

    def test_primed_entry_expires_on_ttl(self) -> None:
        call_count = 0

        @memoize(ttl=0.1)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        prime(counter, 999, 7)
        assert counter(7) == 999
        time.sleep(0.15)
        assert counter(7) == 14
        assert call_count == 1

    def test_clear_all_caches_clears_a_primed_entry(self) -> None:
        call_count = 0

        @memoize(ttl=5)
        def counter(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        prime(counter, 999, 7)
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
        prime(Svc.get, "primed", a, 1)
        assert a.get(1) == "primed"
        assert b.get(1) == "real-1"
