"""Unit tests for SearchCandidate and score_prenorm."""

from taxomesh.application.search import SearchCandidate, normalize, score_candidate, score_prenorm
from taxomesh.domain.models import Item

# ---------------------------------------------------------------------------
# SearchCandidate stores pre-normalized fields
# ---------------------------------------------------------------------------


def test_search_candidate_stores_prenormalized_fields() -> None:
    """SearchCandidate.norm_name/slug/ext must equal normalize() of raw inputs."""
    item = Item(name="Ñoño Café", slug="nono-cafe", external_id="SKU-Ñ001")
    sc: SearchCandidate[Item] = SearchCandidate(
        obj=item,
        norm_name=normalize(item.name),
        norm_slug=normalize(item.slug),
        norm_ext=normalize(item.external_id or ""),
    )
    assert sc.norm_name == normalize("Ñoño Café")
    assert sc.norm_slug == normalize("nono-cafe")
    assert sc.norm_ext == normalize("SKU-Ñ001")
    assert sc.obj is item


def test_search_candidate_empty_ext_stays_empty() -> None:
    """When norm_ext is explicitly set to '' it must remain empty."""
    item = Item(name="Widget", slug="widget")
    sc: SearchCandidate[Item] = SearchCandidate(
        obj=item,
        norm_name=normalize(item.name),
        norm_slug=normalize(item.slug),
        norm_ext="",
    )
    assert sc.norm_ext == ""


# ---------------------------------------------------------------------------
# score_prenorm returns same score as score_candidate
# ---------------------------------------------------------------------------


def test_score_prenorm_exact_match() -> None:
    """score_prenorm must return the same score as score_candidate for an exact match."""
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = normalize("laptop")
    norm_name = normalize(raw_name)
    norm_slug = normalize(raw_slug)
    norm_ext = normalize(raw_ext) if raw_ext else ""

    expected = score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_prefix_match() -> None:
    """score_prenorm must match score_candidate for a prefix match."""
    raw_name, raw_slug, raw_ext = "Laptop Stand", "laptop-stand", ""
    norm_q = normalize("lap")
    norm_name = normalize(raw_name)
    norm_slug = normalize(raw_slug)
    norm_ext = ""

    expected = score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_substring_match() -> None:
    """score_prenorm must match score_candidate for a substring match."""
    raw_name, raw_slug, raw_ext = "Laptop Pro", "laptop-pro", ""
    norm_q = normalize("ptop")
    norm_name = normalize(raw_name)
    norm_slug = normalize(raw_slug)
    norm_ext = ""

    expected = score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual == expected


def test_score_prenorm_fuzzy_match() -> None:
    """score_prenorm must return a non-None score for a typo that score_candidate handles."""
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = normalize("labtop")
    norm_name = normalize(raw_name)
    norm_slug = normalize(raw_slug)
    norm_ext = ""

    expected = score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=True)
    actual = score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=True)
    assert actual == expected
    assert actual is not None


def test_score_prenorm_no_match_returns_none() -> None:
    """score_prenorm returns None when there is no match, same as score_candidate."""
    raw_name, raw_slug, raw_ext = "Laptop", "laptop", ""
    norm_q = normalize("zzzzzzz")
    norm_name = normalize(raw_name)
    norm_slug = normalize(raw_slug)
    norm_ext = ""

    expected = score_candidate(norm_q, raw_name, raw_slug, raw_ext, fuzzy=False)
    actual = score_prenorm(norm_q, norm_name, norm_slug, norm_ext, fuzzy=False)
    assert actual is None
    assert actual == expected
