"""Pre-flight smoke tests verifying all repository backends support parity operations.

File-based smoke tests (JSON, YAML) must PASS before the parametrized service fixture
is wired up. If either fails, the backend has a bug that must be fixed first.

The Django smoke test passes when Django is configured, or skips when it is absent.
"""

from pathlib import Path

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.application.service import TaxomeshService


def test_json_backend_parity_smoke(tmp_path: Path) -> None:
    """JsonRepository must support create/retrieve by id and by slug — core parity operations."""
    svc = TaxomeshService(repository=JsonRepository(tmp_path / "t.json"))
    cat = svc.create_category("Smoke", slug="smoke")
    assert svc.get_category(cat.category_id).name == "Smoke"
    assert svc.get_category_by_slug("smoke").name == "Smoke"


def test_yaml_backend_parity_smoke(tmp_path: Path) -> None:
    """YAMLRepository must support create/retrieve by id and by slug — core parity operations."""
    svc = TaxomeshService(repository=YAMLRepository(tmp_path / "t.yaml"))
    cat = svc.create_category("Smoke", slug="smoke")
    assert svc.get_category(cat.category_id).name == "Smoke"
    assert svc.get_category_by_slug("smoke").name == "Smoke"


@pytest.mark.django_db
def test_django_backend_parity_smoke() -> None:
    """DjangoRepository must support create/retrieve by id and by slug — core parity operations.

    Skips automatically when Django is not installed.
    """
    pytest.importorskip("django")
    from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: PLC0415

    svc = TaxomeshService(repository=DjangoRepository())
    cat = svc.create_category("Smoke", slug="smoke")
    assert svc.get_category(cat.category_id).name == "Smoke"
    assert svc.get_category_by_slug("smoke").name == "Smoke"
