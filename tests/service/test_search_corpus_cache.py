"""Tests for the internal search corpus cache.

Covers:
- Corpus reuse: repeated searches do not rebuild candidates or hit the repo again.
- Corpus invalidation: item/category writes reset the corpus.
- Placement/link operations do not invalidate the corpus.
- Correctness after invalidation: writes are reflected immediately in search.
- Ranking over a held corpus: exact before partial, fuzzy matches only when asked for.
- Filtered/recursive search paths are unaffected by the corpus cache.
- svc.info exposes corpus sizes.
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
# Setup validation — cold cache returns correct results
# ---------------------------------------------------------------------------


def test_cold_cache_item_search_returns_correct_results(svc: TaxomeshService) -> None:
    """First items.search() call on a cold service must return correct results."""
    svc.items.create(name="Piazzolla")
    svc.items.create(name="Unrelated Widget")
    results = svc.items.search("piazzolla")
    names = [i.name for i in results]
    assert "Piazzolla" in names
    assert "Unrelated Widget" not in names


def test_cold_cache_category_search_returns_correct_results(svc: TaxomeshService) -> None:
    """First categories.search() call on a cold service must return correct results."""
    svc.categories.create(name="Tango")
    svc.categories.create(name="Rock")
    results = svc.categories.search("tango")
    names = [c.name for c in results]
    assert "Tango" in names
    assert "Rock" not in names


# ---------------------------------------------------------------------------
# The corpus is built once and reused
# ---------------------------------------------------------------------------


def test_item_search_reuses_memoized_list_items(svc: TaxomeshService) -> None:
    """After the first search, repeated searches must not reload the item list."""
    svc.items.create(name="Alpha")
    svc.items.create(name="Beta")
    with patch.object(svc._repo, "list_items", wraps=svc._repo.list_items) as mock_list:
        svc.items.search("alpha")
        svc.items.search("beta")
        # corpus built on first call; second call reuses it — repo not queried again
        assert mock_list.call_count <= 1


def test_item_corpus_built_once_and_reused(svc: TaxomeshService) -> None:
    """_item_corpus must be the same list object across repeated searches."""
    svc.items.create(name="Alpha")
    svc.items.search("alpha")
    corpus_id_before = id(svc._item_corpus.candidates)
    svc.items.search("beta")
    assert id(svc._item_corpus.candidates) == corpus_id_before


def test_category_search_reuses_cached_corpus(svc: TaxomeshService) -> None:
    """After the first category search, the repo must not be queried again."""
    svc.categories.create(name="Jazz")
    svc.categories.create(name="Blues")
    with patch.object(svc._repo, "list_categories", wraps=svc._repo.list_categories) as mock_list:
        svc.categories.search("jazz")
        svc.categories.search("blues")
        assert mock_list.call_count <= 1


def test_category_corpus_built_once_and_reused(svc: TaxomeshService) -> None:
    """_category_corpus must be the same list object across repeated searches."""
    svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    corpus_id_before = id(svc._category_corpus.candidates)
    svc.categories.search("blues")
    assert id(svc._category_corpus.candidates) == corpus_id_before


def test_item_corpus_is_none_before_first_search(svc: TaxomeshService) -> None:
    """_item_corpus must be None before any search call."""
    assert svc._item_corpus.candidates is None


def test_category_corpus_is_none_before_first_search(svc: TaxomeshService) -> None:
    """_category_corpus must be None before any search call."""
    assert svc._category_corpus.candidates is None


def test_item_corpus_populated_after_search(svc: TaxomeshService) -> None:
    """_item_corpus must be a non-None list after a successful item search."""
    svc.items.create(name="Alpha")
    svc.items.search("alpha")
    assert svc._item_corpus.candidates is not None
    assert len(svc._item_corpus.candidates) >= 1


def test_category_corpus_populated_after_search(svc: TaxomeshService) -> None:
    """_category_corpus must be a non-None list after a successful category search."""
    svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    assert svc._category_corpus.candidates is not None
    assert len(svc._category_corpus.candidates) >= 1


# ---------------------------------------------------------------------------
# Writes invalidate the corpus
# ---------------------------------------------------------------------------


def test_items_create_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """items.create must reset _item_corpus to None."""
    svc.items.create(name="Alpha")
    svc.items.search("alpha")
    assert svc._item_corpus.candidates is not None
    svc.items.create(name="Beta")
    assert svc._item_corpus.candidates is None


def test_items_update_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """items.update must reset _item_corpus to None."""
    item = svc.items.create(name="Alpha")
    svc.items.search("alpha")
    assert svc._item_corpus.candidates is not None
    svc.items.update(item.item_id, name="Alpha Updated")
    assert svc._item_corpus.candidates is None


def test_items_delete_invalidates_item_corpus(svc: TaxomeshService) -> None:
    """items.delete must reset _item_corpus to None."""
    item = svc.items.create(name="Alpha")
    svc.items.search("alpha")
    assert svc._item_corpus.candidates is not None
    svc.items.delete(item.item_id)
    assert svc._item_corpus.candidates is None


def test_categories_create_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """categories.create must reset _category_corpus to None."""
    svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    assert svc._category_corpus.candidates is not None
    svc.categories.create(name="Blues")
    assert svc._category_corpus.candidates is None


def test_categories_update_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """categories.update must reset _category_corpus to None."""
    cat = svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    assert svc._category_corpus.candidates is not None
    svc.categories.update(cat.category_id, name="Modern Jazz")
    assert svc._category_corpus.candidates is None


def test_categories_delete_invalidates_category_corpus(svc: TaxomeshService) -> None:
    """categories.delete must reset _category_corpus to None."""
    cat = svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    assert svc._category_corpus.candidates is not None
    svc.categories.delete(cat.category_id)
    assert svc._category_corpus.candidates is None


def test_new_item_appears_in_search_after_create(svc: TaxomeshService) -> None:
    """After items.create, the new item must appear in subsequent search results."""
    svc.items.create(name="Alpha")
    svc.items.search("alpha")  # warm corpus
    svc.items.create(name="Piazzolla Tango")
    results = svc.items.search("piazzolla")
    names = [i.name for i in results]
    assert "Piazzolla Tango" in names


def test_updated_item_name_searchable_after_update(svc: TaxomeshService) -> None:
    """After items.update, the updated name must be findable in subsequent searches."""
    item = svc.items.create(name="OldName")
    svc.items.search("oldname")  # warm corpus
    svc.items.update(item.item_id, name="NewUniqueName")
    results = svc.items.search("newuniquename")
    names = [i.name for i in results]
    assert "NewUniqueName" in names


def test_deleted_item_absent_from_search_after_delete(svc: TaxomeshService) -> None:
    """After items.delete, the deleted item must not appear in subsequent searches."""
    item = svc.items.create(name="ToDelete")
    svc.items.search("todelete")  # warm corpus
    svc.items.delete(item.item_id)
    results = svc.items.search("todelete")
    names = [i.name for i in results]
    assert "ToDelete" not in names


def test_new_category_appears_in_search_after_create(svc: TaxomeshService) -> None:
    """After categories.create, the new category must appear in subsequent searches."""
    svc.categories.create(name="Jazz")
    svc.categories.search("jazz")  # warm corpus
    svc.categories.create(name="BossaNova Fusion")
    results = svc.categories.search("bossanova")
    names = [c.name for c in results]
    assert "BossaNova Fusion" in names


# ---------------------------------------------------------------------------
# Placement/link operations must NOT invalidate the corpus
# ---------------------------------------------------------------------------


def test_place_in_does_not_invalidate_corpus(svc: TaxomeshService) -> None:
    """items.place_in must NOT reset _item_corpus."""
    item = svc.items.create(name="Alpha")
    cat = svc.categories.create(name="Music")
    svc.items.search("alpha")  # warm corpus
    assert svc._item_corpus.candidates is not None
    svc.items.place_in(item.item_id, cat.category_id)
    assert svc._item_corpus.candidates is not None


def test_remove_from_does_not_invalidate_corpus(svc: TaxomeshService) -> None:
    """items.remove_from must NOT reset _item_corpus."""
    item = svc.items.create(name="Alpha")
    cat = svc.categories.create(name="Music")
    svc.items.place_in(item.item_id, cat.category_id)
    svc.items.search("alpha")  # warm corpus
    assert svc._item_corpus.candidates is not None
    svc.items.remove_from(item.item_id, cat.category_id)
    assert svc._item_corpus.candidates is not None


def test_categories_add_parent_does_not_invalidate_category_corpus(svc: TaxomeshService) -> None:
    """categories.add_parent must NOT reset _category_corpus."""
    parent = svc.categories.create(name="Music")
    child = svc.categories.create(name="Jazz")
    svc.categories.search("jazz")  # warm corpus
    assert svc._category_corpus.candidates is not None
    svc.categories.add_parent(child.category_id, parent.category_id)
    assert svc._category_corpus.candidates is not None


# ---------------------------------------------------------------------------
# Ranking over a held corpus
# ---------------------------------------------------------------------------


def test_exact_match_ranked_first(svc: TaxomeshService) -> None:
    """An exact name match must score higher than a partial match."""
    svc.items.create(name="Piazzolla")
    svc.items.create(name="Piazzolla Tango Nuevo")
    results = svc.items.search("piazzolla", fuzzy=False)
    assert results[0].name == "Piazzolla"


def test_fuzzy_search_returns_near_match(svc: TaxomeshService) -> None:
    """fuzzy=True must return items that are close but not exact matches."""
    svc.items.create(name="Piazzolla")
    results = svc.items.search("piazola", fuzzy=True)
    names = [i.name for i in results]
    assert "Piazzolla" in names


def test_non_fuzzy_excludes_fuzzy_only_match(svc: TaxomeshService) -> None:
    """fuzzy=False must exclude items that only match via fuzzy scoring."""
    svc.items.create(name="Piazzolla")
    results = svc.items.search("piazola", fuzzy=False)
    names = [i.name for i in results]
    assert "Piazzolla" not in names


def test_empty_query_returns_empty_items(svc: TaxomeshService) -> None:
    """Empty query string must return an empty list for items."""
    svc.items.create(name="Alpha")
    assert svc.items.search("") == ()


def test_whitespace_query_returns_empty_items(svc: TaxomeshService) -> None:
    """Whitespace-only query must return an empty list for items."""
    svc.items.create(name="Alpha")
    assert svc.items.search("   ") == ()


def test_empty_query_returns_empty_categories(svc: TaxomeshService) -> None:
    """Empty query string must return an empty list for categories."""
    svc.categories.create(name="Jazz")
    assert svc.categories.search("") == ()


def test_whitespace_query_returns_empty_categories(svc: TaxomeshService) -> None:
    """Whitespace-only query must return an empty list for categories."""
    svc.categories.create(name="Jazz")
    assert svc.categories.search("   ") == ()


def test_accent_insensitive_item_search(svc: TaxomeshService) -> None:
    """Accent-insensitive normalization must match accented names."""
    svc.items.create(name="Ñoño Café")
    results = svc.items.search("nono cafe", fuzzy=False)
    names = [i.name for i in results]
    assert "Ñoño Café" in names


# ---------------------------------------------------------------------------
# Filtered and recursive searches
# ---------------------------------------------------------------------------


def test_filtered_search_with_category_id_restricts_results(svc: TaxomeshService) -> None:
    """items.search with category_id must return only items in that category."""
    item_a = svc.items.create(name="ItemA Music")
    item_b = svc.items.create(name="ItemB Music")
    cat1 = svc.categories.create(name="Category1")
    cat2 = svc.categories.create(name="Category2")
    svc.items.place_in(item_a.item_id, cat1.category_id)
    svc.items.place_in(item_b.item_id, cat2.category_id)
    results = svc.items.search("music", category=cat1.category_id)
    item_ids = {i.item_id for i in results}
    assert item_a.item_id in item_ids
    assert item_b.item_id not in item_ids


def test_recursive_search_returns_subtree_items(svc: TaxomeshService) -> None:
    """recursive=True must include items in descendant categories."""
    root_cat = svc.categories.create(name="RootCat")
    child_cat = svc.categories.create(name="ChildCat")
    svc.categories.add_parent(child_cat.category_id, root_cat.category_id)
    item = svc.items.create(name="DeepItem")
    svc.items.place_in(item.item_id, child_cat.category_id)
    results = svc.items.search("deepitem", category=root_cat.category_id, recursive=True)
    item_ids = {i.item_id for i in results}
    assert item.item_id in item_ids


def test_filtered_search_uses_live_data_not_corpus(svc: TaxomeshService) -> None:
    """Filtered search (category_id set) must not be affected by the global item corpus."""
    item = svc.items.create(name="CorpusItem")
    cat = svc.categories.create(name="SomeCat")
    svc.items.place_in(item.item_id, cat.category_id)
    # Warm the global corpus
    svc.items.search("corpusitem")
    # Filtered search must still correctly restrict to the category
    results = svc.items.search("corpusitem", category=cat.category_id)
    item_ids = {i.item_id for i in results}
    assert item.item_id in item_ids


# ---------------------------------------------------------------------------
# svc.info exposes corpus sizes
# ---------------------------------------------------------------------------


def test_info_item_corpus_size_is_none_before_search(svc: TaxomeshService) -> None:
    """svc.info must report item_corpus_size=None before any search."""
    svc.items.create(name="Alpha")
    info = svc.info
    assert info.item_corpus_size is None


def test_info_item_corpus_size_after_search(svc: TaxomeshService) -> None:
    """svc.info must report item_corpus_size as a non-negative int after a search."""
    svc.items.create(name="Alpha")
    svc.items.create(name="Beta")
    svc.items.search("alpha")
    info = svc.info
    assert info.item_corpus_size == 2


def test_info_item_corpus_size_resets_after_write(svc: TaxomeshService) -> None:
    """svc.info must report item_corpus_size=None after an item write invalidates the corpus."""
    item = svc.items.create(name="Alpha")
    svc.items.search("alpha")
    assert svc.info.item_corpus_size == 1
    svc.items.delete(item.item_id)
    assert svc.info.item_corpus_size is None


def test_info_category_corpus_size_is_none_before_search(svc: TaxomeshService) -> None:
    """svc.info must report category_corpus_size=None before any category search."""
    svc.categories.create(name="Jazz")
    info = svc.info
    assert info.category_corpus_size is None


def test_info_category_corpus_size_after_search(svc: TaxomeshService) -> None:
    """svc.info must report category_corpus_size as a non-negative int after a search."""
    svc.categories.create(name="Jazz")
    svc.categories.create(name="Blues")
    svc.categories.search("jazz")
    info = svc.info
    assert info.category_corpus_size == 2


def test_info_category_corpus_size_resets_after_write(svc: TaxomeshService) -> None:
    """svc.info must report category_corpus_size=None after a category write."""
    cat = svc.categories.create(name="Jazz")
    svc.categories.search("jazz")
    assert svc.info.category_corpus_size == 1
    svc.categories.delete(cat.category_id)
    assert svc.info.category_corpus_size is None
