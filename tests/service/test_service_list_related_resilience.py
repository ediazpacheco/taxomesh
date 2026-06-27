"""Tests for list_related_items_for_sources() resilience: skip_on_error and warning logging."""

import logging
from unittest.mock import patch
from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item, ItemRelationLink
from taxomesh.exceptions import TaxomeshItemNotFoundError
from tests.service.conftest import InMemoryRepository

SERVICE_LOGGER = "taxomesh.application.service"


def _make_service_with_links(items: list[Item], links: list[ItemRelationLink]) -> TaxomeshService:
    """Return a TaxomeshService backed by an InMemoryRepository pre-loaded with items and links."""
    repo = InMemoryRepository()
    for item in items:
        repo.save_item(item)
    repo._item_relation_links = list(links)
    return TaxomeshService(repository=repo)


# ---------------------------------------------------------------------------
# US1 — T002: single dangling link
# ---------------------------------------------------------------------------


def test_single_dangling_link_no_exception(caplog: pytest.LogCaptureFixture) -> None:
    """Single dangling link: returns {}, emits one WARNING, no exception."""
    source = Item(name="Source")
    missing_target_id = uuid4()
    link = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_target_id,
        relation_type="related_to",
    )
    svc = _make_service_with_links([source], [link])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([source.item_id])

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert "list_related_items_for_sources" in msg
    assert source.name in msg
    assert "orphaned" in msg
    assert str(missing_target_id) in msg
    assert "related_to" in msg


def test_empty_source_item_ids_returns_empty(caplog: pytest.LogCaptureFixture) -> None:
    """Empty source_item_ids: returns {} immediately, no WARNING (EC-02)."""
    svc = _make_service_with_links([], [])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([])

    assert result == {}
    assert not any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# US1 — T003: mixed valid + dangling links
# ---------------------------------------------------------------------------


def test_mixed_valid_and_dangling_link(caplog: pytest.LogCaptureFixture) -> None:
    """Valid target appears in result; dangling target absent; one WARNING."""
    source = Item(name="Source")
    valid_target = Item(name="Valid Target")
    missing_id = uuid4()
    link_valid = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=valid_target.item_id,
        relation_type="covers",
    )
    link_dangling = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_id,
        relation_type="covers",
    )
    svc = _make_service_with_links([source, valid_target], [link_valid, link_dangling])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([source.item_id])

    assert source.item_id in result
    covers = result[source.item_id]["covers"]
    assert valid_target in covers
    assert not any(i.item_id == missing_id for i in covers)
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1


def test_relation_types_filter_excludes_dangling_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    """relation_types filter excludes the dangling link → no WARNING emitted (EC-04)."""
    source = Item(name="Source")
    missing_id = uuid4()
    link_dangling = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_id,
        relation_type="other_type",
    )
    svc = _make_service_with_links([source], [link_dangling])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        # filter only "covers" — the dangling "other_type" link is excluded
        result = svc.list_related_items_for_sources([source.item_id], relation_types=["covers"])

    assert result == {}
    assert not any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# US1 — T004: all dangling for one source, valid links for another
# ---------------------------------------------------------------------------


def test_all_dangling_source_absent_other_source_present(caplog: pytest.LogCaptureFixture) -> None:
    """All links for source_a dangling → absent from result; source_b valid → present."""
    source_a = Item(name="Source A")
    source_b = Item(name="Source B")
    valid_target = Item(name="Valid Target")
    missing_id_1 = uuid4()
    missing_id_2 = uuid4()

    links = [
        ItemRelationLink(source_item_id=source_a.item_id, target_item_id=missing_id_1, relation_type="rel"),
        ItemRelationLink(source_item_id=source_a.item_id, target_item_id=missing_id_2, relation_type="rel"),
        ItemRelationLink(source_item_id=source_b.item_id, target_item_id=valid_target.item_id, relation_type="rel"),
    ]
    svc = _make_service_with_links([source_a, source_b, valid_target], links)

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([source_a.item_id, source_b.item_id])

    assert source_a.item_id not in result
    assert source_b.item_id in result
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 2  # one per dangling link


# ---------------------------------------------------------------------------
# US2 — T008: skip_on_error=False raises
# ---------------------------------------------------------------------------


def test_skip_on_error_false_raises(caplog: pytest.LogCaptureFixture) -> None:
    """skip_on_error=False: TaxomeshItemNotFoundError raised, no WARNING logged."""
    source = Item(name="Source")
    missing_id = uuid4()
    link = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_id,
        relation_type="rel",
    )
    svc = _make_service_with_links([source], [link])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER), pytest.raises(TaxomeshItemNotFoundError):
        svc.list_related_items_for_sources([source.item_id], skip_on_error=False)

    assert not any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# US2 — T009: valid links + skip_on_error=False — normal result, no exception
# ---------------------------------------------------------------------------


def test_skip_on_error_false_valid_links_returns_normally() -> None:
    """Valid links only + skip_on_error=False: normal result, no exception."""
    source = Item(name="Source")
    target = Item(name="Target")
    link = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=target.item_id,
        relation_type="covers",
    )
    svc = _make_service_with_links([source, target], [link])

    result = svc.list_related_items_for_sources([source.item_id], skip_on_error=False)

    assert source.item_id in result
    assert target in result[source.item_id]["covers"]


# ---------------------------------------------------------------------------
# US1 — source item __str__ raises: warning still emits safely
# ---------------------------------------------------------------------------


def test_source_str_raises_warning_still_emits(caplog: pytest.LogCaptureFixture) -> None:
    """WARNING emits safely even if the source item's __str__ raises an exception."""
    source = Item(name="Broken Source")
    missing_target_id = uuid4()
    link = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_target_id,
        relation_type="rel",
    )
    svc = _make_service_with_links([source], [link])

    def _raise_str(self: Item) -> str:
        raise RuntimeError("__str__ intentionally broken")

    with (
        caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER),
        patch.object(Item, "__str__", _raise_str),
    ):
        result = svc.list_related_items_for_sources([source.item_id])

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert str(missing_target_id) in msg
    assert "str() failed" in msg


# ---------------------------------------------------------------------------
# 056 — incoming direction resilience (symmetric to the outgoing cases above)
# ---------------------------------------------------------------------------


def test_incoming_single_dangling_link_no_exception(caplog: pytest.LogCaptureFixture) -> None:
    """Incoming dangling link (missing source): returns {}, one WARNING naming the orphan source."""
    target = Item(name="Target")
    missing_source_id = uuid4()
    link = ItemRelationLink(
        source_item_id=missing_source_id,
        target_item_id=target.item_id,
        relation_type="related_to",
    )
    svc = _make_service_with_links([target], [link])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([target.item_id], direction="incoming")

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert "list_related_items_for_sources" in msg
    assert target.name in msg
    assert "orphaned" in msg
    assert str(missing_source_id) in msg
    assert "related_to" in msg
    # Role wording is mirrored for incoming: the orphan is the source endpoint.
    assert f"source: <orphaned item {missing_source_id}>" in msg


def test_incoming_empty_input_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Incoming empty input: returns {} immediately, no WARNING."""
    svc = _make_service_with_links([], [])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = svc.list_related_items_for_sources([], direction="incoming")

    assert result == {}
    assert not any(r.levelno == logging.WARNING for r in caplog.records)


def test_incoming_skip_on_error_false_raises(caplog: pytest.LogCaptureFixture) -> None:
    """Incoming skip_on_error=False: TaxomeshItemNotFoundError raised, no WARNING logged."""
    target = Item(name="Target")
    missing_source_id = uuid4()
    link = ItemRelationLink(
        source_item_id=missing_source_id,
        target_item_id=target.item_id,
        relation_type="rel",
    )
    svc = _make_service_with_links([target], [link])

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER), pytest.raises(TaxomeshItemNotFoundError):
        svc.list_related_items_for_sources([target.item_id], skip_on_error=False, direction="incoming")

    assert not any(r.levelno == logging.WARNING for r in caplog.records)
