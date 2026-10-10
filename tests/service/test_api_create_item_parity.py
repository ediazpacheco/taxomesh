"""Parity regressions for item creation through the public API helpers."""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.contrib.api import handlers
from taxomesh.contrib.api.schemas import CreateItemRequest

pytestmark = pytest.mark.django_db


def test_create_multiple_items_without_external_ids(service: TaxomeshService) -> None:
    """Omitted external IDs remain unset and do not conflict on any backend."""
    first = handlers.items_create(service, body=CreateItemRequest(name="First item"))
    second = handlers.items_create(service, body=CreateItemRequest(name="Second item"))

    assert first.item_id != second.item_id
    assert first.external_id is None
    assert second.external_id is None
    assert service.items[first.item_id] == first
    assert service.items[second.item_id] == second
