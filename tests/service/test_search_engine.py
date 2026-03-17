"""Unit tests for SearchCandidate and SearchEngine._score_prenorm (039-search-perf).

Written strictly before implementation (TDD).
"""

from taxomesh.application.search import SearchCandidate, SearchEngine
from taxomesh.domain.models import Item

# ---------------------------------------------------------------------------
# T006: SearchCandidate stores pre-normalized fields
# ---------------------------------------------------------------------------


def test_search_candidate_stores_prenormalized_fields() -> None:
    """SearchCandidate.norm_name/slug/ext must equal SearchEngine.normalize() of raw inputs."""
    item = Item(name="Ñoño Café", slug="nono-cafe", external_id="SKU-Ñ001")
    sc: SearchCandidate[Item] = SearchCandidate(
        obj=item,
        norm_name=SearchEngine.normalize(item.name),
        norm_slug=SearchEngine.normalize(item.slug),
        norm_ext=SearchEngine.normalize(item.external_id),
    )
    assert sc.norm_name == SearchEngine.normalize("Ñoño Café")
    assert sc.norm_slug == SearchEngine.normalize("nono-cafe")
    assert sc.norm_ext == SearchEngine.normalize("SKU-Ñ001")
    assert sc.obj is item


def test_search_candidate_empty_ext_stays_empty() -> None:
    """When norm_ext is explicitly set to '' it must remain empty."""
    item = Item(name="Widget", slug="widget")
    sc: SearchCandidate[Item] = SearchCandidate(
        obj=item,
        norm_name=SearchEngine.normalize(item.name),
        norm_slug=SearchEngine.normalize(item.slug),
        norm_ext="",
    )
    assert sc.norm_ext == ""


# ---------------------------------------------------------------------------
# T007: _score_prenorm returns same score as score_candidate
# ---------------------------------------------------------------------------


def _make_engine() -> SearchEngine:
    return SearchEngine()


def test_score_prenorm_exact_match() -> None:
    """_score_prenorm must return the same score as score_candidate for an exact match."""
    engine = _make_engine()
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = SearchEngine.normalize("laptop")
    norm_name = SearchEngine.normalize(raw_name)
    norm_slug = SearchEngine.normalize(raw_slug)
    norm_ext = SearchEngine.normalize(raw_ext) if raw_ext else ""

    expected = engine.score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = engine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_prefix_match() -> None:
    """_score_prenorm must match score_candidate for a prefix match."""
    engine = _make_engine()
    raw_name, raw_slug, raw_ext = "Laptop Stand", "laptop-stand", ""
    norm_q = SearchEngine.normalize("lap")
    norm_name = SearchEngine.normalize(raw_name)
    norm_slug = SearchEngine.normalize(raw_slug)
    norm_ext = ""

    expected = engine.score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = engine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_substring_match() -> None:
    """_score_prenorm must match score_candidate for a substring match."""
    engine = _make_engine()
    raw_name, raw_slug, raw_ext = "Laptop Pro", "laptop-pro", ""
    norm_q = SearchEngine.normalize("ptop")
    norm_name = SearchEngine.normalize(raw_name)
    norm_slug = SearchEngine.normalize(raw_slug)
    norm_ext = ""

    expected = engine.score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = engine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_fuzzy_match() -> None:
    """_score_prenorm must return a non-None score for a typo that score_candidate handles."""
    engine = _make_engine()
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = SearchEngine.normalize("labtop")
    norm_name = SearchEngine.normalize(raw_name)
    norm_slug = SearchEngine.normalize(raw_slug)
    norm_ext = ""

    expected = engine.score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=True)
    actual = engine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=True)
    assert actual == expected
    assert actual is not None


def test_score_prenorm_no_match_returns_none() -> None:
    """_score_prenorm returns None when there is no match, same as score_candidate."""
    engine = _make_engine()
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = SearchEngine.normalize("zzzzzzz")
    norm_name = SearchEngine.normalize(raw_name)
    norm_slug = SearchEngine.normalize(raw_slug)
    norm_ext = ""

    expected = engine.score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = engine._score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual is None
    assert actual == expected
