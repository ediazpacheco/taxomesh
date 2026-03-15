"""Tests for fuzzy search (033-fuzzy-search).

Written strictly before implementation (TDD).
"""

from uuid import uuid4

import pytest

from taxomesh.application.search import SearchEngine
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.exceptions import TaxomeshCategoryNotFoundError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def svc(service: TaxomeshService) -> TaxomeshService:
    """Alias so tests can use the shared service fixture."""
    return service


# ---------------------------------------------------------------------------
# T003–T006: SearchEngine.normalize()
# ---------------------------------------------------------------------------


def test_normalize_lowercases() -> None:
    assert SearchEngine.normalize("Hello World") == "hello world"


def test_normalize_strips_diacritics() -> None:
    # é → e, ñ → n
    assert SearchEngine.normalize("café niño") == "cafe nino"


def test_normalize_replaces_separators_with_space() -> None:
    # hyphens, underscores, dots, apostrophes, backslashes
    assert SearchEngine.normalize("foo-bar_baz.qux") == "foo bar baz qux"


def test_normalize_collapses_multiple_spaces() -> None:
    assert SearchEngine.normalize("  foo   bar  ") == "foo bar"


def test_normalize_empty_string() -> None:
    assert SearchEngine.normalize("") == ""


def test_normalize_apostrophe_and_backslash() -> None:
    assert SearchEngine.normalize("it's a\\test") == "it s a test"


# ---------------------------------------------------------------------------
# T007–T010: score_candidate — boost signals (non-fuzzy)
# ---------------------------------------------------------------------------


def test_score_exact_match_name() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("laptop", "Laptop", "", "", fuzzy=False)
    assert score is not None
    assert score >= 1000  # BOOST_EXACT


def test_score_exact_match_slug() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("laptop", "", "laptop", "", fuzzy=False)
    assert score is not None
    assert score >= 1000


def test_score_prefix_name() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("lap", "Laptop Stand", "", "", fuzzy=False)
    assert score is not None
    assert score >= 500  # BOOST_PREFIX_NAME


def test_score_prefix_slug() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("lap", "", "laptop-stand", "", fuzzy=False)
    assert score is not None
    assert score >= 400  # BOOST_PREFIX_SLUG


def test_score_word_prefix() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("stand", "Laptop Stand", "", "", fuzzy=False)
    assert score is not None
    assert score >= 300  # BOOST_WORD_PREFIX (prefix of word "stand")


def test_score_substring_name() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("ptop", "Laptop", "", "", fuzzy=False)
    assert score is not None
    assert score >= 200  # BOOST_SUBSTRING_NAME


def test_score_substring_slug() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("ptop", "", "laptop", "", fuzzy=False)
    assert score is not None
    assert score >= 150  # BOOST_SUBSTRING_SLUG


def test_score_external_id_match() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("sku123", "", "", "SKU123", fuzzy=False)
    assert score is not None
    assert score >= 50  # BOOST_SUBSTRING_EXT


def test_score_no_match_returns_none() -> None:
    engine = SearchEngine()
    score = engine.score_candidate("xyz", "Laptop", "laptop-pro", "sku001", fuzzy=False)
    assert score is None


def test_score_empty_external_id_skips_ext_matching() -> None:
    engine = SearchEngine()
    # query matches nothing else, ext is empty → None
    score = engine.score_candidate("xyz", "Apple", "apple", "", fuzzy=False)
    assert score is None


# ---------------------------------------------------------------------------
# T011–T013: score_candidate — fuzzy path
# ---------------------------------------------------------------------------


def test_score_fuzzy_typo_returns_value() -> None:
    """A near-match with a typo should score above threshold."""
    engine = SearchEngine()
    score = engine.score_candidate("labtop", "Laptop", "laptop", "", fuzzy=True)
    assert score is not None


def test_score_fuzzy_threshold_respected() -> None:
    """Completely unrelated strings should return None even with fuzzy=True."""
    engine = SearchEngine()
    score = engine.score_candidate("zzzzz", "Laptop", "laptop", "", fuzzy=True)
    assert score is None


def test_score_fuzzy_false_typo_no_match() -> None:
    """With fuzzy=False a typo that isn't a substring should return None."""
    engine = SearchEngine()
    score = engine.score_candidate("labtop", "Laptop", "laptop", "", fuzzy=False)
    assert score is None


# ---------------------------------------------------------------------------
# T014–T019: search_items — basic behaviour
# ---------------------------------------------------------------------------


def test_search_items_returns_list(svc: TaxomeshService) -> None:
    svc.create_item(name="Laptop Pro", slug="laptop-pro")
    results = svc.search_items("laptop")
    assert isinstance(results, list)


def test_search_items_empty_query_returns_empty(svc: TaxomeshService) -> None:
    svc.create_item(name="Laptop Pro", slug="laptop-pro")
    assert svc.search_items("   ") == []


def test_search_items_invalid_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.search_items("x", limit=0)


def test_search_items_negative_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.search_items("x", limit=-1)


def test_search_items_exact_match_found(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Laptop Pro", slug="laptop-pro")
    results = svc.search_items("laptop pro")
    ids = [i.item_id for i in results]
    assert item.item_id in ids


def test_search_items_prefix_match_found(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Laptop Stand")
    results = svc.search_items("lap")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_respects_limit(svc: TaxomeshService) -> None:
    for i in range(10):
        svc.create_item(name=f"Laptop Model {i}")
    results = svc.search_items("laptop", limit=3)
    assert len(results) <= 3


def test_search_items_enabled_only_filters_disabled(svc: TaxomeshService) -> None:
    enabled_item = svc.create_item(name="Laptop Enabled")
    disabled_item = svc.create_item(name="Laptop Disabled")
    svc.update_item(disabled_item.item_id, enabled=False)
    results = svc.search_items("laptop", enabled_only=True)
    ids = [i.item_id for i in results]
    assert enabled_item.item_id in ids
    assert disabled_item.item_id not in ids


def test_search_items_no_match_returns_empty(svc: TaxomeshService) -> None:
    svc.create_item(name="Laptop Pro")
    results = svc.search_items("zzzzzzzzz", fuzzy=False)
    assert results == []


def test_search_items_exact_match_ranked_first(svc: TaxomeshService) -> None:
    """Exact match should appear before partial/fuzzy matches."""
    svc.create_item(name="Laptop Stand")
    exact = svc.create_item(name="Laptop")
    results = svc.search_items("laptop")
    assert results[0].item_id == exact.item_id


# ---------------------------------------------------------------------------
# T020–T022: search_categories — basic behaviour
# ---------------------------------------------------------------------------


def test_search_categories_returns_list(svc: TaxomeshService) -> None:
    svc.create_category(name="Electronics")
    results = svc.search_categories("electr")
    assert isinstance(results, list)


def test_search_categories_empty_query_returns_empty(svc: TaxomeshService) -> None:
    svc.create_category(name="Electronics")
    assert svc.search_categories("   ") == []


def test_search_categories_invalid_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.search_categories("x", limit=0)


def test_search_categories_root_excluded(svc: TaxomeshService) -> None:
    """Root category must never appear in search results."""
    results = svc.search_categories(ROOT_CATEGORY_NAME)
    assert all(r.name != ROOT_CATEGORY_NAME for r in results)


def test_search_categories_exact_match_found(svc: TaxomeshService) -> None:
    cat = svc.create_category(name="Electronics")
    results = svc.search_categories("Electronics")
    assert any(r.category_id == cat.category_id for r in results)


# ---------------------------------------------------------------------------
# T023–T030: filters — category_id, recursive, parent_id
# ---------------------------------------------------------------------------


def test_search_items_category_filter_non_recursive(svc: TaxomeshService) -> None:
    cat = svc.create_category(name="Tech")
    in_cat = svc.create_item(name="Laptop Pro")
    out_of_cat = svc.create_item(name="Laptop Other")
    svc.place_item_in_category(in_cat.item_id, cat.category_id)
    results = svc.search_items("laptop", category_id=cat.category_id, recursive=False)
    ids = [i.item_id for i in results]
    assert in_cat.item_id in ids
    assert out_of_cat.item_id not in ids


def test_search_items_category_filter_nonexistent_raises(svc: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.search_items("laptop", category_id=uuid4())


def test_search_items_recursive_includes_descendants(svc: TaxomeshService) -> None:
    parent = svc.create_category(name="Tech")
    child = svc.create_category(name="Laptops")
    svc.add_category_parent(child.category_id, parent.category_id)
    item_in_child = svc.create_item(name="Laptop X")
    svc.place_item_in_category(item_in_child.item_id, child.category_id)
    results = svc.search_items("laptop", category_id=parent.category_id, recursive=True)
    assert any(i.item_id == item_in_child.item_id for i in results)


def test_search_items_recursive_deduplicates(svc: TaxomeshService) -> None:
    parent = svc.create_category(name="Tech")
    child = svc.create_category(name="Laptops")
    svc.add_category_parent(child.category_id, parent.category_id)
    item = svc.create_item(name="Laptop X")
    # Place same item in both parent and child
    svc.place_item_in_category(item.item_id, parent.category_id)
    svc.place_item_in_category(item.item_id, child.category_id)
    results = svc.search_items("laptop", category_id=parent.category_id, recursive=True)
    item_ids = [i.item_id for i in results]
    assert item_ids.count(item.item_id) == 1


def test_search_items_recursive_empty_category(svc: TaxomeshService) -> None:
    parent = svc.create_category(name="Tech")
    results = svc.search_items("laptop", category_id=parent.category_id, recursive=True)
    assert results == []


def test_search_categories_parent_filter(svc: TaxomeshService) -> None:
    parent = svc.create_category(name="Tech")
    child = svc.create_category(name="Laptops")
    svc.add_category_parent(child.category_id, parent.category_id)
    other = svc.create_category(name="Laptops Other")  # under root
    results = svc.search_categories("laptop", parent_id=parent.category_id)
    ids = [r.category_id for r in results]
    assert child.category_id in ids
    assert other.category_id not in ids


def test_search_categories_parent_filter_nonexistent_raises(svc: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.search_categories("x", parent_id=uuid4())


# ---------------------------------------------------------------------------
# T031–T034: Edge cases
# ---------------------------------------------------------------------------


def test_search_items_unicode_query(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Café Laptop")
    results = svc.search_items("café")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_slug_match(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Some Item", slug="laptop-pro-2024")
    results = svc.search_items("laptop-pro")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_external_id_match(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Generic Name", external_id="SKU-999")
    results = svc.search_items("SKU-999")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_all_disabled_enabled_only(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Laptop Test")
    svc.update_item(item.item_id, enabled=False)
    results = svc.search_items("laptop", enabled_only=True)
    assert results == []


def test_search_categories_all_disabled_enabled_only(svc: TaxomeshService) -> None:
    disabled = svc.create_category(name="Disabled Electronics")
    results = svc.search_categories("disabled electronics", enabled_only=False)
    ids = [r.category_id for r in results]
    assert disabled.category_id in ids


def test_search_items_no_items_returns_empty(svc: TaxomeshService) -> None:
    """Search on an empty repository returns empty list, not error."""
    results = svc.search_items("anything")
    assert results == []


# ---------------------------------------------------------------------------
# T035–T036: enabled_only=False and fuzzy=False
# ---------------------------------------------------------------------------


def test_search_items_enabled_only_false_includes_disabled(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Laptop Disabled")
    svc.update_item(item.item_id, enabled=False)
    results = svc.search_items("laptop", enabled_only=False)
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_fuzzy_false_exact_still_works(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Laptop Pro")
    results = svc.search_items("laptop", fuzzy=False)
    assert any(i.item_id == item.item_id for i in results)


# ---------------------------------------------------------------------------
# C1: Missing T017 ranking tests (SC-005 requires ≥ 3 ranking-behavior cases)
# ---------------------------------------------------------------------------


def test_search_items_exact_phrase_ranks_above_partial(svc: TaxomeshService) -> None:
    """'gallo ciego' should rank above 'gallo' when both exist (spec US2 scenario 1)."""
    partial = svc.create_item(name="Gallo")
    exact = svc.create_item(name="Gallo Ciego")
    results = svc.search_items("gallo ciego")
    ids = [i.item_id for i in results]
    assert exact.item_id in ids
    assert ids.index(exact.item_id) < ids.index(partial.item_id)


def test_search_items_prefix_ranks_above_substring(svc: TaxomeshService) -> None:
    """Item whose name starts with the query should rank above one that only contains it."""
    substring_only = svc.create_item(name="Tango Milonga Style")  # "tango" is a word, but not a full-name prefix
    prefix = svc.create_item(name="Tango Style")
    results = svc.search_items("tango style")
    ids = [i.item_id for i in results]
    assert ids.index(prefix.item_id) < ids.index(substring_only.item_id)


# ---------------------------------------------------------------------------
# C2: Missing US1 service-level acceptance scenarios (T014 items 6-8)
# ---------------------------------------------------------------------------


def test_search_items_typo_tolerant_piazola(svc: TaxomeshService) -> None:
    """'piazola' (typo) should find 'Piazzolla' (spec US1 scenario 1)."""
    item = svc.create_item(name="Piazzolla")
    results = svc.search_items("piazola")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_accent_insensitive_query(svc: TaxomeshService) -> None:
    """Accent-stripped query 'agustin magaldi' should find 'Agustín Magaldi' (spec US1 scenario 3)."""
    item = svc.create_item(name="Agustín Magaldi")
    results = svc.search_items("agustin magaldi")
    assert any(i.item_id == item.item_id for i in results)


def test_search_items_punctuation_insensitive(svc: TaxomeshService) -> None:
    """'d arienzo' (punctuation removed) should find 'D'Arienzo' (spec US1 scenario 4)."""
    item = svc.create_item(name="D'Arienzo")
    results = svc.search_items("d arienzo")
    assert any(i.item_id == item.item_id for i in results)


# ---------------------------------------------------------------------------
# C3: Missing US3 category service-level acceptance scenarios (T020 items 3-4)
# ---------------------------------------------------------------------------


def test_search_categories_typo_tolerant(svc: TaxomeshService) -> None:
    """'orkesta tipika' (typo) should find 'Orquesta Típica' (spec US3 scenario 1)."""
    cat = svc.create_category(name="Orquesta Típica")
    results = svc.search_categories("orkesta tipika")
    assert any(r.category_id == cat.category_id for r in results)


def test_search_categories_accent_insensitive(svc: TaxomeshService) -> None:
    """'tango romantico' should find 'Tango Romántico' (spec US3 scenario 2)."""
    cat = svc.create_category(name="Tango Romántico")
    results = svc.search_categories("tango romantico")
    assert any(r.category_id == cat.category_id for r in results)


# ---------------------------------------------------------------------------
# C4: Missing exact-slug match tests at service level (T014 item 2, T012 item 2)
# ---------------------------------------------------------------------------


def test_search_items_exact_slug_match(svc: TaxomeshService) -> None:
    item = svc.create_item(name="Some Item", slug="piazzolla")
    results = svc.search_items("piazzolla")
    assert any(i.item_id == item.item_id for i in results)


def test_search_categories_exact_slug_match(svc: TaxomeshService) -> None:
    cat = svc.create_category(name="Some Category", slug="orquesta-tipica")
    results = svc.search_categories("orquesta tipica")
    assert any(r.category_id == cat.category_id for r in results)
