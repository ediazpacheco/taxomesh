"""Tests for custom storage backend support (US4).

Validates that TaxomeshService accepts any Protocol-conforming object without
requiring inheritance from TaxomeshRepositoryBase.
"""

from taxomesh.application.service import TaxomeshService
from tests.service.conftest import InMemoryRepository


def test_in_memory_repository_has_no_taxomesh_base_in_mro() -> None:
    """InMemoryRepository must not inherit from TaxomeshRepositoryBase."""
    mro_names = {cls.__name__ for cls in InMemoryRepository.__mro__}
    assert "TaxomeshRepositoryBase" not in mro_names


def test_service_delegates_writes_to_custom_backend() -> None:
    """Service must store data in the provided backend, not bypass it."""
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="custom-123")
    assert item.item_id in repo._items
    assert repo._items[item.item_id].external_id == "custom-123"


def test_service_delegates_category_writes_to_custom_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    cat = svc.create_category(name="Custom")
    assert cat.category_id in repo._categories


def test_service_delegates_tag_writes_to_custom_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="ctag")
    assert tag.tag_id in repo._tags


# ---------------------------------------------------------------------------
# T-06: custom backend delegation for delete_tag, place_item_in_category
# ---------------------------------------------------------------------------


def test_service_delegates_delete_tag_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.create_tag(name="del")
    svc.delete_tag(tag.tag_id)
    assert tag.tag_id not in repo._tags


def test_service_delegates_place_item_in_category_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    item = svc.create_item(external_id="x")
    cat = svc.create_category(name="C")
    svc.place_item_in_category(item.item_id, cat.category_id)
    assert len(repo._item_parent_links) == 1
