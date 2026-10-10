"""Tests for TaxomeshService tag operations."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshItemNotFoundError, TaxomeshTagNotFoundError
from tests.service.conftest import CountedService


def test_tags_create_returns_tag_with_id(service: TaxomeshService) -> None:
    tag = service.tags.create(name="urgent")
    assert isinstance(tag.tag_id, UUID)
    assert tag.name == "urgent"


def test_tag_succeeds(service: TaxomeshService) -> None:
    tag = service.tags.create(name="hot")
    item = service.items.create(name="ref-x", external_id="ref-x")
    service.items.tag(item.item_id, tag.tag_id)  # must not raise


def test_tag_idempotent(service: TaxomeshService) -> None:
    tag = service.tags.create(name="cold")
    item = service.items.create(name="ref-y", external_id="ref-y")
    service.items.tag(item.item_id, tag.tag_id)
    service.items.tag(item.item_id, tag.tag_id)  # second call must not raise or duplicate


def test_untag_succeeds(service: TaxomeshService) -> None:
    tag = service.tags.create(name="temp")
    item = service.items.create(name="ref-z", external_id="ref-z")
    service.items.tag(item.item_id, tag.tag_id)
    service.items.untag(item.item_id, tag.tag_id)  # must not raise


def test_untag_noop_if_not_linked(service: TaxomeshService) -> None:
    tag = service.tags.create(name="unused")
    item = service.items.create(name="ref-w", external_id="ref-w")
    service.items.untag(item.item_id, tag.tag_id)  # no prior assignment, must not raise


def test_assign_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.items.create(name="ref-1", external_id="ref-1")
    with pytest.raises(TaxomeshTagNotFoundError):
        service.items.tag(item.item_id, uuid4())


def test_assign_missing_item_raises(service: TaxomeshService) -> None:
    tag = service.tags.create(name="tag1")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items.tag(uuid4(), tag.tag_id)


def test_remove_missing_tag_raises(service: TaxomeshService) -> None:
    item = service.items.create(name="ref-2", external_id="ref-2")
    with pytest.raises(TaxomeshTagNotFoundError):
        service.items.untag(item.item_id, uuid4())


def test_remove_missing_item_raises(service: TaxomeshService) -> None:
    tag = service.tags.create(name="tag2")
    with pytest.raises(TaxomeshItemNotFoundError):
        service.items.untag(uuid4(), tag.tag_id)


def test_assign_both_missing_raises_tag_first(service: TaxomeshService) -> None:
    """Tag existence is validated before item existence (contract guarantee)."""
    with pytest.raises(TaxomeshTagNotFoundError):
        service.items.tag(uuid4(), uuid4())


class TestItemFirstTagging:
    """``items.tag`` and ``items.untag`` take the item first, then the tag."""

    def test_tag_links_the_item_to_the_tag(self, service: TaxomeshService) -> None:
        """The link ``tag(item_id, tag_id)`` leaves is the item's link to that tag."""
        tag = service.tags.create("hot")
        item = service.items.create("ref-x")

        service.items.tag(item.item_id, tag.tag_id)

        assert service.repository.delete_item_tag_link(item.item_id, tag.tag_id) is True

    def test_a_reversed_call_raises_and_links_nothing(self, service: TaxomeshService) -> None:
        """A call still written tag-first fails loudly on the tag, and no link is left behind."""
        tag = service.tags.create("hot")
        item = service.items.create("ref-x")

        with pytest.raises(TaxomeshTagNotFoundError):
            service.items.tag(tag.tag_id, item.item_id)

        assert service.repository.delete_item_tag_link(item.item_id, tag.tag_id) is False

    def test_untag_with_both_ids_unknown_raises_the_tags_error(self, service: TaxomeshService) -> None:
        """Detaching checks the tag first too, exactly as attaching does."""
        with pytest.raises(TaxomeshTagNotFoundError):
            service.items.untag(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# T-06: tags.update, tags.delete
# ---------------------------------------------------------------------------


def test_tags_update_name(service: TaxomeshService) -> None:
    tag = service.tags.create(name="old")
    updated = service.tags.update(tag.tag_id, name="new")
    assert updated.name == "new"


def test_tags_update_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.tags.update(uuid4(), name="ghost")


def test_tags_delete_removes_it(service: TaxomeshService) -> None:
    tag = service.tags.create(name="gone")
    service.tags.delete(tag.tag_id)
    with pytest.raises(TaxomeshTagNotFoundError):
        service.tags.delete(tag.tag_id)


def test_tags_delete_not_found_raises(service: TaxomeshService) -> None:
    with pytest.raises(TaxomeshTagNotFoundError):
        service.tags.delete(uuid4())


def test_get_many_reads_storage_once_for_any_number_of_tags(counting_service: CountedService) -> None:
    """Five identifiers, one of them never stored, cost one keyed read, cold."""
    service = counting_service.service
    stored = [service.tags.create(name=f"tag-{n}") for n in range(4)]
    absent = uuid4()
    counting_service.cold()

    found = service.tags.get_many([*(tag.tag_id for tag in stored), absent])

    assert found == {tag.tag_id: tag for tag in stored}
    assert counting_service.reads.total == 1
    assert counting_service.reads.count_of("map_tags_by_id") == 1
