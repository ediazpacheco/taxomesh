"""The search of taxomesh items and categories.

The functions here score and rank candidates against a text query. They have no state, so threads
can call them at the same time. They use exact, prefix and substring matches, and approximate
matches from rapidfuzz. :func:`normalize` converts a text for comparison, :func:`score_candidate`
scores one candidate, and :func:`score_corpus` ranks many.

``SearchCandidate`` is an internal helper. It keeps a row with its searchable fields already
normalized, so each field is normalized once and not at each step of the scoring.
:func:`candidate_of` builds one from a row.

``SearchCorpus`` holds the built candidates of one kind of entity for the lifetime of the
service's cache, or until that service next creates, updates or deletes a row of that kind. The
service gives it to the collection that searches it.
"""

import heapq
import re
import unicodedata
from collections.abc import Callable
from typing import Final, Protocol

from rapidfuzz import fuzz

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
_SEP_RE: Final[re.Pattern[str]] = re.compile(r"['\-._\\]")
_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


class SearchCandidate[T]:
    """A row with its searchable fields, already normalized.

    Built so that each field of a candidate is normalized once, and not at each step of the
    scoring. A held corpus keeps its candidates from one search to the next.

    Args:
        obj: The row: an ``Item`` or a ``Category``.
        norm_name: ``normalize(obj.name)``, computed once.
        norm_slug: ``normalize(obj.slug)``, computed once.
        norm_ext: ``normalize(obj.external_id)``, or ``""`` when the external id is
            ``None``.

    Example::

        sc = candidate_of(item)
        score = score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext)
    """

    def __init__(self, obj: T, norm_name: str, norm_slug: str, norm_ext: str) -> None:
        """Keep the row and its normalized field values."""
        self.obj = obj
        self.norm_name = norm_name
        self.norm_slug = norm_slug
        self.norm_ext = norm_ext


class _Searchable(Protocol):
    """A row with the three fields that a search matches: an ``Item`` or a ``Category``."""

    @property
    def name(self) -> str: ...

    @property
    def slug(self) -> str: ...

    @property
    def external_id(self) -> str | None: ...


def candidate_of[R: _Searchable](row: R) -> SearchCandidate[R]:
    """Return the search candidate of a row, with its name, slug and external id normalized.

    Args:
        row: An ``Item`` or a ``Category``.

    Returns:
        The candidate. Its ``norm_ext`` is ``""`` when the row has no external id.
    """
    return SearchCandidate(
        obj=row,
        norm_name=normalize(row.name),
        norm_slug=normalize(row.slug),
        norm_ext="" if row.external_id is None else normalize(row.external_id),
    )


class SearchCorpus[T]:
    """The search candidates of one kind of entity, held for the lifetime of the service's cache.

    A create, update or delete of a row of that kind drops them sooner; a write of a link does
    not, because no candidate holds a link.

    The service owns the corpus and gives it to the collection that searches it. The collection
    reads or fills it through :meth:`held_or` on a search that no category limits, and calls
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
        """Return the corpus to search, or ``None`` when none is held or the cache serves nothing now.

        The cache serves nothing inside a transaction, so a search there reads the transaction's
        own writes from storage.
        """
        return self._held() if self._cache.enabled else None

    @property
    def size(self) -> int | None:
        """Return how many candidates are held, or ``None`` when no corpus is held."""
        held = self._held()
        return None if held is None else len(held)

    def _held(self) -> list[SearchCandidate[T]] | None:
        """Return the held corpus, or ``None`` when it was never built, was dropped, or has expired."""
        if self._candidates is None or not self._cache.is_fresh(self._built_at):
            return None
        return self._candidates

    def hold(self, candidates: list[SearchCandidate[T]]) -> list[SearchCandidate[T]]:
        """Hold these candidates for the cache's lifetime, and return them.

        Holds nothing when the cache stores nothing, so a service built with ``cache_ttl=0``
        builds the corpus from storage on every search, and so does a search inside a transaction.

        Args:
            candidates: The corpus just built from storage.

        Returns:
            The same candidates, for the search that built them.
        """
        if self._cache.enabled:
            self._candidates = candidates
            self._built_at = self._cache.now()
        return candidates

    def held_or(self, build: Callable[[], list[SearchCandidate[T]]]) -> list[SearchCandidate[T]]:
        """Return the held candidates, or build them, hold them and return them.

        Args:
            build: Reads the rows from storage and returns their candidates. It is called only
                when :attr:`candidates` is ``None``.

        Returns:
            The corpus to search.
        """
        held = self.candidates
        return self.hold(build()) if held is None else held

    def invalidate(self) -> None:
        """Drop the candidates, so the next search rebuilds them from storage."""
        self._candidates = None


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
    norm_name = normalize(name)
    norm_slug = normalize(slug)
    norm_ext = normalize(external_id)
    return score_prenorm(query, norm_name, norm_slug, norm_ext, fuzzy=fuzzy)


def score_prenorm(
    norm_q: str,
    norm_name: str,
    norm_slug: str,
    norm_ext: str,
    *,
    fuzzy: bool = True,
) -> float | None:
    """Score one candidate from field values that are already normalized.

    Each field must have passed through ``normalize()``; the caller makes sure
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
    boost = _compute_boost(norm_q, norm_name, norm_slug, norm_ext)
    best_ratio = _best_ratio(norm_q, norm_name, norm_slug) if fuzzy else 0.0
    # What the approximate match adds: how far the best ratio is above FUZZY_THRESHOLD, or 0
    fuzzy_bonus = best_ratio - FUZZY_THRESHOLD if best_ratio >= FUZZY_THRESHOLD else 0.0
    if boost > 0:
        return float(boost) + fuzzy_bonus
    if best_ratio >= FUZZY_THRESHOLD:
        return fuzzy_bonus
    return None


def score_corpus[T](
    norm_q: str,
    corpus: list[SearchCandidate[T]],
    *,
    fuzzy: bool,
    limit: int,
) -> tuple[T, ...]:
    """Score candidates whose fields are already normalized, and return the best *limit*.

    Args:
        norm_q: The normalized query.
        corpus: The normalized candidates to score.
        fuzzy: Passed to ``score_prenorm``.
        limit: The maximum number of results.

    Returns:
        The rows, sorted by descending score, then by normalized name, at most *limit* of
        them.
    """
    scored: list[tuple[float, str, T]] = []
    for sc in corpus:
        score = score_prenorm(norm_q, sc.norm_name, sc.norm_slug, sc.norm_ext, fuzzy=fuzzy)
        if score is not None:
            scored.append((score, sc.norm_name, sc.obj))
    return tuple(obj for _, _, obj in heapq.nsmallest(limit, scored, key=lambda t: (-t[0], t[1])))


def _compute_boost(query: str, norm_name: str, norm_slug: str, norm_ext: str) -> int:  # noqa: PLR0911
    """Return the highest deterministic boost that applies."""
    if query in (norm_name, norm_slug):
        return BOOST_EXACT
    if norm_name.startswith(query):
        return BOOST_PREFIX_NAME
    if norm_slug.startswith(query):
        return BOOST_PREFIX_SLUG
    if any(word.startswith(query) for word in norm_name.split()):
        return BOOST_WORD_PREFIX
    if query in norm_name:
        return BOOST_SUBSTRING_NAME
    if query in norm_slug:
        return BOOST_SUBSTRING_SLUG
    if norm_ext and query in norm_ext:
        return BOOST_SUBSTRING_EXT
    return 0


def _best_ratio(query: str, norm_name: str, norm_slug: str) -> float:
    """Return the best rapidfuzz ratio of the query against the name and the slug."""
    return max(
        fuzz.ratio(query, norm_name),
        fuzz.partial_ratio(query, norm_name),
        fuzz.token_set_ratio(query, norm_name),
        fuzz.ratio(query, norm_slug),
        fuzz.partial_ratio(query, norm_slug),
    )
