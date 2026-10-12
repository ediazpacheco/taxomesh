"""Tests for the memoize cache.

``memoize`` decorates a method of an object that carries a ``ReadCache`` as ``_cache``: a
service, or one of its collections. The entries live in that cache, keyed by the member and the
arguments, so every object sharing one cache shares its entries, a ``clear()`` reaches all of
them, and they go when the last object holding the cache goes. The lifetime is the cache's, read
when a call is made.

Two properties here are load-bearing elsewhere and are tested directly rather than inferred:

* **``cached`` never writes.** Read-through consults the cache on every batch read; if a
  lookup refreshed the timestamp, a hot row would never expire and the lifetime would
  silently become sliding expiry.
* **A lifetime of zero stores nothing.** A service built with ``cache_ttl=0`` reads storage on
  every call, and holds no entry that could grow with the keys it is asked about.
"""

import gc
import inspect
import itertools
import pydoc
import sys
import threading
import weakref
from collections import Counter
from collections.abc import Iterator
from types import MethodType, ModuleType
from typing import Final

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.utils import memoize as memoize_module
from taxomesh.utils.memoize import MISS, MemoizedFunction, Miss, ReadCache, memoize


class FakeClock:
    """Stands in for the ``time`` module inside ``memoize``.

    The production code must read ``time.monotonic()`` through the module global at call
    time — ``from time import monotonic`` or a clock captured in ``__init__`` would make
    this substitution silently ineffective, and would also break the
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


class TickingClock:
    """Stands in for the ``time`` module, a second later at every reading, so entries expire as threads store."""

    def __init__(self) -> None:
        self._ticks = itertools.count()

    def monotonic(self) -> float:
        return float(next(self._ticks))


# Threads storing at once in the thread test, and how many entries each stores.
THREADS: Final[int] = 4
STORES_PER_THREAD: Final[int] = 2_000

# The lifetime the thread test's cache holds an entry for, in ticks of its clock.
TICKS_HELD: Final[int] = 50

# The longest a thread is waited for before the test gives up on it.
JOIN_TIMEOUT: Final[float] = 30.0


@pytest.fixture
def fast_switching() -> Iterator[None]:
    """Switch threads as often as the interpreter allows, and restore the interval afterwards."""
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(interval)


class Value:
    """A result that can be referenced weakly, so a test can see when nothing holds it."""

    def __init__(self, key: int) -> None:
        self.key = key


class Owner:
    """An owner of memoized reads, as a service and each of its collections are.

    Every member counts its own calls, so a test can tell a cached answer from a computed one.
    """

    def __init__(self, cache: ReadCache | None = None) -> None:
        self._cache = cache if cache is not None else ReadCache(5)
        self.calls: Counter[str] = Counter()

    @memoize
    def double(self, x: int) -> int:
        """Return twice ``x``."""
        self.calls["double"] += 1
        return x * 2

    @memoize
    def triple(self, x: int) -> int:
        self.calls["triple"] += 1
        return x * 3

    @memoize
    def nothing(self, x: int) -> int | None:
        self.calls["nothing"] += 1
        return None

    @memoize
    def total(self, xs: list[int]) -> int:
        self.calls["total"] += 1
        return sum(xs)

    @memoize
    def paths(self) -> dict[int, str]:
        self.calls["paths"] += 1
        return {1: "a"}

    @memoize
    def mosaic(self, *, count: int = 8) -> list[int]:
        self.calls["mosaic"] += 1
        return list(range(count))

    @memoize
    def tree(self, parent: int, *, depth: int = 3) -> list[str]:
        self.calls["tree"] += 1
        return [str(parent)] * depth

    @memoize
    def defaulted(self, x: int = 1) -> int:
        self.calls["defaulted"] += 1
        return x

    @memoize
    def value(self, key: int) -> Value:
        return Value(key)


class TestHit:
    def test_same_arguments_are_answered_from_the_cache(self) -> None:
        owner = Owner()
        owner.double(1)
        owner.double(1)
        assert owner.calls["double"] == 1

    def test_other_arguments_are_computed(self) -> None:
        owner = Owner()
        owner.double(1)
        owner.double(2)
        assert owner.calls["double"] == 2

    def test_two_members_keep_separate_entries(self) -> None:
        owner = Owner()
        assert owner.double(3) == 6
        assert owner.triple(3) == 9

    def test_owners_with_their_own_caches_share_nothing(self) -> None:
        first, second = Owner(), Owner()
        first.double(1)
        second.double(1)
        assert (first.calls["double"], second.calls["double"]) == (1, 1)

    def test_the_entries_belong_to_the_cache_not_to_the_owner(self) -> None:
        """A service hands its one cache to its collections, so they read each other's entries."""
        shared = ReadCache(5)
        first, second = Owner(shared), Owner(shared)
        first.double(1)
        assert second.double.cached(1) == 2

    def test_unhashable_arguments_are_computed_every_time(self) -> None:
        owner = Owner()
        assert owner.total([1, 2, 3]) == 6
        assert owner.total([1, 2, 3]) == 6
        assert owner.calls["total"] == 2


class TestLifetime:
    def test_an_entry_expires_after_the_lifetime(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double(1)
        clock.now = 4.0
        owner.double(1)
        clock.now = 6.0
        owner.double(1)
        assert owner.calls["double"] == 2

    def test_the_lifetime_is_the_cache_s_read_at_the_call(self, clock: FakeClock) -> None:
        brief, lasting = Owner(ReadCache(1)), Owner(ReadCache(10))
        brief.double(1)
        lasting.double(1)
        clock.now = 5.0
        brief.double(1)
        lasting.double(1)
        assert (brief.calls["double"], lasting.calls["double"]) == (2, 1)

    def test_the_cache_reports_its_lifetime(self) -> None:
        assert ReadCache(2.5).ttl == 2.5
        assert ReadCache(2.5).enabled
        assert not ReadCache(0).enabled


class TestNoLifetime:
    """A cache of lifetime zero stores nothing, so nothing it is asked about is retained."""

    def test_every_call_is_computed(self) -> None:
        owner = Owner(ReadCache(0))
        owner.double(1)
        owner.double(1)
        assert owner.calls["double"] == 2

    def test_prime_stores_nothing(self) -> None:
        owner = Owner(ReadCache(0))
        owner.double.prime(999, 7)
        assert owner.double.cached(7) is MISS
        assert owner.double(7) == 14

    def test_a_call_leaves_no_entry(self) -> None:
        cache = ReadCache(0)
        owner = Owner(cache)
        owner.double(7)
        assert owner.double.cached(7) is MISS
        assert cache.entries(Owner.double) == {}


class TestClear:
    def test_clear_reaches_every_member_of_every_owner_of_the_cache(self) -> None:
        shared = ReadCache(5)
        first, second = Owner(shared), Owner(shared)
        first.double(1)
        second.triple(1)
        shared.clear()
        first.double(1)
        second.triple(1)
        assert (first.calls["double"], second.calls["triple"]) == (2, 2)

    def test_clear_leaves_another_cache_as_it_was(self) -> None:
        cleared, kept = Owner(), Owner()
        cleared.double(1)
        kept.double(1)
        cleared._cache.clear()
        assert kept.double.cached(1) == 2

    def test_clear_cache_clears_one_member_only(self) -> None:
        owner = Owner()
        owner.double(1)
        owner.triple(1)
        owner.double.clear_cache()
        assert owner.double.cached(1) is MISS
        assert owner.triple.cached(1) == 3

    def test_clear_cache_leaves_the_member_s_entries_in_another_cache(self) -> None:
        cleared, kept = Owner(), Owner()
        cleared.double(1)
        kept.double(1)
        cleared.double.clear_cache()
        assert kept.double.cached(1) == 2


class TestPrime:
    def test_a_primed_value_is_served_without_calling(self) -> None:
        owner = Owner()
        owner.double.prime(999, 7)
        assert owner.double(7) == 999
        assert owner.calls["double"] == 0

    def test_priming_one_key_does_not_serve_another(self) -> None:
        owner = Owner()
        owner.double.prime(999, 7)
        assert owner.double(8) == 16

    def test_priming_unhashable_arguments_stores_nothing(self) -> None:
        owner = Owner()
        owner.total.prime(999, [1, 2])
        assert owner.total([1, 2]) == 3

    def test_priming_keyword_arguments(self) -> None:
        owner = Owner()
        owner.mosaic.prime([9], count=4)
        assert owner.mosaic(count=4) == [9]
        assert owner.calls["mosaic"] == 0

    def test_priming_twice_keeps_the_latest_value(self) -> None:
        owner = Owner()
        owner.double.prime(111, 7)
        owner.double.prime(222, 7)
        assert owner.double(7) == 222

    def test_a_primed_entry_expires_after_the_lifetime(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double.prime(999, 7)
        assert owner.double(7) == 999
        clock.now = 6.0
        assert owner.double(7) == 14

    def test_clear_drops_a_primed_entry(self) -> None:
        owner = Owner()
        owner.double.prime(999, 7)
        owner._cache.clear()
        assert owner.double(7) == 14

    def test_a_primed_entry_serves_only_its_own_cache(self) -> None:
        primed, other = Owner(), Owner()
        primed.double.prime(999, 1)
        assert other.double(1) == 2


class TestCached:
    def test_cached_answers_after_a_call(self) -> None:
        owner = Owner()
        assert owner.double.cached(7) is MISS
        owner.double(7)
        assert owner.double.cached(7) == 14

    def test_cached_answers_after_priming(self) -> None:
        owner = Owner()
        owner.double.prime(999, 7)
        assert owner.double.cached(7) == 999

    def test_cached_reports_an_expired_entry_as_a_miss(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double(7)
        clock.now = 4.0
        assert owner.double.cached(7) == 14
        clock.now = 6.0
        assert owner.double.cached(7) is MISS

    def test_cached_reports_a_miss_for_unhashable_arguments(self) -> None:
        owner = Owner()
        owner.total([1, 2])
        assert owner.total.cached([1, 2]) is MISS

    def test_cached_does_not_extend_an_entry_s_lifetime(self, clock: FakeClock) -> None:
        """The invariant read-through depends on: a lookup must not refresh the timestamp.

        Otherwise every batch read would push its rows' expiry forward, and a frequently-read
        row would never expire.
        """
        owner = Owner()
        owner.double(7)
        for moment in (1.0, 2.0, 3.0, 4.0):
            clock.now = moment
            assert owner.double.cached(7) == 14

        clock.now = 6.0
        assert owner.double.cached(7) is MISS
        assert owner.double(7) == 14
        assert owner.calls["double"] == 2


def _held(owner: Owner) -> list[int]:
    """Return the values ``double`` holds in ``owner``'s cache, in the order they were stored."""
    return [value for _, value in owner._cache.entries(Owner.double).values()]


class TestExpiredEntriesAreDropped:
    """A store drops its member's expired entries, so a member holds one lifetime of keys at most.

    Without it an entry is served for its lifetime but held until the next write, and a
    long-lived service asked about ever new keys would hold every key it was ever asked about.
    """

    def test_a_store_drops_the_member_s_expired_entries(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double(1)
        owner.double(2)
        clock.now = 3.0
        owner.double(3)

        clock.now = 6.0
        owner.double(4)

        assert _held(owner) == [6, 8]

    def test_a_key_stored_again_moves_to_the_end(self, clock: FakeClock) -> None:
        """Entries stay in the order of their stamps, so the expired ones are always at the front."""
        owner = Owner()
        owner.double(1)
        clock.now = 3.0
        owner.double(2)
        clock.now = 5.5
        owner.double(1)

        clock.now = 8.5
        owner.double(3)

        assert _held(owner) == [2, 6]

    def test_priming_drops_the_member_s_expired_entries(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double(1)

        clock.now = 6.0
        owner.double.prime(20, 10)

        assert _held(owner) == [20]

    def test_cached_drops_nothing(self, clock: FakeClock) -> None:
        owner = Owner()
        owner.double(1)

        clock.now = 6.0

        assert owner.double.cached(1) is MISS
        assert _held(owner) == [2]


@pytest.mark.usefixtures("fast_switching")
class TestThreads:
    def test_threads_storing_into_one_member_raise_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A store walks its member's entries while other threads store; none of them may fail.

        A service may be shared across threads, so its cache is too. Every reading of the clock
        moves it on, so each store finds expired entries to drop while the others store.
        """
        monkeypatch.setattr(memoize_module, "time", TickingClock())
        owner = Owner(ReadCache(TICKS_HELD))
        failures: list[Exception] = []
        start = threading.Barrier(THREADS)

        def store(k: int) -> None:
            start.wait()
            for n in range(STORES_PER_THREAD):
                try:
                    owner.double(k * STORES_PER_THREAD + n)
                except Exception as exc:
                    failures.append(exc)

        threads = [threading.Thread(target=store, args=(k,), daemon=True) for k in range(THREADS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(JOIN_TIMEOUT)

        assert failures == []
        assert len(_held(owner)) <= TICKS_HELD

    def test_a_key_whose_hash_reads_through_the_cache_does_not_wait_forever(self) -> None:
        """A store hashes its key while it holds the cache's lock, and a hash may run any code.

        Here the hash makes a read no entry answers, which stores in its turn, on the same thread.
        """
        owner = Owner()
        fresh = itertools.count()
        done = threading.Event()

        class Reentrant(int):
            def __hash__(self) -> int:
                owner.triple(next(fresh))
                return int.__hash__(self)

        def read() -> None:
            owner.double(Reentrant(2))
            done.set()

        threading.Thread(target=read, daemon=True).start()

        assert done.wait(JOIN_TIMEOUT), "the read still waits for the cache's lock"


class TestMiss:
    def test_miss_is_a_singleton(self) -> None:
        assert Miss() is Miss()
        assert Miss() is MISS

    def test_miss_reprs_as_its_name(self) -> None:
        """So an assertion failure reads ``== MISS`` rather than an object address."""
        assert repr(MISS) == "MISS"

    def test_a_cached_none_is_distinguishable_from_a_miss(self) -> None:
        """Why the sentinel exists: ``None`` is a legitimate cached value."""
        owner = Owner()
        assert owner.nothing.cached(7) is MISS
        assert owner.nothing(7) is None
        assert owner.nothing.cached(7) is None
        owner.nothing(7)
        assert owner.calls["nothing"] == 1

    def test_a_cached_falsy_value_is_distinguishable_from_a_miss(self) -> None:
        owner = Owner()
        owner.double(0)
        hit = owner.double.cached(0)
        assert hit is not MISS
        assert hit == 0


class TestDecoratedShapes:
    """Every parameter shape a memoized member takes."""

    def test_no_argument(self) -> None:
        owner = Owner()
        assert owner.paths() == {1: "a"}
        assert owner.paths() == {1: "a"}
        assert owner.calls["paths"] == 1
        assert owner.paths.cached() == {1: "a"}
        owner.paths.prime({2: "b"})
        assert owner.paths() == {2: "b"}
        owner.paths.clear_cache()
        assert owner.paths.cached() is MISS

    def test_keyword_only(self) -> None:
        owner = Owner()
        assert owner.mosaic(count=3) == [0, 1, 2]
        assert owner.mosaic(count=3) == [0, 1, 2]
        assert owner.calls["mosaic"] == 1
        assert owner.mosaic.cached(count=4) is MISS

    def test_positional_and_keyword_only(self) -> None:
        owner = Owner()
        assert owner.tree(1, depth=2) == ["1", "1"]
        assert owner.tree.cached(1, depth=2) == ["1", "1"]
        assert owner.tree.cached(1, depth=3) is MISS
        owner.tree.prime(["x"], 1, depth=3)
        assert owner.tree(1, depth=3) == ["x"]

    def test_a_default_keys_apart_from_the_same_value_written_out(self) -> None:
        """A default Python fills in is not among the arguments, so it keys differently."""
        owner = Owner()
        owner.defaulted()
        owner.defaulted(1)
        assert owner.calls["defaulted"] == 2

    def test_the_member_reached_through_the_class_takes_the_owner_first(self) -> None:
        owner = Owner()
        assert Owner.double(owner, 3) == 6
        assert owner.double.cached(3) == 6


class TestOwnership:
    """The cache is the owner's: nothing outside it holds an entry."""

    def test_the_module_keeps_no_cache_of_its_own(self) -> None:
        module: ModuleType = memoize_module
        assert not hasattr(module, "clear_all_caches")
        assert not hasattr(module, "prime")

    def test_an_entry_is_collected_with_its_owner(self) -> None:
        owner = Owner()
        held = weakref.ref(owner.value(1))
        assert held() is not None

        del owner
        gc.collect()

        assert held() is None


class TestIntrospection:
    """A decorated member keeps its own identity.

    ``functools.wraps`` does not apply to a class instance, so these attributes have to be
    carried deliberately; without them ``help()`` and every IDE would show the cache class's
    docstring instead of the member's.
    """

    def test_the_member_reports_its_own_identity(self) -> None:
        member = Owner.double
        assert member.__name__ == "double"
        assert member.__qualname__ == "Owner.double"
        assert member.__doc__ == "Return twice ``x``."
        assert member.__module__ == __name__

    def test_the_member_reports_its_own_signature(self) -> None:
        parameters = inspect.signature(Owner.tree).parameters
        assert list(parameters) == ["self", "parent", "depth"]
        assert parameters["depth"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_a_memoized_service_method_reports_its_own_identity(self) -> None:
        """Introspection seeing through the cache object is what keeps the public ledger from
        degrading to ``(*args, **kwargs)``, whether the member it wraps is public or not."""
        accessor = TaxomeshService._load_graph_rows
        assert accessor.__name__ == "_load_graph_rows"
        assert accessor.__doc__ is not None
        assert accessor.__doc__.startswith("Read the flat rows a graph is assembled from")
        parameters = inspect.signature(accessor).parameters
        assert "enabled" in parameters
        assert "include_items" in parameters

    def test_wrapped_is_the_undecorated_function(self) -> None:
        def original(self: Owner, x: int) -> int:
            return x

        assert memoize(original).__wrapped__ is original


class _Catalogue:
    """An owner of one memoized method, so the bound view is asserted apart from the library's."""

    def __init__(self) -> None:
        self._cache = ReadCache(5)

    @memoize
    def lookup(self, key: int, /, *, fresh: bool = False) -> str:
        """Return the entry stored under this key."""
        return f"entry-{key}"


class TestIntrospectionThroughAnInstance:
    """A memoized method reached through an instance presents the method it wraps.

    ``help()``, an IDE and ``inspect.signature`` are handed the bound view, not the class member,
    so the view carries the member's identity and signature rather than the cache class's.
    """

    def test_it_carries_the_members_identity(self) -> None:
        bound = _Catalogue().lookup
        assert bound.__name__ == "lookup"
        assert bound.__qualname__ == "_Catalogue.lookup"
        assert bound.__doc__ == "Return the entry stored under this key."

    def test_wrapped_is_the_bound_function(self) -> None:
        catalogue = _Catalogue()
        wrapped = catalogue.lookup.__wrapped__
        assert isinstance(wrapped, MethodType)
        assert wrapped.__func__ is _Catalogue.lookup.__wrapped__
        assert wrapped.__self__ is catalogue

    def test_its_signature_is_the_members_without_self(self) -> None:
        member = inspect.signature(_Catalogue.lookup)
        without_self = member.replace(parameters=list(member.parameters.values())[1:])
        assert inspect.signature(_Catalogue().lookup) == without_self
        assert str(without_self) == "(key: int, /, *, fresh: bool = False) -> str"

    def test_help_shows_the_members_docstring(self) -> None:
        rendered = pydoc.plain(pydoc.render_doc(_Catalogue().lookup))
        assert "Return the entry stored under this key." in rendered
        assert "seen through an instance" not in rendered
        assert "object at 0x" not in rendered

    def test_its_repr_names_the_member_and_the_instance(self) -> None:
        catalogue = _Catalogue()
        assert repr(catalogue.lookup) == f"<memoized bound method _Catalogue.lookup of {catalogue!r}>"


class TestTypeSurface:
    def test_memoize_returns_a_memoized_function(self) -> None:
        assert isinstance(Owner.__dict__["double"], MemoizedFunction)

    def test_a_bound_member_exposes_the_documented_operations(self) -> None:
        bound = Owner().double
        assert callable(bound.prime)
        assert callable(bound.cached)
        assert callable(bound.clear_cache)
