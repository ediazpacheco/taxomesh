"""Tests for the memoize decorator."""

import time

from taxomesh.utils.memoize import clear_all_caches, memoize


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
