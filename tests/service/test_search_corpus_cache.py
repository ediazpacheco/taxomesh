"""Tests for the internal search corpus cache (040-search-corpus-cache).

Covers:
- Corpus reuse: repeated searches do not rebuild candidates or hit the repo again.
- Corpus invalidation: item/category writes reset the corpus.
- Placement/link operations do not invalidate the corpus.
- Correctness after invalidation: writes are reflected immediately in search.
- Ranking regression: scoring semantics are unchanged.
- Filtered/recursive search paths are unaffected by the corpus cache.
- get_debug() exposes corpus sizes.
"""

from unittest.mock import patch

import pytest

from taxomesh.application.service import TaxomeshService
from tests.service.conftest import InMemoryRepository

# ---------------------------------------------------------------------------
# Local fixture — fresh InMemoryRepository-backed service per test
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> TaxomeshService:
    """Return a TaxomeshService with a fresh in-memory backend."""
    return TaxomeshService(repository=InMemoryRepository())


# ---------------------------------------------------------------------------
# Phase 1: Setup validation — cold cache returns correct results (FR-004)
# ---------------------------------------------------------------------------


def test_cold_cache_item_search_returns_correct_results(svc: TaxomeshService) -> None:
    """First search_items() call on a cold service must return correct results."""
    svc.create_item(name="Piazzolla")
    svc.create_item(name="Unrelated Widget")
    results = svc.search_items("piazzolla")
    names = [i.name for i in results]
    assert "Piazzolla" in names
    assert "Unrelated Widget" not in names


def test_cold_cache_category_search_returns_correct_results(svc: TaxomeshService) -> None:
    """First search_categories() call on a cold service must return correct results."""
    svc.create_category(name="Tango")
    svc.create_category(name="Rock")
    results = svc.search_categories("tango")
    names = [c.name for c in results]
    assert "Tango" in names
    assert "Rock" not in names


# ---------------------------------------------------------------------------
# Phase 3: US1 — corpus built once and reused (FR-001, FR-002, FR-005, FR-006)
# ---------------------------------------------------------------------------


def test_item_search_reuses_memoized_list_items(svc: TaxomeshService) -> None:
    """After the first search, repeated searches must not reload the item list."""
    svc.create_item(name="Alpha")
    svc.create_item(name="Beta")
    with patch.object(svc._repo, "list_items", wraps=svc._repo.list_items) as mock_list:
        svc.search_items("alpha")
        svc.search_items("beta")
        # corpus built on first call; second call reuses it — repo not queried again
        assert mock_list.call_count <= 1


def test_item_corpus_built_once_and_reused(svc: TaxomeshService) -> None:
    """_item_corpus must be the same list object across repeated searches."""
    svc.create_item(name="Alpha")
    svc.search_items("alpha")
    corpus_id_before = id(svc._item_corpus)
    svc.search_items("beta")
    assert id(svc._item_corpus) == corpus_id_before


def test_category_search_reuses_cached_corpus(svc: TaxomeshService) -> None:
    """After the first category search, the repo must not be queried again."""
    svc.create_category(name="Jazz")
    svc.create_category(name="Blues")
    with patch.object(svc._repo, "list_categories", wraps=svc._repo.list_categories) as mock_list:
        svc.search_categories("jazz")
        svc.search_categories("blues")
        assert mock_list.call_count <= 1


def test_category_corpus_built_once_and_reused(svc: TaxomeshService) -> None:
    """_category_corpus must be the same list object across repeated searches."""
    svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    corpus_id_before = id(svc._category_corpus)
    svc.search_categories("blues")
    assert id(svc._category_corpus) == corpus_id_before


def test_item_corpus_is_none_before_first_search(svc: TaxomeshService) -> None:
    """_item_corpus must be None before any search call."""
    assert svc._item_corpus is None


def test_category_corpus_is_none_before_first_search(svc: TaxomeshService) -> None:
    """_category_corpus must be None before any search call."""
    assert svc._category_corpus is None


def test_item_corpus_populated_after_search(svc: TaxomeshService) -> None:
    """_item_corpus must be a non-None list after a successful item search."""
    svc.create_item(name="Alpha")
    svc.search_items("alpha")
    assert svc._item_corpus is not None
    assert len(svc._item_corpus) >= 1


def test_category_corpus_populated_after_search(svc: TaxomeshService) -> None:
    """_category_corpus must be a non-None list after a successful category search."""
    svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    assert svc._category_corpus is not None
    assert len(svc._category_corpus) >= 1


# ---------------------------------------------------------------------------
# Phase 4: US2 — corpus invalidation on writes (FR-009, FR-010)
# ---------------------------------------------------------------------------


def test_create_item_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """create_item must reset _item_corpus to None."""
    svc.create_item(name="Alpha")
    svc.search_items("alpha")
    assert svc._item_corpus is not None
    svc.create_item(name="Beta")
    assert svc._item_corpus is None


def test_update_item_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """update_item must reset _item_corpus to None."""
    item = svc.create_item(name="Alpha")
    svc.search_items("alpha")
    assert svc._item_corpus is not None
    svc.update_item(item.item_id, name="Alpha Updated")
    assert svc._item_corpus is None


def test_delete_item_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """delete_item must reset _item_corpus to None."""
    item = svc.create_item(name="Alpha")
    svc.search_items("alpha")
    assert svc._item_corpus is not None
    svc.delete_item(item.item_id)
    assert svc._item_corpus is None


def test_create_category_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """create_category must reset _category_corpus to None."""
    svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    assert svc._category_corpus is not None
    svc.create_category(name="Blues")
    assert svc._category_corpus is None


def test_update_category_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """update_category must reset _category_corpus to None."""
    cat = svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    assert svc._category_corpus is not None
    svc.update_category(cat.category_id, name="Modern Jazz")
    assert svc._category_corpus is None


def test_delete_category_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """delete_category must reset _category_corpus to None."""
    cat = svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    assert svc._category_corpus is not None
    svc.delete_category(cat.category_id)
    assert svc._category_corpus is None


def test_new_item_appears_in_search_after_create(svc: TaxomeshService) -> None:
    """After create_item, the new item must appear in subsequent search results."""
    svc.create_item(name="Alpha")
    svc.search_items("alpha")  # warm corpus
    svc.create_item(name="Piazzolla Tango")
    results = svc.search_items("piazzolla")
    names = [i.name for i in results]
    assert "Piazzolla Tango" in names


def test_updated_item_name_searchable_after_update(svc: TaxomeshService) -> None:
    """After update_item, the updated name must be findable in subsequent searches."""
    item = svc.create_item(name="OldName")
    svc.search_items("oldname")  # warm corpus
    svc.update_item(item.item_id, name="NewUniqueName")
    results = svc.search_items("newuniquename")
    names = [i.name for i in results]
    assert "NewUniqueName" in names


def test_deleted_item_absent_from_search_after_delete(svc: TaxomeshService) -> None:
    """After delete_item, the deleted item must not appear in subsequent searches."""
    item = svc.create_item(name="ToDelete")
    svc.search_items("todelete")  # warm corpus
    svc.delete_item(item.item_id)
    results = svc.search_items("todelete")
    names = [i.name for i in results]
    assert "ToDelete" not in names


def test_new_category_appears_in_search_after_create(svc: TaxomeshService) -> None:
    """After create_category, the new category must appear in subsequent searches."""
    svc.create_category(name="Jazz")
    svc.search_categories("jazz")  # warm corpus
    svc.create_category(name="BossaNova Fusion")
    results = svc.search_categories("bossanova")
    names = [c.name for c in results]
    assert "BossaNova Fusion" in names


# ---------------------------------------------------------------------------
# Phase 4: placement/link operations must NOT invalidate the corpus
# ---------------------------------------------------------------------------


def test_place_item_in_category_does_not_invalidate_corpus(svc: TaxomeshService) -> None:
    """place_item_in_category must NOT reset _item_corpus."""
    item = svc.create_item(name="Alpha")
    cat = svc.create_category(name="Music")
    svc.search_items("alpha")  # warm corpus
    assert svc._item_corpus is not None
    svc.place_item_in_category(item.item_id, cat.category_id)
    assert svc._item_corpus is not None


def test_remove_item_from_category_does_not_invalidate_corpus(svc: TaxomeshService) -> None:
    """remove_item_from_category must NOT reset _item_corpus."""
    item = svc.create_item(name="Alpha")
    cat = svc.create_category(name="Music")
    svc.place_item_in_category(item.item_id, cat.category_id)
    svc.search_items("alpha")  # warm corpus
    assert svc._item_corpus is not None
    svc.remove_item_from_category(item.item_id, cat.category_id)
    assert svc._item_corpus is not None


def test_add_category_parent_does_not_invalidate_category_corpus(svc: TaxomeshService) -> None:
    """add_category_parent must NOT reset _category_corpus."""
    parent = svc.create_category(name="Music")
    child = svc.create_category(name="Jazz")
    svc.search_categories("jazz")  # warm corpus
    assert svc._category_corpus is not None
    svc.add_category_parent(child.category_id, parent.category_id)
    assert svc._category_corpus is not None


# ---------------------------------------------------------------------------
# Phase 5: US3 — ranking regression (FR-012, FR-014, FR-015, FR-016)
# ---------------------------------------------------------------------------


def test_exact_match_ranked_first(svc: TaxomeshService) -> None:
    """An exact name match must score higher than a partial match."""
    svc.create_item(name="Piazzolla")
    svc.create_item(name="Piazzolla Tango Nuevo")
    results = svc.search_items("piazzolla", fuzzy=False)
    assert results[0].name == "Piazzolla"


def test_fuzzy_search_returns_near_match(svc: TaxomeshService) -> None:
    """fuzzy=True must return items that are close but not exact matches."""
    svc.create_item(name="Piazzolla")
    results = svc.search_items("piazola", fuzzy=True)
    names = [i.name for i in results]
    assert "Piazzolla" in names


def test_non_fuzzy_excludes_fuzzy_only_match(svc: TaxomeshService) -> None:
    """fuzzy=False must exclude items that only match via fuzzy scoring."""
    svc.create_item(name="Piazzolla")
    results = svc.search_items("piazola", fuzzy=False)
    names = [i.name for i in results]
    assert "Piazzolla" not in names


def test_empty_query_returns_empty_items(svc: TaxomeshService) -> None:
    """Empty query string must return an empty list for items."""
    svc.create_item(name="Alpha")
    assert svc.search_items("") == []


def test_whitespace_query_returns_empty_items(svc: TaxomeshService) -> None:
    """Whitespace-only query must return an empty list for items."""
    svc.create_item(name="Alpha")
    assert svc.search_items("   ") == []


def test_empty_query_returns_empty_categories(svc: TaxomeshService) -> None:
    """Empty query string must return an empty list for categories."""
    svc.create_category(name="Jazz")
    assert svc.search_categories("") == []


def test_whitespace_query_returns_empty_categories(svc: TaxomeshService) -> None:
    """Whitespace-only query must return an empty list for categories."""
    svc.create_category(name="Jazz")
    assert svc.search_categories("   ") == []


def test_accent_insensitive_item_search(svc: TaxomeshService) -> None:
    """Accent-insensitive normalization must match accented names (FR-014)."""
    svc.create_item(name="Ñoño Café")
    results = svc.search_items("nono cafe", fuzzy=False)
    names = [i.name for i in results]
    assert "Ñoño Café" in names


# ---------------------------------------------------------------------------
# Phase 6: US4 — filtered/recursive search unaffected (FR-003)
# ---------------------------------------------------------------------------


def test_filtered_search_with_category_id_restricts_results(svc: TaxomeshService) -> None:
    """search_items with category_id must return only items in that category."""
    item_a = svc.create_item(name="ItemA Music")
    item_b = svc.create_item(name="ItemB Music")
    cat1 = svc.create_category(name="Category1")
    cat2 = svc.create_category(name="Category2")
    svc.place_item_in_category(item_a.item_id, cat1.category_id)
    svc.place_item_in_category(item_b.item_id, cat2.category_id)
    results = svc.search_items("music", category_id=cat1.category_id)
    item_ids = {i.item_id for i in results}
    assert item_a.item_id in item_ids
    assert item_b.item_id not in item_ids


def test_recursive_search_returns_subtree_items(svc: TaxomeshService) -> None:
    """recursive=True must include items in descendant categories."""
    root_cat = svc.create_category(name="RootCat")
    child_cat = svc.create_category(name="ChildCat")
    svc.add_category_parent(child_cat.category_id, root_cat.category_id)
    item = svc.create_item(name="DeepItem")
    svc.place_item_in_category(item.item_id, child_cat.category_id)
    results = svc.search_items("deepitem", category_id=root_cat.category_id, recursive=True)
    item_ids = {i.item_id for i in results}
    assert item.item_id in item_ids


def test_filtered_search_uses_live_data_not_corpus(svc: TaxomeshService) -> None:
    """Filtered search (category_id set) must not be affected by the global item corpus."""
    item = svc.create_item(name="CorpusItem")
    cat = svc.create_category(name="SomeCat")
    svc.place_item_in_category(item.item_id, cat.category_id)
    # Warm the global corpus
    svc.search_items("corpusitem")
    # Filtered search must still correctly restrict to the category
    results = svc.search_items("corpusitem", category_id=cat.category_id)
    item_ids = {i.item_id for i in results}
    assert item.item_id in item_ids


# ---------------------------------------------------------------------------
# Phase 7: get_debug() exposes corpus sizes (FR-026, SC-007)
# ---------------------------------------------------------------------------


def test_get_debug_item_corpus_size_is_none_before_search(svc: TaxomeshService) -> None:
    """get_debug() must return item_corpus_size=None before any search."""
    svc.create_item(name="Alpha")
    debug = svc.get_debug()
    assert debug["item_corpus_size"] is None


def test_get_debug_item_corpus_size_after_search(svc: TaxomeshService) -> None:
    """get_debug() must return item_corpus_size as a non-negative int after a search."""
    svc.create_item(name="Alpha")
    svc.create_item(name="Beta")
    svc.search_items("alpha")
    debug = svc.get_debug()
    assert debug["item_corpus_size"] == 2


def test_get_debug_item_corpus_size_resets_after_write(svc: TaxomeshService) -> None:
    """get_debug() must return item_corpus_size=None after an item write invalidates the corpus."""
    item = svc.create_item(name="Alpha")
    svc.search_items("alpha")
    assert svc.get_debug()["item_corpus_size"] == 1
    svc.delete_item(item.item_id)
    assert svc.get_debug()["item_corpus_size"] is None


def test_get_debug_category_corpus_size_is_none_before_search(svc: TaxomeshService) -> None:
    """get_debug() must return category_corpus_size=None before any category search."""
    svc.create_category(name="Jazz")
    debug = svc.get_debug()
    assert debug["category_corpus_size"] is None


def test_get_debug_category_corpus_size_after_search(svc: TaxomeshService) -> None:
    """get_debug() must return category_corpus_size as a non-negative int after a search."""
    svc.create_category(name="Jazz")
    svc.create_category(name="Blues")
    svc.search_categories("jazz")
    debug = svc.get_debug()
    assert debug["category_corpus_size"] == 2


def test_get_debug_category_corpus_size_resets_after_write(svc: TaxomeshService) -> None:
    """get_debug() must return category_corpus_size=None after a category write."""
    cat = svc.create_category(name="Jazz")
    svc.search_categories("jazz")
    assert svc.get_debug()["category_corpus_size"] == 1
    svc.delete_category(cat.category_id)
    assert svc.get_debug()["category_corpus_size"] is None
