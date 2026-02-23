"""Tests for TaxomeshService item operations (US2)."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshItemNotFoundError


def test_create_item_with_uuid_external_id(service: TaxomeshService) -> None:
    ext = uuid4()
    item = service.create_item(external_id=ext)
    assert isinstance(item.item_id, UUID)
    assert item.item_id != ext
    assert item.external_id == ext


def test_create_item_with_str_external_id(service: TaxomeshService) -> None:
    item = service.create_item(external_id="product-abc")
    assert item.external_id == "product-abc"


def test_create_item_with_int_external_id(service: TaxomeshService) -> None:
    item = service.create_item(external_id=42)
    assert item.external_id == 42


def test_get_item_returns_item_with_all_fields(service: TaxomeshService) -> None:
    item = service.create_item(external_id="ref-1", metadata={"k": "v"})
    retrieved = service.get_item(item.item_id)
    assert retrieved.item_id == item.item_id
    assert retrieved.external_id == "ref-1"
    assert retrieved.metadata == {"k": "v"}


def test_get_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.get_item(uuid4())


def test_list_items_returns_all_created(service: TaxomeshService) -> None:
    service.create_item(external_id="a")
    service.create_item(external_id="b")
    items = service.list_items()
    assert len(items) == 2


def test_list_items_empty(service: TaxomeshService) -> None:
    assert service.list_items() == []


def test_delete_item_removes_it(service: TaxomeshService) -> None:
    item = service.create_item(external_id="to-delete")
    service.delete_item(item.item_id)
    with pytest.raises(TaxomeshItemNotFoundError):
        service.get_item(item.item_id)


def test_delete_missing_item_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshItemNotFoundError):
        service.delete_item(uuid4())
