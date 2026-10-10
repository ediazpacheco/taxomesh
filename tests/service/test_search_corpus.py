"""The search-corpus holder the service owns and injects into its collections.

The collection builds the corpus on search and invalidates it whenever it creates, updates or
deletes a row, while the service reports its size. The holder keeps the corpus for the lifetime
of the service's cache. Both must therefore hold the **same**
object: a collection keeping its own list would leave the service describing a corpus that no
longer exists. That sharing is exercised end to end by ``test_search_corpus_cache.py``; this
file pins the holder itself.
"""

import pytest

from taxomesh.application.search import SearchCandidate, SearchCorpus
from taxomesh.utils import memoize as memoize_module
from taxomesh.utils.memoize import ReadCache


def _candidate(name: str) -> SearchCandidate[str]:
    """Return a candidate whose fields are already in normalised form."""
    return SearchCandidate(obj=name, norm_name=name, norm_slug="", norm_ext="")


def test_a_new_corpus_holds_nothing() -> None:
    """Nothing is built until a search asks for it."""
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(5))

    assert corpus.candidates is None
    assert corpus.size is None


def test_size_counts_the_held_candidates() -> None:
    """``size`` reports how many candidates are held."""
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(5))
    corpus.hold([_candidate("a"), _candidate("b")])

    assert corpus.size == 2


def test_an_empty_corpus_is_built_rather_than_absent() -> None:
    """A corpus built over no rows has size 0, distinguishable from one never built."""
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(5))
    corpus.hold([])

    assert corpus.size == 0


def test_invalidate_drops_the_candidates() -> None:
    """After invalidation the next search rebuilds, and ``size`` says so."""
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(5))
    corpus.hold([_candidate("a")])

    corpus.invalidate()

    assert corpus.candidates is None
    assert corpus.size is None


def test_a_cache_that_stores_nothing_holds_no_corpus() -> None:
    """With a lifetime of zero every search builds the corpus from storage again."""
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(0))

    candidates = [_candidate("a")]

    assert corpus.hold(candidates) is candidates
    assert corpus.candidates is None
    assert corpus.size is None


def test_a_corpus_past_its_lifetime_is_no_longer_held(monkeypatch: pytest.MonkeyPatch) -> None:
    """The corpus is held for the lifetime of the cache it was given, measured from its build."""

    class Clock:
        now = 0.0

        def monotonic(self) -> float:
            return self.now

    clock = Clock()
    monkeypatch.setattr(memoize_module, "time", clock)
    corpus: SearchCorpus[str] = SearchCorpus(ReadCache(5))
    corpus.hold([_candidate("a")])

    clock.now = 4.0
    assert corpus.size == 1
    clock.now = 6.0
    assert corpus.candidates is None
