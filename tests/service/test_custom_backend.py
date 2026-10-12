"""Tests for custom storage backend support.

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
    item = svc.items.create(name="custom-123", external_id="custom-123")
    assert item.item_id in repo._items
    assert repo._items[item.item_id].external_id == "custom-123"


def test_service_delegates_category_writes_to_custom_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    cat = svc.categories.create(name="Custom")
    assert cat.category_id in repo._categories


def test_service_delegates_tag_writes_to_custom_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.tags.create(name="ctag")
    assert tag.tag_id in repo._tags


# ---------------------------------------------------------------------------
# T-06: custom backend delegation for tags.delete, items.place_in
# ---------------------------------------------------------------------------


def test_service_delegates_tags_delete_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    tag = svc.tags.create(name="del")
    svc.tags.delete(tag.tag_id)
    assert tag.tag_id not in repo._tags


def test_service_delegates_place_in_to_backend() -> None:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    item = svc.items.create(name="x", external_id="x")
    cat = svc.categories.create(name="C")
    svc.items.place_in(item.item_id, cat.category_id)
    assert len(repo._item_parent_links) == 1
