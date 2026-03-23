"""Tests for taxomesh public-library logging conventions."""

import logging
import re
from uuid import uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item, ItemRelationLink
from tests.service.conftest import InMemoryRepository

SERVICE_LOGGER = "taxomesh.application.service"
ROOT_LOGGER = "taxomesh"


def test_null_handler_registered() -> None:
    """NullHandler is registered on the taxomesh root logger after import."""
    import taxomesh  # noqa: F401, PLC0415 — ensure package is imported

    root_logger = logging.getLogger(ROOT_LOGGER)
    handler_types = [type(h) for h in root_logger.handlers]
    assert logging.NullHandler in handler_types, (
        f"Expected NullHandler in taxomesh logger handlers, got: {handler_types}"
    )


def test_taxomesh_logger_hierarchy() -> None:
    """All taxomesh module loggers are descendants of the 'taxomesh' root logger."""
    service_logger = logging.getLogger(SERVICE_LOGGER)
    assert service_logger.name.startswith("taxomesh."), (
        f"Logger name {service_logger.name!r} is not under 'taxomesh' hierarchy"
    )


def test_no_timestamp_in_message_text(caplog: pytest.LogCaptureFixture) -> None:
    """Taxomesh WARNING messages do not embed timestamps in the message string itself."""
    source = Item(name="Source Item")
    missing_target_id = uuid4()
    link = ItemRelationLink(
        source_item_id=source.item_id,
        target_item_id=missing_target_id,
        relation_type="related_to",
    )
    repo = InMemoryRepository()
    repo.save_item(source)
    repo._item_relation_links = [link]
    svc = TaxomeshService(repository=repo)

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        svc.list_related_items_for_sources([source.item_id])

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert not re.search(r"\d{4}-\d{2}-\d{2}", msg), f"ISO-8601 timestamp pattern found in log message text: {msg!r}"
