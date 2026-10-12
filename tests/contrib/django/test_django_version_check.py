"""On Django, a save conditional on a version is one ``UPDATE`` filtered on that version.

The statement's row count is the comparison: no row matched means the stored row is at another
version, or is gone. No read comes before the write, so no other writer can land between the
comparison and the write, and two services holding one version cannot both succeed.
"""

from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.domain.models import Category, Item  # noqa: E402
from taxomesh.exceptions import TaxomeshVersionConflictError  # noqa: E402

pytestmark = pytest.mark.django_db


@pytest.fixture()
def repo() -> DjangoRepository:
    return DjangoRepository()


def _statements(captured: CaptureQueriesContext) -> tuple[list[str], list[str]]:
    """Return the captured ``UPDATE`` and ``SELECT`` statements."""
    sql = [query["sql"] for query in captured.captured_queries]
    return [s for s in sql if s.startswith("UPDATE")], [s for s in sql if s.startswith("SELECT")]


def test_a_category_save_at_the_expected_version_is_one_update(repo: DjangoRepository) -> None:
    row = Category(category_id=uuid4(), name="Tango")
    repo.save_category(row)
    with CaptureQueriesContext(connection) as captured:
        stored = repo.save_category(row.model_copy(update={"name": "Milonga"}), expected_version=0)
    updates, selects = _statements(captured)
    assert (len(updates), selects) == (1, [])
    assert '"version" = 0' in updates[0]
    assert (stored.name, stored.version) == ("Milonga", 1)


def test_a_stale_category_version_is_refused_by_the_same_update(repo: DjangoRepository) -> None:
    row = Category(category_id=uuid4(), name="Tango")
    repo.save_category(row)
    repo.save_category(row.model_copy(update={"name": "Milonga"}), expected_version=0)
    with CaptureQueriesContext(connection) as captured, pytest.raises(TaxomeshVersionConflictError):
        repo.save_category(row.model_copy(update={"name": "Vals"}), expected_version=0)
    updates, selects = _statements(captured)
    assert (len(updates), selects) == (1, [])
    stored = repo.find_category(row.category_id)
    assert stored is not None
    assert (stored.name, stored.version) == ("Milonga", 1)


def test_a_stale_item_version_is_refused_by_one_update(repo: DjangoRepository) -> None:
    row = Item(item_id=uuid4(), name="Percanta")
    repo.save_item(row)
    repo.save_item(row.model_copy(update={"name": "Mina"}), expected_version=0)
    with CaptureQueriesContext(connection) as captured, pytest.raises(TaxomeshVersionConflictError):
        repo.save_item(row.model_copy(update={"name": "Paica"}), expected_version=0)
    updates, selects = _statements(captured)
    assert (len(updates), selects) == (1, [])
    stored = repo.find_item(row.item_id)
    assert stored is not None
    assert (stored.name, stored.version) == ("Mina", 1)


def test_two_services_holding_one_version_cannot_both_succeed() -> None:
    """The second writer read the row before the first wrote it, and is refused."""
    first = TaxomeshService(repository=DjangoRepository())
    second = TaxomeshService(repository=DjangoRepository())
    created = first.items.create("Percanta")
    held = second.items[created.item_id]
    first.items.update(created.item_id, name="Mina", expected_version=held.version)
    with pytest.raises(TaxomeshVersionConflictError):
        second.items.update(created.item_id, name="Paica", expected_version=held.version)
    assert first.items[created.item_id].name == "Mina"
