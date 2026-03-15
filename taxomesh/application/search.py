"""Fuzzy search engine for taxomesh items and categories.

This module provides SearchEngine — a stateless scoring utility that ranks
candidates against a text query using exact, prefix, substring, and
rapidfuzz-based fuzzy signals.
"""

import re
import unicodedata
from typing import Final

from rapidfuzz import fuzz

from taxomesh.domain.constants import DEFAULT_ITEM_EXTERNAL_ID

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

# Characters to treat as word separators during normalisation
_SEP_RE: Final[re.Pattern[str]] = re.compile(r"['\'\-._\\]")
_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


class SearchEngine:
    """Stateless scorer that ranks a single candidate against a query string.

    All public methods are safe to call from multiple threads because no
    instance state is mutated after construction.
    """

    @staticmethod
    def normalize(text: str) -> str:
        """Normalise *text* for comparison.

        Steps applied in order:
        1. Unicode NFD decomposition followed by removal of combining marks
           (Unicode category ``Mn``) — strips accents and diacritics.
        2. Replace separator characters (``' ' - . _ \\``) with a space.
        3. Lower-case.
        4. Collapse consecutive whitespace and strip leading/trailing spaces.

        Args:
            text: Raw input string.

        Returns:
            Normalised string suitable for comparison.
        """
        # Strip diacritics via NFD decomposition
        nfd = unicodedata.normalize("NFD", text)
        stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
        # Separator → space, then lower-case, then collapse whitespace
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

        The returned value is a float ≥ 0 when the candidate is considered a
        match, or ``None`` when it should be excluded from results.

        Scoring logic:
        - Compute deterministic *boost* from exact / prefix / word-prefix /
          substring signals on the normalised name, slug, and external_id.
        - When *fuzzy* is ``True``, compute rapidfuzz ratios against name and
          slug and add a fuzzy additive (max_fuzzy − FUZZY_THRESHOLD).
        - A candidate passes if ``boost > 0`` **or** ``max_fuzzy ≥
          FUZZY_THRESHOLD``.

        Args:
            query: Pre-normalised query string (caller must normalise).
            name: Raw item/category name.
            slug: Raw item/category slug.
            external_id: Raw external identifier; empty string disables ext
                matching.
            fuzzy: When ``True`` rapidfuzz ratios are included.

        Returns:
            A numeric score (higher is better) or ``None`` if no match.
        """
        norm_name = self.normalize(name)
        norm_slug = self.normalize(slug)
        norm_ext = self.normalize(external_id) if external_id != DEFAULT_ITEM_EXTERNAL_ID else ""

        boost = self._compute_boost(query, norm_name, norm_slug, norm_ext)

        fuzzy_additive = 0.0
        max_fuzzy = 0.0
        if fuzzy:
            max_fuzzy, fuzzy_additive = self._compute_fuzzy(query, norm_name, norm_slug)

        if boost > 0:
            return float(boost) + fuzzy_additive
        if max_fuzzy >= FUZZY_THRESHOLD:
            return fuzzy_additive
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
        # Additive contribution: how far above zero the best fuzzy score is
        fuzzy_additive = max_fuzzy - FUZZY_THRESHOLD if max_fuzzy >= FUZZY_THRESHOLD else 0.0
        return max_fuzzy, fuzzy_additive
