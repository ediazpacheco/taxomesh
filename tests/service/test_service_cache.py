"""Tests for service-level memoization caching."""

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.utils.memoize import clear_all_caches


def _make_service(repo: MagicMock) -> TaxomeshService:
    """Build a TaxomeshService with a mock repository."""
    return TaxomeshService(repository=repo)


def _mock_repo() -> MagicMock:
    """Create a mock repository with common return values."""
    repo = MagicMock()
    cat_id = uuid4()
    item_id = uuid4()
    tag_id = uuid4()
    cat = Category(category_id=cat_id, name="TestCat")
    item = Item(external_id="test-item", item_id=item_id)
    tag = Tag(tag_id=tag_id, name="testtag")
    repo.get_category.return_value = cat
    repo.list_categories.return_value = [cat]
    repo.get_item.return_value = item
    repo.list_items.return_value = [item]
    repo.list_tags.return_value = [tag]
    repo.list_category_parent_links.return_value = []
    repo.list_item_parent_links.return_value = []
    repo.get_config_summary.return_value = "mock"
    return repo


class TestServiceGetCategoryCaching:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_get_category_called_once_when_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        cat_id = repo.get_category.return_value.category_id
        svc.get_category(cat_id)
        svc.get_category(cat_id)
        repo.get_category.assert_called_once()


class TestServiceCacheInvalidationOnWrite:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_create_category_invalidates_cache(self) -> None:
        repo = _mock_repo()
        new_cat = Category(category_id=uuid4(), name="NewCat")
        repo.save_category.return_value = None
        repo.get_category.return_value = new_cat
        svc = _make_service(repo)

        cat_id = new_cat.category_id
        repo.get_category.return_value = new_cat
        svc.get_category(cat_id)

        svc.create_category(name="Another")
        svc.get_category(cat_id)
        assert repo.get_category.call_count == 2


class TestServiceReadMethodsCaching:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_list_categories_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.list_categories()
        svc.list_categories()
        repo.list_categories.assert_called_once()

    def test_get_item_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        item_id = repo.get_item.return_value.item_id
        svc.get_item(item_id)
        svc.get_item(item_id)
        repo.get_item.assert_called_once()

    def test_list_items_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.list_items()
        svc.list_items()
        repo.list_items.assert_called_once()

    def test_list_tags_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.list_tags()
        svc.list_tags()
        repo.list_tags.assert_called_once()


# ---------------------------------------------------------------------------
# T003 / T004 — write-invalidation bug fixes: relate_items, remove_item_relation
# ---------------------------------------------------------------------------


class TestRelationWriteInvalidation:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_relate_items_invalidates_cache(self) -> None:
        """relate_items must call clear_all_caches so subsequent reads are fresh."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
        repo.list_item_relation_links.return_value = []
        repo.save_item_relation_link.return_value = None
        repo.get_item.return_value = Item(external_id="x", item_id=src_id)
        svc = _make_service(repo)

        # Warm cache with empty result
        svc.list_item_relations(src_id)
        assert repo.list_item_relation_links.call_count == 1

        # Write — must invalidate
        repo.list_item_relation_links.return_value = [link]
        svc.relate_items(src_id, tgt_id, "covers")

        # Next read must hit repo again (cache was cleared)
        result = svc.list_item_relations(src_id)
        assert repo.list_item_relation_links.call_count == 2
        assert len(result) == 1

    def test_remove_item_relation_invalidates_cache(self) -> None:
        """remove_item_relation must call clear_all_caches so subsequent reads are fresh."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
        repo.list_item_relation_links.return_value = [link]
        repo.delete_item_relation_link.return_value = True
        svc = _make_service(repo)

        # Warm cache with one relation
        svc.list_item_relations(src_id)
        assert repo.list_item_relation_links.call_count == 1

        # Write — must invalidate
        repo.list_item_relation_links.return_value = []
        svc.remove_item_relation(src_id, tgt_id, "covers")

        # Next read must hit repo again
        result = svc.list_item_relations(src_id)
        assert repo.list_item_relation_links.call_count == 2
        assert len(result) == 0


# ---------------------------------------------------------------------------
# T005 / T006 / T007 — US1: get_item_by_external_id, get_category_by_external_id (spec 041)
# ---------------------------------------------------------------------------


class TestExternalIdLookupCaching:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_get_item_by_external_id_cached(self) -> None:
        """T005 — second call with same external_id must not hit repo."""
        repo = _mock_repo()
        item = Item(external_id="ext-001", item_id=uuid4())
        repo.get_item_by_external_id.return_value = item
        svc = _make_service(repo)

        svc.get_item_by_external_id("ext-001")
        svc.get_item_by_external_id("ext-001")
        repo.get_item_by_external_id.assert_called_once()

    def test_get_category_by_external_id_cached(self) -> None:
        """T006 — second call with same external_id must not hit repo."""
        repo = _mock_repo()
        cat = Category(category_id=uuid4(), name="Cat", external_id="ext-cat-1")
        repo.get_category_by_external_id.return_value = cat
        repo.get_category.return_value = None  # root not involved
        svc = _make_service(repo)

        svc.get_category_by_external_id("ext-cat-1")
        svc.get_category_by_external_id("ext-cat-1")
        repo.get_category_by_external_id.assert_called_once()

    def test_get_item_by_external_id_none_result_cached(self) -> None:
        """T007 — None result must also be cached (not re-queried)."""
        repo = _mock_repo()
        repo.get_item_by_external_id.return_value = None
        svc = _make_service(repo)

        result1 = svc.get_item_by_external_id("unknown")
        result2 = svc.get_item_by_external_id("unknown")
        assert result1 is None
        assert result2 is None
        repo.get_item_by_external_id.assert_called_once()

    def test_get_item_by_external_id_cache_expires_after_ttl(self) -> None:
        """FR-007 — cached result must be re-fetched once the TTL window has elapsed."""
        repo = _mock_repo()
        item = Item(external_id="ext-ttl", item_id=uuid4())
        repo.get_item_by_external_id.return_value = item
        svc = _make_service(repo)

        with patch("taxomesh.utils.memoize.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            svc.get_item_by_external_id("ext-ttl")
            assert repo.get_item_by_external_id.call_count == 1

            mock_time.monotonic.return_value = 6.0  # past DEFAULT_CACHE_TTL (5 s)
            svc.get_item_by_external_id("ext-ttl")
            assert repo.get_item_by_external_id.call_count == 2

    def test_different_external_ids_are_independent_cache_entries(self) -> None:
        """Distinct external IDs must each hit the repo once."""
        repo = _mock_repo()
        repo.get_item_by_external_id.return_value = None
        svc = _make_service(repo)

        svc.get_item_by_external_id("id-A")
        svc.get_item_by_external_id("id-B")
        assert repo.get_item_by_external_id.call_count == 2


# ---------------------------------------------------------------------------
# T010 / T011 / T012 — US2: list_item_relations, list_related_items
# ---------------------------------------------------------------------------


class TestItemRelationCaching:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_list_item_relations_cached(self) -> None:
        """T010 — second call with same args must not hit repo."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=uuid4(), relation_type="covers")
        repo.list_item_relation_links.return_value = [link]
        svc = _make_service(repo)

        svc.list_item_relations(src_id)
        svc.list_item_relations(src_id)
        repo.list_item_relation_links.assert_called_once()

    def test_list_item_relations_direction_independent_cache(self) -> None:
        """T011 — outgoing and incoming are distinct cache entries."""
        repo = _mock_repo()
        src_id = uuid4()
        repo.list_item_relation_links.return_value = []
        svc = _make_service(repo)

        svc.list_item_relations(src_id, direction="outgoing")
        svc.list_item_relations(src_id, direction="incoming")
        assert repo.list_item_relation_links.call_count == 2

    def test_list_related_items_cached(self) -> None:
        """T012 — second call with same args returns cached list[Item]."""
        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        repo.list_item_relation_links.return_value = []
        repo.get_item.return_value = Item(external_id="t", item_id=tgt_id)
        svc = _make_service(repo)

        svc.list_related_items(src_id)
        svc.list_related_items(src_id)
        repo.list_item_relation_links.assert_called_once()


# ---------------------------------------------------------------------------
# 055-memoize-batch-related — list_related_items_for_sources caching
# ---------------------------------------------------------------------------


def _repo_with_batch_relation(src_id: UUID, tgt_id: UUID) -> MagicMock:
    """Mock repo with one outgoing relation src → tgt for the batch lookup."""
    from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

    repo = _mock_repo()
    link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
    repo.list_item_relation_links_for_items.return_value = [link]
    repo.get_items_by_ids.return_value = {
        src_id: Item(external_id="src", item_id=src_id),
        tgt_id: Item(external_id="tgt", item_id=tgt_id),
    }
    return repo


class TestBatchRelatedItemsCaching:
    def setup_method(self) -> None:
        clear_all_caches()

    def test_identical_calls_hit_repo_once(self) -> None:
        """US1 — two identical batched calls query the repository once."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        first = svc.list_related_items_for_sources([src_id])
        second = svc.list_related_items_for_sources([src_id])
        repo.list_item_relation_links_for_items.assert_called_once()
        assert second == first

    def test_cache_expires_after_ttl(self) -> None:
        """US1 — cached result is re-fetched once the TTL window has elapsed."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        with patch("taxomesh.utils.memoize.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            svc.list_related_items_for_sources([src_id])
            assert repo.list_item_relation_links_for_items.call_count == 1

            mock_time.monotonic.return_value = 6.0  # past DEFAULT_CACHE_TTL (5 s)
            svc.list_related_items_for_sources([src_id])
            assert repo.list_item_relation_links_for_items.call_count == 2

    def test_different_source_ids_are_independent_entries(self) -> None:
        """US1 — a different source set queries the repository again."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id])
        svc.list_related_items_for_sources([uuid4()])
        assert repo.list_item_relation_links_for_items.call_count == 2

    def test_different_relation_type_filters_are_independent_entries(self) -> None:
        """US1 — a different relation-type filter queries the repository again."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id], relation_types=["covers"])
        svc.list_related_items_for_sources([src_id], relation_types=["performs"])
        assert repo.list_item_relation_links_for_items.call_count == 2

    def test_empty_source_ids_returns_empty_without_repo_call(self) -> None:
        """US1 — empty input short-circuits before the cache and the repository."""
        repo = _mock_repo()
        svc = _make_service(repo)

        assert svc.list_related_items_for_sources([]) == {}
        repo.list_item_relation_links_for_items.assert_not_called()

    def test_relation_type_variants_share_cache_entry(self) -> None:
        """US2 — reordering, duplicates, casing and whitespace share one entry."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id], relation_types=["a", "b"])
        svc.list_related_items_for_sources([src_id], relation_types=["b", "a"])
        svc.list_related_items_for_sources([src_id], relation_types=["B", " a ", "b"])
        repo.list_item_relation_links_for_items.assert_called_once()

    def test_source_id_variants_share_cache_entry(self) -> None:
        """US2 — reordered and duplicated source IDs share one entry."""
        src_a, src_b, tgt_id = uuid4(), uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_a, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_a, src_b])
        svc.list_related_items_for_sources([src_b, src_a, src_a])
        repo.list_item_relation_links_for_items.assert_called_once()

    def test_none_and_empty_relation_types_share_cache_entry(self) -> None:
        """US2 — "no filter" as None and as an empty collection share one entry."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id], relation_types=None)
        svc.list_related_items_for_sources([src_id], relation_types=[])
        repo.list_item_relation_links_for_items.assert_called_once()

    def test_skip_on_error_values_are_distinct_entries(self) -> None:
        """US2/FR-003 — skip_on_error changes behaviour, so it splits the key."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id], skip_on_error=True)
        svc.list_related_items_for_sources([src_id], skip_on_error=False)
        assert repo.list_item_relation_links_for_items.call_count == 2

    def test_clear_all_caches_forces_refetch(self) -> None:
        """US3 — explicit cache clearing re-queries the repository."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([src_id])
        clear_all_caches()
        svc.list_related_items_for_sources([src_id])
        assert repo.list_item_relation_links_for_items.call_count == 2

    def test_direction_variants_are_independent_entries(self) -> None:
        """056 — outgoing/incoming/both are distinct cache keys (one unified query each)."""
        a, b = uuid4(), uuid4()
        repo = _repo_with_batch_relation(a, b)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([a], direction="outgoing")
        svc.list_related_items_for_sources([a], direction="incoming")
        svc.list_related_items_for_sources([a], direction="both")
        # Three distinct directions → three distinct cache entries → three queries.
        assert repo.list_item_relation_links_for_items.call_count == 3

    def test_incoming_identical_calls_hit_repo_once(self) -> None:
        """056 — two identical incoming calls query the repository once."""
        a, b = uuid4(), uuid4()
        repo = _repo_with_batch_relation(a, b)
        svc = _make_service(repo)

        svc.list_related_items_for_sources([b], direction="incoming")
        svc.list_related_items_for_sources([b], direction="incoming")
        repo.list_item_relation_links_for_items.assert_called_once()

    def test_write_invalidates_batch_cache(self) -> None:
        """US3 — a write between identical calls invalidates the cached entry."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        repo.get_item.return_value = Item(external_id="src", item_id=src_id)
        svc = _make_service(repo)

        first = svc.list_related_items_for_sources([src_id])
        assert set(first[src_id]) == {"covers"}

        new_tgt = uuid4()
        repo.list_item_relation_links_for_items.return_value = [
            ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers"),
            ItemRelationLink(source_item_id=src_id, target_item_id=new_tgt, relation_type="performs"),
        ]
        repo.get_items_by_ids.return_value = {
            src_id: Item(external_id="src", item_id=src_id),
            tgt_id: Item(external_id="tgt", item_id=tgt_id),
            new_tgt: Item(external_id="new-tgt", item_id=new_tgt),
        }
        svc.relate_items(src_id, new_tgt, "performs")

        second = svc.list_related_items_for_sources([src_id])
        assert repo.list_item_relation_links_for_items.call_count == 2
        assert set(second[src_id]) == {"covers", "performs"}

    def test_raised_error_is_not_cached(self) -> None:
        """US3 — a TaxomeshItemNotFoundError leaves no cache entry behind."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415
        from taxomesh.exceptions import TaxomeshItemNotFoundError  # noqa: PLC0415

        src_id, tgt_id = uuid4(), uuid4()
        repo = _mock_repo()
        repo.list_item_relation_links_for_items.return_value = [
            ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
        ]
        repo.get_items_by_ids.return_value = {src_id: Item(external_id="src", item_id=src_id)}  # tgt dangling
        svc = _make_service(repo)

        with pytest.raises(TaxomeshItemNotFoundError):
            svc.list_related_items_for_sources([src_id], skip_on_error=False)
        with pytest.raises(TaxomeshItemNotFoundError):
            svc.list_related_items_for_sources([src_id], skip_on_error=False)
        assert repo.list_item_relation_links_for_items.call_count == 2


# ---------------------------------------------------------------------------
# 055-memoize-batch-related (FR-009) — bulk target resolution in
# list_related_items: one get_items_by_ids call instead of N get_item calls
# ---------------------------------------------------------------------------


class TestListRelatedItemsBulkResolution:
    def setup_method(self) -> None:
        clear_all_caches()

    def _repo_with_links(self, src_id: UUID, tgt_ids: list[UUID]) -> MagicMock:
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        repo.list_item_relation_links.return_value = [
            ItemRelationLink(source_item_id=src_id, target_item_id=tgt, relation_type="covers") for tgt in tgt_ids
        ]
        repo.get_items_by_ids.return_value = {
            tgt: Item(external_id=f"t{i}", item_id=tgt) for i, tgt in enumerate(tgt_ids)
        }
        return repo

    def test_cold_cache_uses_single_bulk_lookup(self) -> None:
        """FR-009 — targets resolve via one get_items_by_ids call, never get_item."""
        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        svc = _make_service(repo)

        svc.list_related_items(src_id)
        repo.get_items_by_ids.assert_called_once_with(set(tgt_ids), enabled=None)
        repo.get_item.assert_not_called()

    def test_link_order_is_preserved(self) -> None:
        """FR-009 — result order follows link order, not the bulk dict's order."""
        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        svc = _make_service(repo)

        result = svc.list_related_items(src_id)
        assert [item.item_id for item in result] == tgt_ids

    def test_missing_target_raises_item_not_found(self) -> None:
        """FR-009 — a dangling target raises with the same message as get_item."""
        from taxomesh.exceptions import TaxomeshItemNotFoundError  # noqa: PLC0415

        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        missing = tgt_ids[1]
        del repo.get_items_by_ids.return_value[missing]
        svc = _make_service(repo)

        with pytest.raises(TaxomeshItemNotFoundError, match=f"Item not found: {missing}"):
            svc.list_related_items(src_id)

    def test_incoming_direction_resolves_sources_in_bulk(self) -> None:
        """FR-009 — direction="incoming" bulk-resolves source items the same way."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        tgt_id = uuid4()
        src_ids = [uuid4(), uuid4()]
        repo = _mock_repo()
        repo.list_item_relation_links.return_value = [
            ItemRelationLink(source_item_id=src, target_item_id=tgt_id, relation_type="covers") for src in src_ids
        ]
        repo.get_items_by_ids.return_value = {
            src: Item(external_id=f"s{i}", item_id=src) for i, src in enumerate(src_ids)
        }
        svc = _make_service(repo)

        result = svc.list_related_items(tgt_id, direction="incoming")
        repo.get_items_by_ids.assert_called_once_with(set(src_ids), enabled=None)
        repo.get_item.assert_not_called()
        assert [item.item_id for item in result] == src_ids

    def test_no_links_returns_empty_without_bulk_lookup(self) -> None:
        """FR-009 — zero links short-circuits before the bulk item query."""
        repo = _mock_repo()
        repo.list_item_relation_links.return_value = []
        svc = _make_service(repo)

        assert svc.list_related_items(uuid4()) == []
        repo.get_items_by_ids.assert_not_called()
