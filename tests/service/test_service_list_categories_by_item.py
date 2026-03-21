"""Tests for TaxomeshService.list_categories_by_item."""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshItemNotFoundError
from taxomesh.utils.memoize import clear_all_caches


def test_single_category_returned_us1(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat = service.create_category(name="Jazz")
    service.place_item_in_category(item.item_id, cat.category_id)

    result = service.list_categories_by_item(item.item_id)

    assert len(result) == 1
    assert result[0].category_id == cat.category_id


def test_multiple_categories_ordered_by_sort_index_us1(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat_a = service.create_category(name="cat_a")
    cat_b = service.create_category(name="cat_b")
    cat_c = service.create_category(name="cat_c")
    # Place in non-alphabetical order; sort_index determines result order
    service.place_item_in_category(item.item_id, cat_c.category_id, sort_index=5)
    service.place_item_in_category(item.item_id, cat_a.category_id, sort_index=1)
    service.place_item_in_category(item.item_id, cat_b.category_id, sort_index=3)

    result = service.list_categories_by_item(item.item_id)

    assert [c.category_id for c in result] == [cat_a.category_id, cat_b.category_id, cat_c.category_id]


def test_removed_placement_not_in_result_us1(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat = service.create_category(name="Jazz")
    service.place_item_in_category(item.item_id, cat.category_id)
    service.remove_item_from_category(item.item_id, cat.category_id)

    result = service.list_categories_by_item(item.item_id)

    assert result == []


def test_empty_when_item_has_no_placements_us2(service: TaxomeshService) -> None:
    item = service.create_item(name="unplaced")

    result = service.list_categories_by_item(item.item_id)

    assert result == []


def test_nonexistent_item_raises_us3(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.list_categories_by_item(uuid4())


def test_disabled_category_included_us4(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat = service.create_category(name="Jazz")
    service.place_item_in_category(item.item_id, cat.category_id)
    # Disable category at repository level and invalidate cache
    service._repo.save_category(cat.model_copy(update={"enabled": False}))
    clear_all_caches()

    result = service.list_categories_by_item(item.item_id)

    assert len(result) == 1
    assert result[0].category_id == cat.category_id
    assert result[0].enabled is False


def test_cache_invalidated_after_place_us4(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat = service.create_category(name="Jazz")

    # Prime the cache with empty result
    first = service.list_categories_by_item(item.item_id)
    assert first == []

    # Place the item — cache must be invalidated
    service.place_item_in_category(item.item_id, cat.category_id)

    result = service.list_categories_by_item(item.item_id)
    assert len(result) == 1
    assert result[0].category_id == cat.category_id


def test_cache_invalidated_after_remove_us4(service: TaxomeshService) -> None:
    item = service.create_item(name="album")
    cat = service.create_category(name="Jazz")
    service.place_item_in_category(item.item_id, cat.category_id)

    # Prime the cache with one category
    first = service.list_categories_by_item(item.item_id)
    assert len(first) == 1

    # Remove the placement — cache must be invalidated
    service.remove_item_from_category(item.item_id, cat.category_id)

    result = service.list_categories_by_item(item.item_id)
    assert result == []


def test_cache_invalidated_after_reorder_us4(service: TaxomeshService) -> None:
    item_x = service.create_item(name="item_x")
    item_y = service.create_item(name="item_y")
    cat_a = service.create_category(name="cat_a")
    cat_b = service.create_category(name="cat_b")
    # item_x belongs to both categories; initial order: cat_b (sort=2) then cat_a (sort=5)
    service.place_item_in_category(item_x.item_id, cat_a.category_id, sort_index=5)
    service.place_item_in_category(item_x.item_id, cat_b.category_id, sort_index=2)
    service.place_item_in_category(item_y.item_id, cat_a.category_id, sort_index=10)

    # Prime the cache
    first = service.list_categories_by_item(item_x.item_id)
    assert [c.category_id for c in first] == [cat_b.category_id, cat_a.category_id]

    # Reorder items in cat_a: item_x gets sort_index=0, item_y gets sort_index=1
    # After reorder item_x links: cat_a(0), cat_b(2) → expected order [cat_a, cat_b]
    service.reorder_items_in_category(cat_a.category_id, [item_x.item_id, item_y.item_id])

    result = service.list_categories_by_item(item_x.item_id)
    assert [c.category_id for c in result] == [cat_a.category_id, cat_b.category_id]
