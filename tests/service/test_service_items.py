"""Tests for TaxomeshService item operations."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError


def test_items_create_with_uuid_external_id(service: TaxomeshService) -> None:
    ext = uuid4()
    item = service.items.create(name=str(ext), external_id=ext)
    assert isinstance(item.item_id, UUID)
    assert item.item_id != ext
    assert item.external_id == str(ext)


def test_items_create_with_str_external_id(service: TaxomeshService) -> None:
    item = service.items.create(name="product-abc", external_id="product-abc")
    assert item.external_id == "product-abc"


def test_items_create_with_int_external_id(service: TaxomeshService) -> None:
    item = service.items.create(name="42", external_id=42)
    assert item.external_id == "42"


def test_items_subscript_returns_item_with_all_fields(service: TaxomeshService) -> None:
    item = service.items.create(name="ref-1", external_id="ref-1", metadata={"k": "v"})
    retrieved = service.items[item.item_id]
    assert retrieved.item_id == item.item_id
    assert retrieved.external_id == "ref-1"
    assert retrieved.metadata == {"k": "v"}


def test_get_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items[uuid4()]


def test_items_list_returns_all_created(service: TaxomeshService) -> None:
    service.items.create(name="a", external_id="a")
    service.items.create(name="b", external_id="b")
    items = service.items.list()
    assert len(items) == 2


def test_items_list_empty(service: TaxomeshService) -> None:
    assert service.items.list() == ()


def test_items_delete_removes_it(service: TaxomeshService) -> None:
    item = service.items.create(name="to-delete", external_id="to-delete")
    service.items.delete(item.item_id)
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items[item.item_id]


def test_delete_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items.delete(uuid4())


# ---------------------------------------------------------------------------
# T-06: items.update, items.place_in, items.list filtered
# ---------------------------------------------------------------------------


def test_items_update_enabled(service: TaxomeshService) -> None:
    item = service.items.create(name="x", external_id="x")
    updated = service.items.update(item.item_id, enabled=False)
    assert updated.enabled is False


def test_items_update_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items.update(uuid4(), enabled=True)


def test_items_update_metadata_replaces_value(service: TaxomeshService) -> None:
    item = service.items.create(name="meta-item", external_id="meta-item", metadata={"old": True})
    updated = service.items.update(item.item_id, metadata={"new": 42})
    assert updated.metadata == {"new": 42}


def test_items_update_metadata_none_leaves_existing_unchanged(service: TaxomeshService) -> None:
    item = service.items.create(name="preserve-item", external_id="preserve-item", metadata={"keep": "me"})
    updated = service.items.update(item.item_id, enabled=False)
    assert updated.metadata == {"keep": "me"}


def test_place_in_returns_link(service: TaxomeshService) -> None:
    item = service.items.create(name="x", external_id="x")
    cat = service.categories.create(name="C")
    link = service.items.place_in(item.item_id, cat.category_id, sort_index=2)
    assert link.item_id == item.item_id
    assert link.category_id == cat.category_id
    assert link.sort_index == 2


def test_place_in_idempotent(service: TaxomeshService) -> None:
    item = service.items.create(name="x", external_id="x")
    cat = service.categories.create(name="C")
    service.items.place_in(item.item_id, cat.category_id, sort_index=1)
    service.items.place_in(item.item_id, cat.category_id, sort_index=99)
    links = service._repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99


def test_place_in_item_not_found_raises(service: TaxomeshService) -> None:
    cat = service.categories.create(name="C")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items.place_in(uuid4(), cat.category_id)


def test_place_in_category_not_found_raises(service: TaxomeshService) -> None:
    item = service.items.create(name="x", external_id="x")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.items.place_in(item.item_id, uuid4())


def test_items_list_filtered_by_category(service: TaxomeshService) -> None:
    cat = service.categories.create(name="C")
    i1 = service.items.create(name="a", external_id="a")
    i2 = service.items.create(name="b", external_id="b")
    service.items.place_in(i2.item_id, cat.category_id, sort_index=1)
    service.items.place_in(i1.item_id, cat.category_id, sort_index=2)
    result = service.items.list(category=cat.category_id)
    assert [i.item_id for i in result] == [i2.item_id, i1.item_id]


def test_items_list_category_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.items.list(category=uuid4())


def test_items_create_without_external_id(service: TaxomeshService) -> None:
    item = service.items.create(name="no-id-item")
    assert item.external_id is None
