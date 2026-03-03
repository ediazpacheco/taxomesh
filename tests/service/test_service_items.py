"""Tests for TaxomeshService item operations (US2)."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError


def test_create_item_with_uuid_external_id(service: TaxomeshService) -> None:
    ext = uuid4()
    item = service.create_item(name=str(ext), external_id=ext)
    assert isinstance(item.item_id, UUID)
    assert item.item_id != ext
    assert item.external_id == str(ext)


def test_create_item_with_str_external_id(service: TaxomeshService) -> None:
    item = service.create_item(name="product-abc", external_id="product-abc")
    assert item.external_id == "product-abc"


def test_create_item_with_int_external_id(service: TaxomeshService) -> None:
    item = service.create_item(name="42", external_id=42)
    assert item.external_id == "42"


def test_get_item_returns_item_with_all_fields(service: TaxomeshService) -> None:
    item = service.create_item(name="ref-1", external_id="ref-1", metadata={"k": "v"})
    retrieved = service.get_item(item.item_id)
    assert retrieved.item_id == item.item_id
    assert retrieved.external_id == "ref-1"
    assert retrieved.metadata == {"k": "v"}


def test_get_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.get_item(uuid4())


def test_list_items_returns_all_created(service: TaxomeshService) -> None:
    service.create_item(name="a", external_id="a")
    service.create_item(name="b", external_id="b")
    items = service.list_items()
    assert len(items) == 2


def test_list_items_empty(service: TaxomeshService) -> None:
    assert service.list_items() == []


def test_delete_item_removes_it(service: TaxomeshService) -> None:
    item = service.create_item(name="to-delete", external_id="to-delete")
    service.delete_item(item.item_id)
    with pytest.raises(TaxomeshItemNotFoundError):
        service.get_item(item.item_id)


def test_delete_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.delete_item(uuid4())


# ---------------------------------------------------------------------------
# T-06: update_item, place_item_in_category, list_items filtered (FR-028, FR-031, FR-032)
# ---------------------------------------------------------------------------


def test_update_item_enabled(service: TaxomeshService) -> None:
    item = service.create_item(name="x", external_id="x")
    updated = service.update_item(item.item_id, enabled=False)
    assert updated.enabled is False


def test_update_item_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.update_item(uuid4(), enabled=True)


def test_update_item_metadata_replaces_value(service: TaxomeshService) -> None:
    item = service.create_item(name="meta-item", external_id="meta-item", metadata={"old": True})
    updated = service.update_item(item.item_id, metadata={"new": 42})
    assert updated.metadata == {"new": 42}


def test_update_item_metadata_none_leaves_existing_unchanged(service: TaxomeshService) -> None:
    item = service.create_item(name="preserve-item", external_id="preserve-item", metadata={"keep": "me"})
    updated = service.update_item(item.item_id, enabled=False)
    assert updated.metadata == {"keep": "me"}


def test_place_item_in_category_returns_link(service: TaxomeshService) -> None:
    item = service.create_item(name="x", external_id="x")
    cat = service.create_category(name="C")
    link = service.place_item_in_category(item.item_id, cat.category_id, sort_index=2)
    assert link.item_id == item.item_id
    assert link.category_id == cat.category_id
    assert link.sort_index == 2


def test_place_item_in_category_idempotent(service: TaxomeshService) -> None:
    item = service.create_item(name="x", external_id="x")
    cat = service.create_category(name="C")
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=1)
    service.place_item_in_category(item.item_id, cat.category_id, sort_index=99)
    links = service._repo.list_item_parent_links()
    assert len(links) == 1
    assert links[0].sort_index == 99


def test_place_item_in_category_item_not_found_raises(service: TaxomeshService) -> None:
    cat = service.create_category(name="C")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.place_item_in_category(uuid4(), cat.category_id)


def test_place_item_in_category_category_not_found_raises(service: TaxomeshService) -> None:
    item = service.create_item(name="x", external_id="x")
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.place_item_in_category(item.item_id, uuid4())


def test_list_items_filtered_by_category(service: TaxomeshService) -> None:
    cat = service.create_category(name="C")
    i1 = service.create_item(name="a", external_id="a")
    i2 = service.create_item(name="b", external_id="b")
    service.place_item_in_category(i2.item_id, cat.category_id, sort_index=1)
    service.place_item_in_category(i1.item_id, cat.category_id, sort_index=2)
    result = service.list_items(category_id=cat.category_id)
    assert [i.item_id for i in result] == [i2.item_id, i1.item_id]


def test_list_items_category_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshCategoryNotFoundError):
        service.list_items(category_id=uuid4())
