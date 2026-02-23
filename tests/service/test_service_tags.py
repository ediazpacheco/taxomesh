"""Tests for TaxomeshService tag operations (US3)."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshItemNotFoundError, TaxomeshTagNotFoundError


def test_create_tag_returns_tag_with_id(service: TaxomeshService) -> None:
    tag = service.create_tag(name="urgent")
    assert isinstance(tag.tag_id, UUID)
    assert tag.name == "urgent"


def test_assign_tag_succeeds(service: TaxomeshService) -> None:
    tag = service.create_tag(name="hot")
    item = service.create_item(external_id="ref-x")
    service.assign_tag(tag.tag_id, item.item_id)  # must not raise


def test_assign_tag_idempotent(service: TaxomeshService) -> None:
    tag = service.create_tag(name="cold")
    item = service.create_item(external_id="ref-y")
    service.assign_tag(tag.tag_id, item.item_id)
    service.assign_tag(tag.tag_id, item.item_id)  # second call must not raise or duplicate


def test_remove_tag_succeeds(service: TaxomeshService) -> None:
    tag = service.create_tag(name="temp")
    item = service.create_item(external_id="ref-z")
    service.assign_tag(tag.tag_id, item.item_id)
    service.remove_tag(tag.tag_id, item.item_id)  # must not raise


def test_remove_tag_noop_if_not_linked(service: TaxomeshService) -> None:
    tag = service.create_tag(name="unused")
    item = service.create_item(external_id="ref-w")
    service.remove_tag(tag.tag_id, item.item_id)  # no prior assignment, must not raise


def test_assign_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.create_item(external_id="ref-1")
    with pytest.raises(TaxomeshTagNotFoundError):
        service.assign_tag(uuid4(), item.item_id)


def test_assign_missing_item_raises(service: TaxomeshService) -> None:
    tag = service.create_tag(name="tag1")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.assign_tag(tag.tag_id, uuid4())


def test_remove_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.create_item(external_id="ref-2")
    with pytest.raises(TaxomeshTagNotFoundError):
        service.remove_tag(uuid4(), item.item_id)


def test_remove_missing_item_raises(service: TaxomeshService) -> None:
    tag = service.create_tag(name="tag2")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.remove_tag(tag.tag_id, uuid4())


def test_assign_both_missing_raises_tag_first(service: TaxomeshService) -> None:
    """Tag existence is validated before item existence (contract guarantee)."""
    with pytest.raises(TaxomeshTagNotFoundError):
        service.assign_tag(uuid4(), uuid4())
