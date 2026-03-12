"""Shared fixtures for the contrib test suite."""

import pytest

from taxomesh.application.service import TaxomeshService
from tests.service.conftest import InMemoryRepository


@pytest.fixture
def service() -> TaxomeshService:
    """Return a TaxomeshService backed by a fresh InMemoryRepository."""
    return TaxomeshService(repository=InMemoryRepository())
