"""Tests for TaxomeshService.categories.list(item=…)."""

from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshItemNotFoundError


def test_single_category_returned_us1(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat = service.categories.create(name="Jazz")
    service.items.place_in(item.item_id, cat.category_id)

    result = service.categories.list(item=item.item_id)

    assert len(result) == 1
    assert result[0].category_id == cat.category_id


def test_multiple_categories_ordered_by_sort_index_us1(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat_a = service.categories.create(name="cat_a")
    cat_b = service.categories.create(name="cat_b")
    cat_c = service.categories.create(name="cat_c")
    # Place in non-alphabetical order; sort_index determines result order
    service.items.place_in(item.item_id, cat_c.category_id, sort_index=5)
    service.items.place_in(item.item_id, cat_a.category_id, sort_index=1)
    service.items.place_in(item.item_id, cat_b.category_id, sort_index=3)

    result = service.categories.list(item=item.item_id)

    assert [c.category_id for c in result] == [cat_a.category_id, cat_b.category_id, cat_c.category_id]


def test_removed_placement_not_in_result_us1(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat = service.categories.create(name="Jazz")
    service.items.place_in(item.item_id, cat.category_id)
    service.items.remove_from(item.item_id, cat.category_id)

    result = service.categories.list(item=item.item_id)

    assert result == ()


def test_empty_when_item_has_no_placements_us2(service: TaxomeshService) -> None:
    item = service.items.create(name="unplaced")

    result = service.categories.list(item=item.item_id)

    assert result == ()


def test_nonexistent_item_raises_us3(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.categories.list(item=uuid4())


def test_disabled_category_included_us4(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat = service.categories.create(name="Jazz")
    service.items.place_in(item.item_id, cat.category_id)
    # Disable category at repository level and invalidate cache
    service._repo.save_category(cat.model_copy(update={"enabled": False}))
    service._cache.clear()

    result = service.categories.list(item=item.item_id, enabled=None)

    assert len(result) == 1
    assert result[0].category_id == cat.category_id
    assert result[0].enabled is False


def test_cache_invalidated_after_place_us4(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat = service.categories.create(name="Jazz")

    # Prime the cache with empty result
    first = service.categories.list(item=item.item_id)
    assert first == ()

    # Place the item — cache must be invalidated
    service.items.place_in(item.item_id, cat.category_id)

    result = service.categories.list(item=item.item_id)
    assert len(result) == 1
    assert result[0].category_id == cat.category_id


def test_cache_invalidated_after_remove_us4(service: TaxomeshService) -> None:
    item = service.items.create(name="album")
    cat = service.categories.create(name="Jazz")
    service.items.place_in(item.item_id, cat.category_id)

    # Prime the cache with one category
    first = service.categories.list(item=item.item_id)
    assert len(first) == 1

    # Remove the placement — cache must be invalidated
    service.items.remove_from(item.item_id, cat.category_id)

    result = service.categories.list(item=item.item_id)
    assert result == ()


def test_cache_invalidated_after_reorder_us4(service: TaxomeshService) -> None:
    item_x = service.items.create(name="item_x")
    item_y = service.items.create(name="item_y")
    cat_a = service.categories.create(name="cat_a")
    cat_b = service.categories.create(name="cat_b")
    # item_x belongs to both categories; initial order: cat_b (sort=2) then cat_a (sort=5)
    service.items.place_in(item_x.item_id, cat_a.category_id, sort_index=5)
    service.items.place_in(item_x.item_id, cat_b.category_id, sort_index=2)
    service.items.place_in(item_y.item_id, cat_a.category_id, sort_index=10)

    # Prime the cache
    first = service.categories.list(item=item_x.item_id)
    assert [c.category_id for c in first] == [cat_b.category_id, cat_a.category_id]

    # Reorder items in cat_a: item_x gets sort_index=0, item_y gets sort_index=1
    # After reorder item_x links: cat_a(0), cat_b(2) → expected order [cat_a, cat_b]
    service.items.reorder(cat_a.category_id, [item_x.item_id, item_y.item_id])

    result = service.categories.list(item=item_x.item_id)
    assert [c.category_id for c in result] == [cat_a.category_id, cat_b.category_id]
