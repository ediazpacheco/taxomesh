"""Neither related read raises for the other end of a relation, whatever that end's state.

``items.list_related`` and ``items.get_many_related`` both take ``enabled``, defaulting to ``True``,
and filter the related rows by it as a listing does: a disabled row is left out without a log. A
relation whose other end is not stored is skipped, with one WARNING that names that end absent.

Only the JSON, YAML and in-memory stores can hold a relation to an item that is not stored, planted
through the port as data written outside taxomesh would be. Django's foreign keys never store one,
so the absent-row cases run on the three backends that can hold one.
"""

import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.collections.items import ItemCollection
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item, ItemRelationLink
from taxomesh.domain.types import Direction
from tests.service.conftest import InMemoryRepository

SERVICE_LOGGER = "taxomesh.application.collections.items"

type Read = Callable[..., list[str]]


# Any: the options are handed to either read unchanged, and each read checks its own.
def _via_list_related(service: TaxomeshService, item: Item, **options: Any) -> list[str]:
    """The names ``list_related`` returns for one item."""
    return [related.name for related in service.items.list_related(item, **options)]


def _via_get_many_related(service: TaxomeshService, item: Item, **options: Any) -> list[str]:
    """The names ``get_many_related`` returns for one item, across its relation types."""
    found = service.items.get_many_related([item], **options).get(item.item_id)
    return [] if found is None else [related.name for related in found]


READS: list[tuple[str, Read]] = [("list_related", _via_list_related), ("get_many_related", _via_get_many_related)]
READ_IDS = [name for name, _ in READS]


@pytest.fixture(params=["in_memory", "json", "yaml"])
def holding_service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    """A service over a store that can hold a relation to an item that is not stored."""
    if request.param == "json":
        return TaxomeshService(repository=JsonRepository(tmp_path / "store.json"))
    if request.param == "yaml":
        return TaxomeshService(repository=YamlRepository(tmp_path / "store.yaml"))
    return TaxomeshService(repository=InMemoryRepository())


def _plant(service: TaxomeshService, source: UUID, target: UUID, relation_type: str = "covers") -> None:
    """Store a relation through the port, which checks neither end."""
    service.repository.save_item_relation_link(
        ItemRelationLink(source_item_id=source, target_item_id=target, relation_type=relation_type)
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.parametrize(("name", "read"), READS, ids=READ_IDS)
class TestAnAbsentRowIsSkipped:
    """A relation whose other end is not stored is left out, with one WARNING naming that end absent."""

    def test_outgoing(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = holding_service.items.create("Source")
        missing = uuid4()
        _plant(holding_service, source.item_id, missing)

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
            assert read(holding_service, source) == []

        (message,) = _warnings(caplog)
        assert f"target item {missing} is absent" in message
        assert source.name in message
        assert "covers" in message

    def test_incoming(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        target = holding_service.items.create("Target")
        missing = uuid4()
        _plant(holding_service, missing, target.item_id)

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
            assert read(holding_service, target, direction=Direction.INCOMING) == []

        (message,) = _warnings(caplog)
        assert f"source item {missing} is absent" in message
        assert target.name in message

    def test_beside_a_stored_row(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = holding_service.items.create("Source")
        kept = holding_service.items.create("Kept")
        holding_service.items.relate(source, kept, "covers")
        _plant(holding_service, source.item_id, uuid4())

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
            assert read(holding_service, source) == ["Kept"]

        assert len(_warnings(caplog)) == 1

    def test_a_disabled_queried_item_is_named_in_the_warning(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = holding_service.items.create("Source")
        holding_service.items.update(source, enabled=False)
        _plant(holding_service, source.item_id, uuid4())

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
            read(holding_service, source)

        (message,) = _warnings(caplog)
        assert "Source" in message
        assert "unknown" not in message

    def test_a_type_filter_that_leaves_it_out_logs_nothing(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = holding_service.items.create("Source")
        _plant(holding_service, source.item_id, uuid4(), "other")

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
            assert read(holding_service, source, relation_types=["covers"]) == []

        assert _warnings(caplog) == []

    def test_a_queried_item_whose_str_raises_is_still_logged(
        self, holding_service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = holding_service.items.create("Broken")
        missing = uuid4()
        _plant(holding_service, source.item_id, missing)

        def _raise(self: Item) -> str:
            raise RuntimeError("__str__ intentionally broken")

        with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER), patch.object(Item, "__str__", _raise):
            read(holding_service, source)

        (message,) = _warnings(caplog)
        assert str(missing) in message
        assert "str() failed" in message


@pytest.mark.parametrize(("name", "read"), READS, ids=READ_IDS)
class TestADisabledRowIsFiltered:
    """``enabled`` filters the related rows as a listing does, defaulting to enabled only."""

    def test_by_default_without_a_log(
        self, service: TaxomeshService, caplog: pytest.LogCaptureFixture, name: str, read: Read
    ) -> None:
        source = service.items.create("Source")
        on = service.items.create("On")
        off = service.items.create("Off")
        service.items.relate(source, on, "covers")
        service.items.relate(source, off, "covers", sort_index=1)
        service.items.update(off, enabled=False)

        with caplog.at_level(logging.DEBUG, logger=SERVICE_LOGGER):
            assert read(service, source) == ["On"]

        assert caplog.records == []

    def test_each_value_selects_as_a_listing_does(self, service: TaxomeshService, name: str, read: Read) -> None:
        source = service.items.create("Source")
        on = service.items.create("On")
        off = service.items.create("Off")
        service.items.relate(source, on, "covers")
        service.items.relate(source, off, "covers", sort_index=1)
        service.items.update(off, enabled=False)

        assert read(service, source, enabled=True) == ["On"]
        assert read(service, source, enabled=False) == ["Off"]
        assert read(service, source, enabled=None) == ["On", "Off"]

    def test_a_disabled_queried_item_still_has_its_relations(
        self, service: TaxomeshService, name: str, read: Read
    ) -> None:
        source = service.items.create("Source")
        target = service.items.create("Target")
        service.items.relate(source, target, "covers")
        service.items.update(source, enabled=False)

        assert read(service, source) == ["Target"]


def test_an_empty_request_reads_and_logs_nothing(service: TaxomeshService, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        assert service.items.get_many_related([]) == {}
        assert service.items.get_many_related([], direction="incoming") == {}

    assert _warnings(caplog) == []


@pytest.mark.parametrize("member", [ItemCollection.list_related, ItemCollection.get_many_related])
def test_neither_read_can_be_told_to_raise(member: Callable[..., object]) -> None:
    """Nothing a related row can be makes either read raise, so no option asks it to."""
    assert "skip_on_error" not in inspect.signature(member).parameters
