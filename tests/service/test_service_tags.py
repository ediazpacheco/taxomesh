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
    item = service.create_item(name="ref-x", external_id="ref-x")
    service.assign_tag(tag.tag_id, item.item_id)  # must not raise


def test_assign_tag_idempotent(service: TaxomeshService) -> None:
    tag = service.create_tag(name="cold")
    item = service.create_item(name="ref-y", external_id="ref-y")
    service.assign_tag(tag.tag_id, item.item_id)
    service.assign_tag(tag.tag_id, item.item_id)  # second call must not raise or duplicate


def test_remove_tag_succeeds(service: TaxomeshService) -> None:
    tag = service.create_tag(name="temp")
    item = service.create_item(name="ref-z", external_id="ref-z")
    service.assign_tag(tag.tag_id, item.item_id)
    service.remove_tag(tag.tag_id, item.item_id)  # must not raise


def test_remove_tag_noop_if_not_linked(service: TaxomeshService) -> None:
    tag = service.create_tag(name="unused")
    item = service.create_item(name="ref-w", external_id="ref-w")
    service.remove_tag(tag.tag_id, item.item_id)  # no prior assignment, must not raise


def test_assign_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.create_item(name="ref-1", external_id="ref-1")
    with pytest.raises(TaxomeshTagNotFoundError):
        service.assign_tag(uuid4(), item.item_id)


def test_assign_missing_item_raises(service: TaxomeshService) -> None:
    tag = service.create_tag(name="tag1")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.assign_tag(tag.tag_id, uuid4())


def test_remove_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.create_item(name="ref-2", external_id="ref-2")
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


# ---------------------------------------------------------------------------
# T-06: update_tag, delete_tag (FR-030, FR-031)
# ---------------------------------------------------------------------------


def test_update_tag_name(service: TaxomeshService) -> None:
    tag = service.create_tag(name="old")
    updated = service.update_tag(tag.tag_id, name="new")
    assert updated.name == "new"


def test_update_tag_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.update_tag(uuid4(), name="ghost")


def test_delete_tag_removes_it(service: TaxomeshService) -> None:
    tag = service.create_tag(name="gone")
    service.delete_tag(tag.tag_id)
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(tag.tag_id)


def test_delete_tag_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.delete_tag(uuid4())
