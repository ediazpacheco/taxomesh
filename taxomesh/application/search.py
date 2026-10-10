"""The search of taxomesh items and categories.

``SearchEngine`` scores and ranks candidates against a text query. It has no state, and it uses
exact, prefix and substring matches, and approximate matches from rapidfuzz.

``SearchCandidate`` is an internal helper. It keeps a row with its searchable fields already
normalized, so each field is normalized once and not at each step of the scoring.

``SearchCorpus`` holds the built candidates of one kind of entity for the lifetime of the
service's cache, or until that service next creates, updates or deletes a row of that kind. The
service gives it to the collection that searches it.
"""

import heapq
import re
import unicodedata
from collections.abc import Callable, Sequence
from typing import Final

from rapidfuzz import fuzz

from taxomesh.domain.constants import DEFAULT_ITEM_EXTERNAL_ID
from taxomesh.utils.memoize import ReadCache

# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

DEFAULT_SEARCH_LIMIT: Final[int] = 20

BOOST_EXACT: Final[int] = 1000
BOOST_PREFIX_NAME: Final[int] = 500
BOOST_PREFIX_SLUG: Final[int] = 400
BOOST_WORD_PREFIX: Final[int] = 300
BOOST_SUBSTRING_NAME: Final[int] = 200
BOOST_SUBSTRING_SLUG: Final[int] = 150
BOOST_SUBSTRING_EXT: Final[int] = 50
FUZZY_THRESHOLD: Final[int] = 70

# The characters that normalisation replaces with a space, as word separators
_SEP_RE: Final[re.Pattern[str]] = re.compile(r"['\'\-._\\]")
_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


class SearchCandidate[T]:
    """A row with its searchable fields, already normalized.

    Built so that each field of a candidate is normalized once, and not at each step of the
    scoring. A held corpus keeps its candidates from one search to the next.

    Args:
        obj: The row: an ``Item`` or a ``Category``.
        norm_name: ``SearchEngine.normalize(obj.name)``, computed once.
        norm_slug: ``SearchEngine.normalize(obj.slug)``, computed once.
        norm_ext: ``SearchEngine.normalize(obj.external_id)``, or ``""`` when the external id is
            ``None``.

    Example::

        sc = SearchCandidate(
            obj=item,
            norm_name=SearchEngine.normalize(item.name),
            norm_slug=SearchEngine.normalize(item.slug),
            norm_ext=SearchEngine.normalize(item.external_id),
        )
        score = engine._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext)
    """

    def __init__(self, obj: T, norm_name: str, norm_slug: str, norm_ext: str) -> None:
        """Keep the row and its normalized field values."""
        self.obj = obj
        self.norm_name = norm_name
        self.norm_slug = norm_slug
        self.norm_ext = norm_ext


class SearchCorpus[T]:
    """The search candidates of one kind of entity, held for the lifetime of the service's cache.

    A create, update or delete of a row of that kind drops them sooner; a write of a link does
    not, because no candidate holds a link.

    The service owns the corpus and gives it to the collection that searches it. The collection
    fills it through :meth:`hold` on an unfiltered search that finds nothing held, and calls
    :meth:`invalidate` whenever it creates, updates or deletes a row of that kind; the service
    reports :attr:`size`. Because the two hold the same object, they agree: a collection with a
    list of its own would let the service describe a corpus that the collection had dropped.
    """

    def __init__(self, cache: ReadCache) -> None:
        """Start empty: the first search that needs the corpus builds it.

        Args:
            cache: The service's cache, whose lifetime and clock the corpus uses. When the cache
                stores nothing, the corpus holds nothing either.
        """
        self._cache = cache
        self._candidates: list[SearchCandidate[T]] | None = None
        self._built_at = 0.0

    @property
    def candidates(self) -> list[SearchCandidate[T]] | None:
        """Return the held corpus, or ``None`` when it was never built, was dropped, or has expired."""
        if self._candidates is None or not self._cache.is_fresh(self._built_at):
            return None
        return self._candidates

    @property
    def size(self) -> int | None:
        """Return how many candidates are held, or ``None`` when no corpus is held."""
        held = self.candidates
        return None if held is None else len(held)

    def hold(self, candidates: list[SearchCandidate[T]]) -> list[SearchCandidate[T]]:
        """Hold these candidates for the cache's lifetime, and return them.

        Holds nothing when the cache stores nothing, so a service built with ``cache_ttl=0``
        builds the corpus from storage on every search.

        Args:
            candidates: The corpus just built from storage.

        Returns:
            The same candidates, for the search that built them.
        """
        if self._cache.enabled:
            self._candidates = candidates
            self._built_at = self._cache.now()
        return candidates

    def invalidate(self) -> None:
        """Drop the candidates, so the next search rebuilds them from storage."""
        self._candidates = None


class SearchEngine:
    """A scorer with no state, which ranks candidates against a query string.

    Threads can call every public method at the same time, because an instance has no state to
    change.
    """

    @staticmethod
    def normalize(text: str) -> str:
        """Normalise *text* for comparison.

        The steps, in order:
        1. Decompose the text to Unicode NFD, then remove the combining marks (Unicode category
           ``Mn``): this removes accents and other diacritics.
        2. Replace each separator character, ``'``, ``-``, ``.``, ``_`` and ``\\``, with a space.
        3. Put the text in lowercase.
        4. Replace each run of whitespace with one space, and remove the spaces at the start and
           at the end.

        Args:
            text: The text as given.

        Returns:
            The normalised text, ready for comparison.
        """
        # Remove the diacritics through the NFD decomposition
        nfd = unicodedata.normalize("NFD", text)
        stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
        # Separator to space, then lowercase, then one space for each run of whitespace
        separated = _SEP_RE.sub(" ", stripped)
        return _SPACE_RE.sub(" ", separated.lower()).strip()

    def score_candidate(
        self,
        query: str,
        name: str,
        slug: str,
        external_id: str,
        *,
        fuzzy: bool = True,
    ) -> float | None:
        """Score one candidate against *query*.

        The result is a float ≥ 0 when the candidate matches, or ``None`` when it does not.

        How the score is made:
        - A fixed *boost* comes from an exact, prefix, word-prefix or substring match on the
          normalised name, slug and external id.
        - When *fuzzy* is ``True``, the rapidfuzz ratios against the name and the slug add
          ``max_fuzzy − FUZZY_THRESHOLD`` to the score.
        - A candidate matches if ``boost > 0`` **or** ``max_fuzzy ≥ FUZZY_THRESHOLD``.

        Args:
            query: The query, already normalised by the caller.
            name: The name of the item or category, as stored.
            slug: The slug of the item or category, as stored.
            external_id: The external id, as stored; an empty string turns off the external-id
                match.
            fuzzy: When it is ``True``, the rapidfuzz ratios count.

        Returns:
            A score (higher is better), or ``None`` if the candidate does not match.
        """
        norm_name = self.normalize(name)
        norm_slug = self.normalize(slug)
        norm_ext = self.normalize(external_id) if external_id != DEFAULT_ITEM_EXTERNAL_ID else ""
        return self._score_prenorm(query, norm_name, norm_slug, norm_ext, fuzzy=fuzzy)

    def _score_prenorm(
        self,
        norm_q: str,
        norm_name: str,
        norm_slug: str,
        norm_ext: str,
        *,
        fuzzy: bool = True,
    ) -> float | None:
        """Score one candidate from field values that are already normalized.

        Each field must have passed through ``SearchEngine.normalize()``; the caller makes sure
        of it. For values as stored, use ``score_candidate()``.

        Args:
            norm_q: The normalized query.
            norm_name: The normalized name of the candidate.
            norm_slug: The normalized slug of the candidate.
            norm_ext: The normalized external id, or ``""`` when the external id is ``None``,
                which turns off the external-id match.
            fuzzy: When it is ``True``, the rapidfuzz ratios count.

        Returns:
            A score (higher is better), or ``None`` if the candidate does not match.
        """
        boost = self._compute_boost(norm_q, norm_name, norm_slug, norm_ext)

        fuzzy_additive = 0.0
        max_fuzzy = 0.0
        if fuzzy:
            max_fuzzy, fuzzy_additive = self._compute_fuzzy(norm_q, norm_name, norm_slug)

        if boost > 0:
            return float(boost) + fuzzy_additive
        if max_fuzzy >= FUZZY_THRESHOLD:
            return fuzzy_additive
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rank_scored[T](self, scored: list[tuple[float, str, T]], limit: int) -> tuple[T, ...]:
        """Sort the *scored* tuples by descending score, then by ascending name, and keep *limit*.

        When *limit* is smaller than the number of matches, ``heapq.nsmallest`` replaces the full
        sort: O(N log k), not O(N log N).

        Args:
            scored: The ``(score, norm_name, obj)`` tuples to rank.
            limit: The maximum number of results.

        Returns:
            The rows in rank order, at most *limit* of them.
        """
        if limit < len(scored):
            return tuple(c for _, _, c in heapq.nsmallest(limit, scored, key=lambda t: (-t[0], t[1])))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return tuple(c for _, _, c in scored)

    def _score_corpus[T](
        self,
        norm_q: str,
        corpus: list[SearchCandidate[T]],
        *,
        fuzzy: bool,
        limit: int,
    ) -> tuple[T, ...]:
        """Score candidates whose fields are already normalized, and return the best *limit*.

        Takes ``SearchCandidate`` objects whose fields are already normalized, so it skips the
        normalization that ``_score_and_rank`` does on each call. The ranking is the same:
        descending score, then ascending normalized name.

        Args:
            norm_q: The normalized query.
            corpus: The normalized candidates to score.
            fuzzy: Passed to ``_score_prenorm``.
            limit: The maximum number of results.

        Returns:
            The rows, sorted by descending score, then by normalized name, at most *limit* of
            them.
        """
        scored: list[tuple[float, str, T]] = []
        for sc in corpus:
            score = self._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, fuzzy=fuzzy)
            if score is not None:
                scored.append((score, sc.norm_name, sc.obj))
        return self._rank_scored(scored, limit)

    def _score_and_rank[T](  # noqa: PLR0913
        self,
        norm_q: str,
        candidates: Sequence[T],
        *,
        get_name: Callable[[T], str],
        get_slug: Callable[[T], str],
        get_ext: Callable[[T], str | None],
        fuzzy: bool,
        limit: int,
    ) -> tuple[T, ...]:
        """Score *candidates* against *norm_q* and return the best *limit*.

        The fields of each candidate are normalized exactly once, in a ``SearchCandidate``,
        before the scoring. When ``limit`` is smaller than the number of matching candidates,
        ``heapq.nsmallest`` replaces the full sort: O(N log k), not O(N log N).

        Args:
            norm_q: The normalised query.
            candidates: The rows to score: items or categories.
            get_name: Returns the name of a candidate.
            get_slug: Returns the slug of a candidate.
            get_ext: Returns the external id of a candidate.
            fuzzy: Passed to ``_score_prenorm``.
            limit: The maximum number of results.

        Returns:
            The rows, sorted by descending score, then by normalised name, at most *limit* of
            them.
        """

        # Normalize the fields of each candidate exactly once.
        def _norm_ext(c: T) -> str:
            ext = get_ext(c)
            return SearchEngine.normalize(ext) if ext is not None else ""

        search_candidates: list[SearchCandidate[T]] = [
            SearchCandidate(
                obj=c,
                norm_name=SearchEngine.normalize(get_name(c)),
                norm_slug=SearchEngine.normalize(get_slug(c)),
                norm_ext=_norm_ext(c),
            )
            for c in candidates
        ]
        scored: list[tuple[float, str, T]] = []
        for sc in search_candidates:
            score = self._score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, fuzzy=fuzzy)
            if score is not None:
                scored.append((score, sc.norm_name, sc.obj))
        return self._rank_scored(scored, limit)

    @staticmethod
    def _compute_boost(query: str, norm_name: str, norm_slug: str, norm_ext: str) -> int:  # noqa: PLR0911
        """Return the highest deterministic boost that applies."""
        # Exact match on name or slug
        if query in (norm_name, norm_slug):
            return BOOST_EXACT

        # Prefix of name
        if norm_name.startswith(query):
            return BOOST_PREFIX_NAME

        # Prefix of slug
        if norm_slug.startswith(query):
            return BOOST_PREFIX_SLUG

        # Prefix of any individual word in name
        name_words = norm_name.split()
        if any(w.startswith(query) for w in name_words):
            return BOOST_WORD_PREFIX

        # Substring of name
        if query in norm_name:
            return BOOST_SUBSTRING_NAME

        # Substring of slug
        if query in norm_slug:
            return BOOST_SUBSTRING_SLUG

        # Substring of external_id (only when non-empty)
        if norm_ext and query in norm_ext:
            return BOOST_SUBSTRING_EXT

        return 0

    @staticmethod
    def _compute_fuzzy(query: str, norm_name: str, norm_slug: str) -> tuple[float, float]:
        """Return (max_fuzzy_score, fuzzy_additive) for the candidate."""
        scores: list[float] = [
            fuzz.ratio(query, norm_name),
            fuzz.partial_ratio(query, norm_name),
            fuzz.token_set_ratio(query, norm_name),
            fuzz.ratio(query, norm_slug),
            fuzz.partial_ratio(query, norm_slug),
        ]
        max_fuzzy = max(scores)
        # What the approximate match adds: how far the best ratio is above FUZZY_THRESHOLD, or 0
        fuzzy_additive = max_fuzzy - FUZZY_THRESHOLD if max_fuzzy >= FUZZY_THRESHOLD else 0.0
        return max_fuzzy, fuzzy_additive
