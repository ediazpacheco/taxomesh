"""Tests for service-level memoization caching."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

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
