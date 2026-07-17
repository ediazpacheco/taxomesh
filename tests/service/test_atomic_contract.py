"""Contract tests for the ``TaxomeshRepositoryBase.atomic()`` port method.

Parametrized over every backend (in-memory, JSON, YAML, Django) to assert the
shared behavioral contract: ``atomic()`` is usable as a ``with`` block, yields
``None``, and a single write performed inside the block persists on the success
path. This is backend-agnostic — the two-tier rollback/no-op distinction is
verified elsewhere (``test_atomic_operations.py``).
"""

from contextlib import AbstractContextManager
from pathlib import Path
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.domain.models import Category
from tests.service.conftest import InMemoryRepository


@pytest.fixture(
    params=["in_memory", "json", "yaml", "django"],
    ids=["in_memory", "json", "yaml", "django"],
)
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> object:
    """Return a fresh repository instance for each backend."""
    if request.param == "in_memory":
        return InMemoryRepository()
    if request.param == "json":
        return JsonRepository(tmp_path / "test.json")
    if request.param == "yaml":
        return YAMLRepository(tmp_path / "test.yaml")
    # django
    pytest.importorskip("django", reason="django not installed")
    request.getfixturevalue("db")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    return DjangoRepository()


def test_atomic_returns_context_manager(repo: object) -> None:
    """``atomic()`` returns an object usable as a context manager."""
    ctx = repo.atomic()  # type: ignore[attr-defined]
    assert isinstance(ctx, AbstractContextManager)


def test_atomic_usable_as_with_block_yields_none(repo: object) -> None:
    """Entering the ``with`` block must not raise and must yield ``None``."""
    with repo.atomic() as value:  # type: ignore[attr-defined]
        assert value is None


def test_atomic_success_path_persists_write(repo: object) -> None:
    """A write performed inside the boundary persists on normal exit."""
    category = Category(category_id=uuid4(), name="Inside atomic")
    with repo.atomic():  # type: ignore[attr-defined]
        repo.save_category(category)  # type: ignore[attr-defined]
    assert repo.get_category(category.category_id) == category  # type: ignore[attr-defined]
