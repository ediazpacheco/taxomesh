"""Tests for fuzzy search."""

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
# SearchEngine.normalize()
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
# score_candidate — boost signals (non-fuzzy)
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
# score_candidate — fuzzy path
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
# items.search — basic behaviour
# ---------------------------------------------------------------------------


def test_items_search_returns_list(svc: TaxomeshService) -> None:
    svc.items.create(name="Laptop Pro", slug="laptop-pro")
    results = svc.items.search("laptop")
    assert isinstance(results, tuple)


def test_items_search_empty_query_returns_empty(svc: TaxomeshService) -> None:
    svc.items.create(name="Laptop Pro", slug="laptop-pro")
    assert svc.items.search("   ") == ()


def test_items_search_invalid_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.items.search("x", limit=0)


def test_items_search_negative_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.items.search("x", limit=-1)


def test_items_search_exact_match_found(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Laptop Pro", slug="laptop-pro")
    results = svc.items.search("laptop pro")
    ids = [i.item_id for i in results]
    assert item.item_id in ids


def test_items_search_prefix_match_found(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Laptop Stand")
    results = svc.items.search("lap")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_respects_limit(svc: TaxomeshService) -> None:
    for i in range(10):
        svc.items.create(name=f"Laptop Model {i}")
    results = svc.items.search("laptop", limit=3)
    assert len(results) <= 3


def test_items_search_enabled_true_filters_disabled(svc: TaxomeshService) -> None:
    enabled_item = svc.items.create(name="Laptop Enabled")
    disabled_item = svc.items.create(name="Laptop Disabled")
    svc.items.update(disabled_item.item_id, enabled=False)
    results = svc.items.search("laptop", enabled=True)
    ids = [i.item_id for i in results]
    assert enabled_item.item_id in ids
    assert disabled_item.item_id not in ids


def test_items_search_no_match_returns_empty(svc: TaxomeshService) -> None:
    svc.items.create(name="Laptop Pro")
    results = svc.items.search("zzzzzzzzz", fuzzy=False)
    assert results == ()


def test_items_search_exact_match_ranked_first(svc: TaxomeshService) -> None:
    """Exact match should appear before partial/fuzzy matches."""
    svc.items.create(name="Laptop Stand")
    exact = svc.items.create(name="Laptop")
    results = svc.items.search("laptop")
    assert results[0].item_id == exact.item_id


# ---------------------------------------------------------------------------
# categories.search — basic behaviour
# ---------------------------------------------------------------------------


def test_categories_search_returns_list(svc: TaxomeshService) -> None:
    svc.categories.create(name="Electronics")
    results = svc.categories.search("electr")
    assert isinstance(results, tuple)


def test_categories_search_empty_query_returns_empty(svc: TaxomeshService) -> None:
    svc.categories.create(name="Electronics")
    assert svc.categories.search("   ") == ()


def test_categories_search_invalid_limit_raises(svc: TaxomeshService) -> None:
    with pytest.raises(ValueError):
        svc.categories.search("x", limit=0)


def test_categories_search_root_excluded(svc: TaxomeshService) -> None:
    """Root category must never appear in search results."""
    results = svc.categories.search(ROOT_CATEGORY_NAME)
    assert all(r.name != ROOT_CATEGORY_NAME for r in results)


def test_categories_search_exact_match_found(svc: TaxomeshService) -> None:
    cat = svc.categories.create(name="Electronics")
    results = svc.categories.search("Electronics")
    assert any(r.category_id == cat.category_id for r in results)


# ---------------------------------------------------------------------------
# Filters — category_id, recursive, parent_id
# ---------------------------------------------------------------------------


def test_items_search_category_filter_non_recursive(svc: TaxomeshService) -> None:
    cat = svc.categories.create(name="Tech")
    in_cat = svc.items.create(name="Laptop Pro")
    out_of_cat = svc.items.create(name="Laptop Other")
    svc.items.place_in(in_cat.item_id, cat.category_id)
    results = svc.items.search("laptop", category=cat.category_id, recursive=False)
    ids = [i.item_id for i in results]
    assert in_cat.item_id in ids
    assert out_of_cat.item_id not in ids


def test_items_search_category_filter_nonexistent_raises(svc: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.items.search("laptop", category=uuid4())


def test_items_search_recursive_includes_descendants(svc: TaxomeshService) -> None:
    parent = svc.categories.create(name="Tech")
    child = svc.categories.create(name="Laptops")
    svc.categories.add_parent(child.category_id, parent.category_id)
    item_in_child = svc.items.create(name="Laptop X")
    svc.items.place_in(item_in_child.item_id, child.category_id)
    results = svc.items.search("laptop", category=parent.category_id, recursive=True)
    assert any(i.item_id == item_in_child.item_id for i in results)


def test_items_search_recursive_deduplicates(svc: TaxomeshService) -> None:
    parent = svc.categories.create(name="Tech")
    child = svc.categories.create(name="Laptops")
    svc.categories.add_parent(child.category_id, parent.category_id)
    item = svc.items.create(name="Laptop X")
    # Place same item in both parent and child
    svc.items.place_in(item.item_id, parent.category_id)
    svc.items.place_in(item.item_id, child.category_id)
    results = svc.items.search("laptop", category=parent.category_id, recursive=True)
    item_ids = [i.item_id for i in results]
    assert item_ids.count(item.item_id) == 1


def test_items_search_recursive_empty_category(svc: TaxomeshService) -> None:
    parent = svc.categories.create(name="Tech")
    results = svc.items.search("laptop", category=parent.category_id, recursive=True)
    assert results == ()


def test_categories_search_parent_filter(svc: TaxomeshService) -> None:
    parent = svc.categories.create(name="Tech")
    child = svc.categories.create(name="Laptops")
    svc.categories.add_parent(child.category_id, parent.category_id)
    other = svc.categories.create(name="Laptops Other")  # under root
    results = svc.categories.search("laptop", parent=parent.category_id)
    ids = [r.category_id for r in results]
    assert child.category_id in ids
    assert other.category_id not in ids


def test_categories_search_parent_filter_nonexistent_raises(svc: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.categories.search("x", parent=uuid4())


BLANK_QUERIES = ["", "   "]


class TestABlankQueryStillChecksItsFilter:
    """A blank query answers ``[]``, but only once its filter is known to name a stored row.

    A filter naming a row that is not stored is a wrong address rather than a miss, and raises
    that row's not-found error. A blank query checks the filter first, so a wrong address raises
    under ``""`` as it does under ``"x"``.
    """

    @pytest.mark.parametrize("query", BLANK_QUERIES)
    def test_categories_unknown_parent_raises(self, svc: TaxomeshService, query: str) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            svc.categories.search(query, parent=uuid4())

    @pytest.mark.parametrize("query", BLANK_QUERIES)
    def test_items_unknown_category_raises(self, svc: TaxomeshService, query: str) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            svc.items.search(query, category=uuid4())

    @pytest.mark.parametrize("query", BLANK_QUERIES)
    def test_items_unknown_subtree_raises(self, svc: TaxomeshService, query: str) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            svc.items.search(query, category=uuid4(), recursive=True)

    @pytest.mark.parametrize("query", BLANK_QUERIES)
    def test_items_the_root_as_a_subtree_raises(self, svc: TaxomeshService, query: str) -> None:
        """The implicit root is never a subtree to descend from."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            svc.items.search(query, category=svc._root_id, recursive=True)

    @pytest.mark.parametrize("query", BLANK_QUERIES)
    def test_a_stored_filter_still_answers_empty(self, svc: TaxomeshService, query: str) -> None:
        """Guard: checking the filter does not stop a blank query from answering ``[]``."""
        tech = svc.categories.create(name="Tech")
        laptop = svc.items.create(name="Laptop")
        svc.items.place_in(laptop.item_id, tech.category_id)

        assert svc.categories.search(query, parent=tech.category_id) == ()
        assert svc.items.search(query, category=tech.category_id) == ()
        assert svc.items.search(query, category=tech.category_id, recursive=True) == ()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_items_search_unicode_query(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Café Laptop")
    results = svc.items.search("café")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_slug_match(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Some Item", slug="laptop-pro-2024")
    results = svc.items.search("laptop-pro")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_external_id_match(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Generic Name", external_id="SKU-999")
    results = svc.items.search("SKU-999")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_all_disabled_enabled_true(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Laptop Test")
    svc.items.update(item.item_id, enabled=False)
    results = svc.items.search("laptop", enabled=True)
    assert results == ()


def test_categories_search_all_disabled_enabled_true(svc: TaxomeshService) -> None:
    disabled = svc.categories.create(name="Disabled Electronics")
    # Actually disable the category so it appears when enabled=False
    disabled_obj = svc.repository.find_category(disabled.category_id)
    assert disabled_obj is not None
    svc.repository.save_category(disabled_obj.model_copy(update={"enabled": False}))
    svc._category_corpus.invalidate()
    results = svc.categories.search("disabled electronics", enabled=False)
    ids = [r.category_id for r in results]
    assert disabled.category_id in ids


def test_items_search_no_items_returns_empty(svc: TaxomeshService) -> None:
    """Search on an empty repository returns empty list, not error."""
    results = svc.items.search("anything")
    assert results == ()


# ---------------------------------------------------------------------------
# Enabled=False and fuzzy=False
# ---------------------------------------------------------------------------


def test_items_search_enabled_false_includes_disabled(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Laptop Disabled")
    svc.items.update(item.item_id, enabled=False)
    results = svc.items.search("laptop", enabled=False)
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_fuzzy_false_exact_still_works(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Laptop Pro")
    results = svc.items.search("laptop", fuzzy=False)
    assert any(i.item_id == item.item_id for i in results)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def test_items_search_exact_phrase_ranks_above_partial(svc: TaxomeshService) -> None:
    """'gallo ciego' should rank above 'gallo' when both exist."""
    partial = svc.items.create(name="Gallo")
    exact = svc.items.create(name="Gallo Ciego")
    results = svc.items.search("gallo ciego")
    ids = [i.item_id for i in results]
    assert exact.item_id in ids
    assert ids.index(exact.item_id) < ids.index(partial.item_id)


def test_items_search_prefix_ranks_above_substring(svc: TaxomeshService) -> None:
    """Item whose name starts with the query should rank above one that only contains it."""
    substring_only = svc.items.create(name="Tango Milonga Style")  # "tango" is a word, but not a full-name prefix
    prefix = svc.items.create(name="Tango Style")
    results = svc.items.search("tango style")
    ids = [i.item_id for i in results]
    assert ids.index(prefix.item_id) < ids.index(substring_only.item_id)


# ---------------------------------------------------------------------------
# Typos, accents and punctuation in an item search
# ---------------------------------------------------------------------------


def test_items_search_typo_tolerant_piazola(svc: TaxomeshService) -> None:
    """'piazola' (typo) should find 'Piazzolla'."""
    item = svc.items.create(name="Piazzolla")
    results = svc.items.search("piazola")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_accent_insensitive_query(svc: TaxomeshService) -> None:
    """Accent-stripped query 'agustin magaldi' should find 'Agustín Magaldi'."""
    item = svc.items.create(name="Agustín Magaldi")
    results = svc.items.search("agustin magaldi")
    assert any(i.item_id == item.item_id for i in results)


def test_items_search_punctuation_insensitive(svc: TaxomeshService) -> None:
    """'d arienzo' (punctuation removed) should find 'D'Arienzo'."""
    item = svc.items.create(name="D'Arienzo")
    results = svc.items.search("d arienzo")
    assert any(i.item_id == item.item_id for i in results)


# ---------------------------------------------------------------------------
# Typos and accents in a category search
# ---------------------------------------------------------------------------


def test_categories_search_typo_tolerant(svc: TaxomeshService) -> None:
    """'orkesta tipika' (typo) should find 'Orquesta Típica'."""
    cat = svc.categories.create(name="Orquesta Típica")
    results = svc.categories.search("orkesta tipika")
    assert any(r.category_id == cat.category_id for r in results)


def test_categories_search_accent_insensitive(svc: TaxomeshService) -> None:
    """'tango romantico' should find 'Tango Romántico'."""
    cat = svc.categories.create(name="Tango Romántico")
    results = svc.categories.search("tango romantico")
    assert any(r.category_id == cat.category_id for r in results)


# ---------------------------------------------------------------------------
# An exact slug match
# ---------------------------------------------------------------------------


def test_items_search_exact_slug_match(svc: TaxomeshService) -> None:
    item = svc.items.create(name="Some Item", slug="piazzolla")
    results = svc.items.search("piazzolla")
    assert any(i.item_id == item.item_id for i in results)


def test_categories_search_exact_slug_match(svc: TaxomeshService) -> None:
    cat = svc.categories.create(name="Some Category", slug="orquesta-tipica")
    results = svc.categories.search("orquesta tipica")
    assert any(r.category_id == cat.category_id for r in results)


# ---------------------------------------------------------------------------
# Top-k correctness and fuzzy survival
# ---------------------------------------------------------------------------


def test_topk_matches_full_sort(svc: TaxomeshService) -> None:
    """items.search(q, limit=5) must return the same items in the same order
    as the first 5 of items.search(q, limit=50) for varied queries.

    This documents the top-k invariant: using a smaller limit must not change
    which items are selected, only how many are returned.
    """
    names = [
        "Apple",
        "Apricot",
        "Avocado",
        "Appetizer",
        "Application",
        "Banana",
        "Cherry",
        "Date",
        "Elderberry",
        "Fig",
        "Grape",
        "Honeydew",
        "Kiwi",
        "Lemon",
        "Mango",
        "Nectarine",
        "Orange",
        "Papaya",
        "Quince",
        "Raspberry",
        "Strawberry",
        "Tangerine",
        "Ugli Fruit",
        "Vanilla",
        "Watermelon",
        "Apricot Jam",
        "Apple Pie",
        "Avocado Toast",
        "Banana Bread",
        "Cherry Tart",
        "Apple Sauce",
        "Apple Cider",
        "Apple Juice",
        "Apple Core",
        "Apple Seed",
        "Apricot Tree",
        "Avocado Oil",
        "Banana Split",
        "Cherry Blossom",
        "Date Sugar",
        "Apple Farm",
        "Apple Park",
        "Apricot Extra",
        "Avocado Green",
        "Banana Yellow",
        "Cherry Red",
        "Apple Tree",
        "Apple Fresh",
        "Apricot New",
        "Avocado Fresh",
    ]
    for name in names:
        svc.items.create(name=name, slug=name.lower().replace(" ", "-"))

    queries = ["app", "apri", "avo", "ban", "che", "apple", "apricot", "avocado", "banana", "cherry"]
    for q in queries:
        top5 = [i.item_id for i in svc.items.search(q, limit=5)]
        all_results = [i.item_id for i in svc.items.search(q, limit=50)]
        # The limit=5 result must be a prefix of the full result list
        assert top5 == all_results[: len(top5)], (
            f"top-k mismatch for query {q!r}: limit=5 gave {top5}, "
            f"limit=50 first {len(top5)} are {all_results[: len(top5)]}"
        )


# ---------------------------------------------------------------------------
# Ordering stability
# ---------------------------------------------------------------------------


def test_tie_breaking_by_norm_name(svc: TaxomeshService) -> None:
    """When multiple items produce equal scores, they must be ordered by
    normalized name ascending — stable before and after the optimization.
    """
    # All five names contain "widget" so they share the same boost tier;
    # tie-breaking must produce alphabetical order by normalized name.
    names = ["Widget Zeta", "Widget Alpha", "Widget Mu", "Widget Beta", "Widget Eta"]
    items = [svc.items.create(name=n, slug=n.lower().replace(" ", "-")) for n in names]
    _ = items  # referenced via results

    results = svc.items.search("widget", limit=10)
    result_names = [i.name for i in results]
    norm_names_in_order = [SearchEngine.normalize(n) for n in result_names]
    # Scores must be non-increasing
    assert norm_names_in_order == sorted(norm_names_in_order), f"Tie-breaking order wrong: {norm_names_in_order}"


def test_topk_order_identical_to_full_sort(svc: TaxomeshService) -> None:
    """items.search(q, limit=10) must return the same 10 items in the same order
    as the first 10 of items.search(q, limit=100) for varied queries.
    """
    # 100 items with predictable score distribution for several prefix queries
    prefixes = ["alpha", "beta", "gamma", "delta", "epsilon"]
    for prefix in prefixes:
        for i in range(20):
            svc.items.create(
                name=f"{prefix.capitalize()} Item {i:02d}",
                slug=f"{prefix}-item-{i:02d}",
            )

    for q in prefixes:
        top10 = [i.item_id for i in svc.items.search(q, limit=10)]
        all_results = [i.item_id for i in svc.items.search(q, limit=100)]
        assert top10 == all_results[: len(top10)], (
            f"Ordering mismatch for query {q!r}: limit=10 gave {top10}, limit=100 first 10 are {all_results[:10]}"
        )


def test_fuzzy_match_survives_small_limit(svc: TaxomeshService) -> None:
    """A fuzzy match that ranks within the limit must appear in results.

    Ensures that top-k selection does not accidentally drop fuzzy-scored items
    that would rank in the top-k under the full-sort order.
    """
    fuzzy_item = svc.items.create(name="Laptop Pro", slug="laptop-pro")
    # Items that score None for the typo query (no structural or fuzzy match)
    svc.items.create(name="Refrigerator", slug="fridge")
    svc.items.create(name="Washing Machine", slug="washer")

    results = svc.items.search("labtop", limit=3, fuzzy=True)
    ids = [i.item_id for i in results]
    assert fuzzy_item.item_id in ids
