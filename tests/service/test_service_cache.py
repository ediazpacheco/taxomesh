"""Tests for service-level memoization caching."""

import gc
import math
import re
import weakref
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from taxomesh.application.collections.categories import CategoryCollection
from taxomesh.application.service import DEFAULT_CACHE_TTL, TaxomeshService
from taxomesh.domain.info import TaxomeshInfo
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.exceptions import TaxomeshError, TaxomeshValidationError
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.service.conftest import BACKEND_PARAMS, CountedService, CountingRepository, _build_repository


# Any: these calls pass what the annotations refuse, as an untyped caller can.
def untyped(value: object) -> Any:
    """Return ``value`` typed as anything, so a call can pass what its annotation refuses."""
    return value


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
    item = Item(name="Item", external_id="test-item", item_id=item_id)
    tag = Tag(tag_id=tag_id, name="testtag")
    repo.find_category.return_value = cat
    repo.list_categories.return_value = [cat]
    repo.find_item.return_value = item
    repo.list_items.return_value = [item]
    repo.list_tags.return_value = [tag]
    repo.list_category_parent_links.return_value = []
    repo.list_item_parent_links.return_value = []
    repo.config_summary = "mock"
    return repo


class TestServiceCategoriesSubscriptCaching:
    def test_categories_subscript_called_once_when_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        cat_id = repo.find_category.return_value.category_id
        svc.categories[cat_id]
        svc.categories[cat_id]
        repo.find_category.assert_called_once()


class TestServiceCacheInvalidationOnWrite:
    def test_categories_create_invalidates_cache(self) -> None:
        repo = _mock_repo()
        new_cat = Category(category_id=uuid4(), name="NewCat")
        repo.save_category.return_value = None
        repo.find_category.return_value = new_cat
        svc = _make_service(repo)

        cat_id = new_cat.category_id
        repo.find_category.return_value = new_cat
        svc.categories[cat_id]

        svc.categories.create(name="Another")
        svc.categories[cat_id]
        assert repo.find_category.call_count == 2


class TestServiceReadMethodsCaching:
    def test_categories_list_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.categories.list()
        svc.categories.list()
        # One read from _ensure_root at construction, one from the first list(); the second
        # adds none. Asserted through list() rather than roots(), which reaches
        # list_category_parent_links and so could never move this count either way.
        assert repo.list_categories.call_count == 2

    def test_items_subscript_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        item_id = repo.find_item.return_value.item_id
        svc.items[item_id]
        svc.items[item_id]
        repo.find_item.assert_called_once()

    def test_items_list_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.items.list()
        svc.items.list()
        repo.list_items.assert_called_once()

    def test_tags_list_cached(self) -> None:
        repo = _mock_repo()
        svc = _make_service(repo)
        svc.tags.list()
        svc.tags.list()
        repo.list_tags.assert_called_once()


# ---------------------------------------------------------------------------
# Write-invalidation bug fixes: items.relate, items.unrelate
# ---------------------------------------------------------------------------


class TestRelationWriteInvalidation:
    def test_relate_invalidates_cache(self) -> None:
        """items.relate clears the service's cache, so the next read is fresh."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
        repo.list_item_relation_links.return_value = []
        repo.save_item_relation_link.return_value = None
        repo.find_item.return_value = Item(name="Item", external_id="x", item_id=src_id)
        svc = _make_service(repo)

        # Warm cache with empty result
        svc.items.list_relations(src_id)
        assert repo.list_item_relation_links.call_count == 1

        # Write — must invalidate
        repo.list_item_relation_links.return_value = [link]
        svc.items.relate(src_id, tgt_id, "covers")

        # Next read must hit repo again (cache was cleared)
        result = svc.items.list_relations(src_id)
        assert repo.list_item_relation_links.call_count == 2
        assert len(result) == 1

    def test_unrelate_invalidates_cache(self) -> None:
        """items.unrelate clears the service's cache, so the next read is fresh."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
        repo.list_item_relation_links.return_value = [link]
        repo.delete_item_relation_link.return_value = True
        svc = _make_service(repo)

        # Warm cache with one relation
        svc.items.list_relations(src_id)
        assert repo.list_item_relation_links.call_count == 1

        # Write — must invalidate
        repo.list_item_relation_links.return_value = []
        svc.items.unrelate(src_id, tgt_id, "covers")

        # Next read must hit repo again
        result = svc.items.list_relations(src_id)
        assert repo.list_item_relation_links.call_count == 2
        assert len(result) == 0


# ---------------------------------------------------------------------------
# items.get_by_external_id, categories.get_by_external_id
# ---------------------------------------------------------------------------


class TestExternalIdLookupCaching:
    def test_items_get_by_external_id_cached(self) -> None:
        """Second call with same external_id must not hit repo."""
        repo = _mock_repo()
        item = Item(name="Item", external_id="ext-001", item_id=uuid4())
        repo.find_item_by_external_id.return_value = item
        svc = _make_service(repo)

        svc.items.get_by_external_id("ext-001")
        svc.items.get_by_external_id("ext-001")
        repo.find_item_by_external_id.assert_called_once()

    def test_categories_get_by_external_id_cached(self) -> None:
        """Second call with same external_id must not hit repo."""
        repo = _mock_repo()
        cat = Category(category_id=uuid4(), name="Cat", external_id="ext-cat-1")
        repo.find_category_by_external_id.return_value = cat
        repo.find_category.return_value = None  # root not involved
        svc = _make_service(repo)

        svc.categories.get_by_external_id("ext-cat-1")
        svc.categories.get_by_external_id("ext-cat-1")
        repo.find_category_by_external_id.assert_called_once()

    def test_items_get_by_external_id_none_result_cached(self) -> None:
        """None result must also be cached (not re-queried)."""
        repo = _mock_repo()
        repo.find_item_by_external_id.return_value = None
        svc = _make_service(repo)

        result1 = svc.items.get_by_external_id("unknown")
        result2 = svc.items.get_by_external_id("unknown")
        assert result1 is None
        assert result2 is None
        repo.find_item_by_external_id.assert_called_once()

    def test_items_get_by_external_id_cache_expires_after_ttl(self) -> None:
        """Cached result must be re-fetched once the TTL window has elapsed."""
        repo = _mock_repo()
        item = Item(name="Item", external_id="ext-ttl", item_id=uuid4())
        repo.find_item_by_external_id.return_value = item
        svc = _make_service(repo)

        with patch("taxomesh.utils.memoize.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            svc.items.get_by_external_id("ext-ttl")
            assert repo.find_item_by_external_id.call_count == 1

            mock_time.monotonic.return_value = 6.0  # past DEFAULT_CACHE_TTL (5 s)
            svc.items.get_by_external_id("ext-ttl")
            assert repo.find_item_by_external_id.call_count == 2

    def test_different_external_ids_are_independent_cache_entries(self) -> None:
        """Distinct external IDs must each hit the repo once."""
        repo = _mock_repo()
        repo.find_item_by_external_id.return_value = None
        svc = _make_service(repo)

        svc.items.get_by_external_id("id-A")
        svc.items.get_by_external_id("id-B")
        assert repo.find_item_by_external_id.call_count == 2


# ---------------------------------------------------------------------------
# items.list_relations, items.list_related
# ---------------------------------------------------------------------------


class TestItemRelationCaching:
    def test_list_relations_cached(self) -> None:
        """Second call with same args must not hit repo."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        src_id = uuid4()
        link = ItemRelationLink(source_item_id=src_id, target_item_id=uuid4(), relation_type="covers")
        repo.list_item_relation_links.return_value = [link]
        svc = _make_service(repo)

        svc.items.list_relations(src_id)
        svc.items.list_relations(src_id)
        repo.list_item_relation_links.assert_called_once()

    def test_list_relations_direction_independent_cache(self) -> None:
        """Outgoing and incoming are distinct cache entries."""
        repo = _mock_repo()
        src_id = uuid4()
        repo.list_item_relation_links.return_value = []
        svc = _make_service(repo)

        svc.items.list_relations(src_id, direction="outgoing")
        svc.items.list_relations(src_id, direction="incoming")
        assert repo.list_item_relation_links.call_count == 2

    def test_list_related_cached(self) -> None:
        """Second call with same args returns cached list[Item]."""
        repo = _mock_repo()
        src_id = uuid4()
        tgt_id = uuid4()
        repo.list_item_relation_links.return_value = []
        repo.find_item.return_value = Item(name="Item", external_id="t", item_id=tgt_id)
        svc = _make_service(repo)

        svc.items.list_related(src_id)
        svc.items.list_related(src_id)
        repo.list_item_relation_links.assert_called_once()


# ---------------------------------------------------------------------------
# items.get_many_related caching
# ---------------------------------------------------------------------------


def _repo_with_batch_relation(src_id: UUID, tgt_id: UUID) -> MagicMock:
    """Mock repo with one outgoing relation src → tgt for the batch lookup."""
    from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

    repo = _mock_repo()
    link = ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers")
    repo.list_item_relation_links_batch.return_value = [link]
    repo.map_items_by_id.return_value = {
        src_id: Item(name="Item", external_id="src", item_id=src_id),
        tgt_id: Item(name="Item", external_id="tgt", item_id=tgt_id),
    }
    return repo


class TestBatchRelatedItemsCaching:
    def test_identical_calls_hit_repo_once(self) -> None:
        """Two identical batched calls query the repository once."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        first = svc.items.get_many_related([src_id])
        second = svc.items.get_many_related([src_id])
        repo.list_item_relation_links_batch.assert_called_once()
        assert second == first

    def test_cache_expires_after_ttl(self) -> None:
        """Cached result is re-fetched once the TTL window has elapsed."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        with patch("taxomesh.utils.memoize.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            svc.items.get_many_related([src_id])
            assert repo.list_item_relation_links_batch.call_count == 1

            mock_time.monotonic.return_value = 6.0  # past DEFAULT_CACHE_TTL (5 s)
            svc.items.get_many_related([src_id])
            assert repo.list_item_relation_links_batch.call_count == 2

    def test_different_source_ids_are_independent_entries(self) -> None:
        """A different source set queries the repository again."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id])
        svc.items.get_many_related([uuid4()])
        assert repo.list_item_relation_links_batch.call_count == 2

    def test_different_relation_type_filters_are_independent_entries(self) -> None:
        """A different relation-type filter queries the repository again."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id], relation_types=["covers"])
        svc.items.get_many_related([src_id], relation_types=["performs"])
        assert repo.list_item_relation_links_batch.call_count == 2

    def test_empty_source_ids_returns_empty_without_repo_call(self) -> None:
        """Empty input short-circuits before the cache and the repository."""
        repo = _mock_repo()
        svc = _make_service(repo)

        assert svc.items.get_many_related([]) == {}
        repo.list_item_relation_links_batch.assert_not_called()

    def test_relation_type_variants_share_cache_entry(self) -> None:
        """Reordering, duplicates, casing and whitespace share one entry."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id], relation_types=["a", "b"])
        svc.items.get_many_related([src_id], relation_types=["b", "a"])
        svc.items.get_many_related([src_id], relation_types=["B", " a ", "b"])
        repo.list_item_relation_links_batch.assert_called_once()

    def test_source_id_variants_share_cache_entry(self) -> None:
        """Reordered and duplicated source IDs share one entry."""
        src_a, src_b, tgt_id = uuid4(), uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_a, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_a, src_b])
        svc.items.get_many_related([src_b, src_a, src_a])
        repo.list_item_relation_links_batch.assert_called_once()

    def test_none_and_empty_relation_types_share_cache_entry(self) -> None:
        """ "no filter" as None and as an empty collection share one entry."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id], relation_types=None)
        svc.items.get_many_related([src_id], relation_types=[])
        repo.list_item_relation_links_batch.assert_called_once()

    def test_enabled_values_are_distinct_entries(self) -> None:
        """``enabled`` changes which rows come back, so it splits the key."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id], enabled=True)
        svc.items.get_many_related([src_id], enabled=None)
        assert repo.list_item_relation_links_batch.call_count == 2

    def test_clearing_the_cache_forces_a_refetch(self) -> None:
        """Clearing the service's cache re-queries the repository."""
        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        svc = _make_service(repo)

        svc.items.get_many_related([src_id])
        svc._cache.clear()
        svc.items.get_many_related([src_id])
        assert repo.list_item_relation_links_batch.call_count == 2

    def test_direction_variants_are_independent_entries(self) -> None:
        """056 — outgoing/incoming/both are distinct cache keys (one unified query each)."""
        a, b = uuid4(), uuid4()
        repo = _repo_with_batch_relation(a, b)
        svc = _make_service(repo)

        svc.items.get_many_related([a], direction="outgoing")
        svc.items.get_many_related([a], direction="incoming")
        svc.items.get_many_related([a], direction="both")
        # Three distinct directions → three distinct cache entries → three queries.
        assert repo.list_item_relation_links_batch.call_count == 3

    def test_incoming_identical_calls_hit_repo_once(self) -> None:
        """056 — two identical incoming calls query the repository once."""
        a, b = uuid4(), uuid4()
        repo = _repo_with_batch_relation(a, b)
        svc = _make_service(repo)

        svc.items.get_many_related([b], direction="incoming")
        svc.items.get_many_related([b], direction="incoming")
        repo.list_item_relation_links_batch.assert_called_once()

    def test_write_invalidates_batch_cache(self) -> None:
        """A write between identical calls invalidates the cached entry."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        src_id, tgt_id = uuid4(), uuid4()
        repo = _repo_with_batch_relation(src_id, tgt_id)
        repo.find_item.return_value = Item(name="Item", external_id="src", item_id=src_id)
        svc = _make_service(repo)

        first = svc.items.get_many_related([src_id])
        assert set(first[src_id].relation_types) == {"covers"}

        new_tgt = uuid4()
        repo.list_item_relation_links_batch.return_value = [
            ItemRelationLink(source_item_id=src_id, target_item_id=tgt_id, relation_type="covers"),
            ItemRelationLink(source_item_id=src_id, target_item_id=new_tgt, relation_type="performs"),
        ]
        repo.map_items_by_id.return_value = {
            src_id: Item(name="Item", external_id="src", item_id=src_id),
            tgt_id: Item(name="Item", external_id="tgt", item_id=tgt_id),
            new_tgt: Item(name="Item", external_id="new-tgt", item_id=new_tgt),
        }
        svc.items.relate(src_id, new_tgt, "performs")

        second = svc.items.get_many_related([src_id])
        assert repo.list_item_relation_links_batch.call_count == 2
        assert set(second[src_id].relation_types) == {"covers", "performs"}

    def test_raised_error_is_not_cached(self) -> None:
        """A storage error leaves no cache entry behind, so the next call reads again."""
        from taxomesh.exceptions import TaxomeshRepositoryError  # noqa: PLC0415

        repo = _mock_repo()
        repo.list_item_relation_links_batch.side_effect = TaxomeshRepositoryError("storage down")
        svc = _make_service(repo)
        src_id = uuid4()

        with pytest.raises(TaxomeshRepositoryError):
            svc.items.get_many_related([src_id])
        with pytest.raises(TaxomeshRepositoryError):
            svc.items.get_many_related([src_id])
        assert repo.list_item_relation_links_batch.call_count == 2


# ---------------------------------------------------------------------------
# Bulk target resolution in
# items.list_related: one map_items_by_id call instead of N items[...] calls
# ---------------------------------------------------------------------------


class TestListRelatedBulkResolution:
    def _repo_with_links(self, src_id: UUID, tgt_ids: list[UUID]) -> MagicMock:
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        repo = _mock_repo()
        repo.list_item_relation_links.return_value = [
            ItemRelationLink(source_item_id=src_id, target_item_id=tgt, relation_type="covers") for tgt in tgt_ids
        ]
        repo.map_items_by_id.return_value = {
            tgt: Item(name="Item", external_id=f"t{i}", item_id=tgt) for i, tgt in enumerate(tgt_ids)
        }
        return repo

    def test_cold_cache_uses_single_bulk_lookup(self) -> None:
        """Targets resolve via one map_items_by_id call, never items[...]."""
        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        svc = _make_service(repo)

        svc.items.list_related(src_id)
        repo.map_items_by_id.assert_called_once_with({*tgt_ids, src_id}, enabled=None)
        repo.find_item.assert_not_called()

    def test_link_order_is_preserved(self) -> None:
        """The result is in link order, not in the order of the batch dict."""
        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        svc = _make_service(repo)

        result = svc.items.list_related(src_id)
        assert [item.item_id for item in result] == tgt_ids

    def test_missing_target_is_skipped(self) -> None:
        """A target no stored item carries is left out of the answer, which the rest keeps."""
        src_id = uuid4()
        tgt_ids = [uuid4(), uuid4()]
        repo = self._repo_with_links(src_id, tgt_ids)
        del repo.map_items_by_id.return_value[tgt_ids[1]]
        svc = _make_service(repo)

        assert [item.item_id for item in svc.items.list_related(src_id)] == [tgt_ids[0]]

    def test_incoming_direction_resolves_sources_in_bulk(self) -> None:
        """Direction="incoming" bulk-resolves source items the same way."""
        from taxomesh.domain.models import ItemRelationLink  # noqa: PLC0415

        tgt_id = uuid4()
        src_ids = [uuid4(), uuid4()]
        repo = _mock_repo()
        repo.list_item_relation_links.return_value = [
            ItemRelationLink(source_item_id=src, target_item_id=tgt_id, relation_type="covers") for src in src_ids
        ]
        repo.map_items_by_id.return_value = {
            src: Item(name="Item", external_id=f"s{i}", item_id=src) for i, src in enumerate(src_ids)
        }
        svc = _make_service(repo)

        result = svc.items.list_related(tgt_id, direction="incoming")
        repo.map_items_by_id.assert_called_once_with({*src_ids, tgt_id}, enabled=None)
        repo.find_item.assert_not_called()
        assert [item.item_id for item in result] == src_ids

    def test_no_links_returns_empty_without_bulk_lookup(self) -> None:
        """Zero links short-circuits before the bulk item query."""
        repo = _mock_repo()
        repo.list_item_relation_links.return_value = []
        svc = _make_service(repo)

        assert svc.items.list_related(uuid4()) == ()
        repo.map_items_by_id.assert_not_called()


class TestPlacementReadCaching:
    """Batching the placement reads must not change their cache behaviour.

    Results stay cached for the TTL and stay invalidated on write. These
    run against a real in-memory backend rather than a mock, because what is being
    checked is that the rewritten call path still sits behind the memoize decorator.
    """

    @staticmethod
    def _service_with_one_placement() -> tuple[TaxomeshService, UUID, UUID]:
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        service = TaxomeshService(repository=InMemoryRepository())
        category = service.categories.create("Cached")
        item = service.items.create(name="Cached Item")
        service.items.place_in(item.item_id, category.category_id)
        service._cache.clear()
        return service, category.category_id, item.item_id

    def test_items_list_by_category_is_served_from_cache_on_repeat(self) -> None:
        service, category_id, _ = self._service_with_one_placement()

        first = service.items.list(category=category_id)
        with patch.object(service.repository, "list_item_parent_links") as spy:
            second = service.items.list(category=category_id)

        assert spy.call_count == 0, "the second call reached storage — memoization was lost"
        assert [item.item_id for item in first] == [item.item_id for item in second]

    def test_items_list_by_category_is_invalidated_by_a_write(self) -> None:
        service, category_id, _ = self._service_with_one_placement()
        assert len(service.items.list(category=category_id)) == 1

        added = service.items.create(name="Added Later")
        service.items.place_in(added.item_id, category_id, sort_index=1)

        assert len(service.items.list(category=category_id)) == 2, "a write did not invalidate the cache"

    def test_items_list_by_category_reflects_a_removal(self) -> None:
        service, category_id, item_id = self._service_with_one_placement()
        assert len(service.items.list(category=category_id)) == 1

        service.items.remove_from(item_id, category_id)

        assert service.items.list(category=category_id) == ()

    def test_categories_list_by_parent_is_served_from_cache_on_repeat(self) -> None:
        """For the children path."""
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        service = TaxomeshService(repository=InMemoryRepository())
        parent = service.categories.create("Cached Parent")
        child = service.categories.create("Cached Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        service._cache.clear()

        first = service.categories.list(parent=parent.category_id)
        with patch.object(service.repository, "list_category_parent_links") as spy:
            second = service.categories.list(parent=parent.category_id)

        assert spy.call_count == 0
        assert [c.category_id for c in first] == [c.category_id for c in second]

    def test_categories_list_by_parent_is_invalidated_by_a_write(self) -> None:
        from tests.service.conftest import InMemoryRepository  # noqa: PLC0415

        service = TaxomeshService(repository=InMemoryRepository())
        parent = service.categories.create("Cached Parent")
        child = service.categories.create("Cached Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        service._cache.clear()
        assert len(service.categories.list(parent=parent.category_id)) == 1

        added = service.categories.create("Added Later")
        service.categories.add_parent(added.category_id, parent.category_id, sort_index=1)

        assert len(service.categories.list(parent=parent.category_id)) == 2


# ---------------------------------------------------------------------------
# The cache belongs to one service
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Stored:
    """The rows every read form below is asked about."""

    category: Category
    item: Item
    related: Item
    tag: Tag


def _store(service: TaxomeshService) -> _Stored:
    """Store one row of each kind every read form needs, with the links between them."""
    category = service.categories.create("Music", slug="music", external_id="cat-ext")
    item = service.items.create("Tango", slug="tango", external_id="item-ext")
    related = service.items.create("Milonga")
    tag = service.tags.create("classic")
    service.items.place_in(item, category)
    service.items.tag(item, tag)
    service.items.relate(item, related, "cover")
    return _Stored(category=category, item=item, related=related, tag=tag)


type _Read = Callable[[TaxomeshService, _Stored], object]

# One form for each memoized read the service offers, and one for each search, whose corpus is
# held for the same lifetime.
_READ_FORMS: Final[Mapping[str, _Read]] = {
    "categories[key]": lambda svc, stored: svc.categories[stored.category],
    "categories.get_many": lambda svc, stored: svc.categories.get_many(stored.category),
    "categories.list": lambda svc, stored: svc.categories.list(),
    "categories.roots": lambda svc, stored: svc.categories.roots(),
    "categories.get_by_slug": lambda svc, stored: svc.categories.get_by_slug("music"),
    "categories.get_by_external_id": lambda svc, stored: svc.categories.get_by_external_id("cat-ext"),
    "categories.get_many_by_external_id": lambda svc, stored: svc.categories.get_many_by_external_id(["cat-ext"]),
    "categories.search": lambda svc, stored: svc.categories.search("music"),
    "items[key]": lambda svc, stored: svc.items[stored.item],
    "items.get_many": lambda svc, stored: svc.items.get_many(stored.item),
    "items.list": lambda svc, stored: svc.items.list(),
    "items.get_by_slug": lambda svc, stored: svc.items.get_by_slug("tango"),
    "items.get_by_external_id": lambda svc, stored: svc.items.get_by_external_id("item-ext"),
    "items.get_many_by_external_id": lambda svc, stored: svc.items.get_many_by_external_id(["item-ext"]),
    "items.list_relations": lambda svc, stored: svc.items.list_relations(stored.item),
    "items.list_related": lambda svc, stored: svc.items.list_related(stored.item),
    "items.get_many_related": lambda svc, stored: svc.items.get_many_related([stored.item]),
    "items.search": lambda svc, stored: svc.items.search("tango"),
    "tags.get_many": lambda svc, stored: svc.tags.get_many(stored.tag),
    "tags.list": lambda svc, stored: svc.tags.list(),
    "graph": lambda svc, stored: svc.graph(),
}

# Each entity's search, and the size its corpus reports through ``info``.
_CORPORA: Final[Mapping[str, tuple[_Read, Callable[[TaxomeshInfo], int | None]]]] = {
    "items": (_READ_FORMS["items.search"], lambda info: info.item_corpus_size),
    "categories": (_READ_FORMS["categories.search"], lambda info: info.category_corpus_size),
}

# The batch lookups, each answering a new dict.
_BATCH_LOOKUPS: Final[tuple[str, ...]] = ("categories.get_many", "items.get_many", "tags.get_many")


@pytest.fixture(params=BACKEND_PARAMS)
def repository(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshRepositoryBase:
    """Return a fresh repository for each backend, for a test that builds its own services."""
    return _build_repository(request, tmp_path)


class TestNoLifetime:
    """With ``cache_ttl=0`` every read reaches storage."""

    @pytest.mark.parametrize("form", _READ_FORMS)
    def test_a_repeated_read_costs_its_reads_again(self, counting_service: CountedService, form: str) -> None:
        stored = _store(counting_service.service)
        uncached = TaxomeshService(repository=counting_service.reads, cache_ttl=0)
        read = _READ_FORMS[form]

        counting_service.reads.reset()
        read(uncached, stored)
        first = counting_service.reads.total
        counting_service.reads.reset()
        read(uncached, stored)

        assert first > 0
        assert counting_service.reads.total == first

    def test_no_corpus_is_held(self, counting_service: CountedService) -> None:
        _store(counting_service.service)
        uncached = TaxomeshService(repository=counting_service.reads, cache_ttl=0)

        uncached.items.search("tango")
        uncached.categories.search("music")

        assert uncached.info.item_corpus_size is None
        assert uncached.info.category_corpus_size is None


class TestDefaultLifetime:
    """At the default lifetime a repeated read is served from the service's cache."""

    @pytest.mark.parametrize("form", _READ_FORMS)
    def test_a_repeated_read_costs_nothing(self, counting_service: CountedService, form: str) -> None:
        stored = _store(counting_service.service)
        read = _READ_FORMS[form]
        counting_service.cold()
        read(counting_service.service, stored)

        counting_service.reads.reset()
        read(counting_service.service, stored)

        assert counting_service.reads.total == 0

    @pytest.mark.parametrize("entity", _CORPORA)
    def test_a_corpus_past_its_lifetime_is_built_again(self, counting_service: CountedService, entity: str) -> None:
        svc = counting_service.service
        stored = _store(svc)
        search, size_of = _CORPORA[entity]
        with patch("taxomesh.utils.memoize.time") as clock:
            clock.monotonic.return_value = 100.0
            counting_service.cold()
            search(svc, stored)
            held = size_of(svc.info)

            clock.monotonic.return_value = 100.0 + DEFAULT_CACHE_TTL + 1
            expired = size_of(svc.info)
            counting_service.reads.reset()
            search(svc, stored)

        assert held is not None
        assert expired is None
        assert counting_service.reads.total > 0

    @pytest.mark.parametrize("entity", _CORPORA)
    def test_cold_drops_the_corpus_too(self, counting_service: CountedService, entity: str) -> None:
        """``cold()`` is where every read count starts, so the search after it reads storage."""
        svc = counting_service.service
        stored = _store(svc)
        search, size_of = _CORPORA[entity]
        search(svc, stored)

        counting_service.cold()

        assert size_of(svc.info) is None
        search(svc, stored)
        assert counting_service.reads.total > 0

    @pytest.mark.parametrize("form", _BATCH_LOOKUPS)
    def test_a_batch_lookup_hands_back_a_new_dict_each_call(self, service: TaxomeshService, form: str) -> None:
        """The cached answer is copied out, so a caller changing one answer leaves the next whole."""
        stored = _store(service)
        read = _READ_FORMS[form]
        first = read(service, stored)
        assert isinstance(first, dict)

        first.clear()

        assert read(service, stored)

    def test_lookups_past_the_lifetime_drop_the_expired_entries(self, service: TaxomeshService) -> None:
        """Lookups over an open key space, such as slugs taken from URLs, hold one lifetime of keys.

        An entry is dropped when its member stores the next one after it expired, so a long-lived
        service asked about ever new keys holds the keys of the last ``cache_ttl``, not every key.
        """
        with patch("taxomesh.utils.memoize.time") as clock:
            clock.monotonic.return_value = 100.0
            for n in range(50):
                service.categories.get_by_slug(f"early-{n}")
            clock.monotonic.return_value = 100.0 + DEFAULT_CACHE_TTL + 1
            for n in range(50):
                service.categories.get_by_slug(f"late-{n}")

        assert len(service._cache.entries(CategoryCollection._by_slug)) == 50


class TestConstruction:
    """Building a service reads every category once, to find the root.

    The root is found by its reserved name, and the port has no lookup by name, so the read is the
    price of the one top level. It is paid once per service, which is why a service is built once
    and shared rather than built per request.
    """

    def test_building_a_service_reads_the_categories_once(self, repository: TaxomeshRepositoryBase) -> None:
        counter = CountingRepository(repository)

        first = TaxomeshService(repository=counter)

        assert counter.calls == ["list_categories"]
        for name in ("Music", "Jazz"):
            first.categories.create(name)
        counter.reset()

        TaxomeshService(repository=counter)

        assert counter.calls == ["list_categories"]


class TestOneServicesCache:
    """A write clears the cache of the service it went through, and no other."""

    def test_a_write_through_another_service_leaves_this_cache_as_it_was(
        self, counting_service: CountedService
    ) -> None:
        reader = counting_service.service
        writer = TaxomeshService(repository=counting_service.reads)
        category = reader.categories.create("Before")
        counting_service.cold()
        assert reader.categories[category].name == "Before"

        writer.categories.update(category, name="After")
        counting_service.reads.reset()

        assert reader.categories[category].name == "Before"
        assert counting_service.reads.total == 0
        assert writer.categories[category].name == "After"

    def test_a_service_no_longer_referenced_is_collected_with_its_entries(
        self, repository: TaxomeshRepositoryBase
    ) -> None:
        svc = TaxomeshService(repository=repository)
        _READ_FORMS["graph"](svc, _store(svc))
        svc.categories.list()
        collected = weakref.ref(svc)

        del svc
        gc.collect()

        assert collected() is None

    @pytest.mark.parametrize("lifetime", [-1, -0.5, math.nan])
    def test_a_lifetime_below_zero_is_refused_before_storage_is_touched(
        self, lifetime: float, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(TaxomeshValidationError, match=re.escape(f"cache_ttl must be ≥ 0, got {lifetime!r}")):
            TaxomeshService(cache_ttl=lifetime)

        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("lifetime", ["5", None, [1]], ids=["str", "None", "list"])
    def test_a_lifetime_that_is_no_number_is_a_type_error_naming_it(
        self, lifetime: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(TypeError) as caught:
            TaxomeshService(cache_ttl=untyped(lifetime))

        assert str(caught.value).startswith("cache_ttl ")
        assert not isinstance(caught.value, TaxomeshError)
        assert list(tmp_path.iterdir()) == []

    def test_a_lifetime_of_true_is_one_second(self, repository: TaxomeshRepositoryBase) -> None:
        """``True`` is the integer 1, as ``limit=True`` and ``expected_version=True`` are."""
        assert TaxomeshService(repository=repository, cache_ttl=True).categories.list() == ()
