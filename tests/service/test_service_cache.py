"""Tests for service-level memoization caching."""

from unittest.mock import MagicMock
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
