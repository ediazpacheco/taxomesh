"""A Django write that fails as its transaction opens or commits raises ``TaxomeshRepositoryError``.

The service runs each write in one ``atomic()`` block. When the database fails as the block opens, as
when it cannot be reached, or as it commits, as when SQLite refuses the lock that a commit needs, the
error is a ``TaxomeshRepositoryError`` whose cause is the database's error. An error that the body of a
block raises keeps its type: the caller's own ORM error, or any other exception. The failures run in
``_transaction_failures.py``, in a process of its own, so that the transaction commits for real.
"""

from pathlib import Path

import pytest

pytest.importorskip("django", reason="Django is not installed")

from django.db import OperationalError, connection

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.exceptions import TaxomeshValidationError
from tests.contrib.django._process import Printed, run_helper

HELPER = "tests.contrib.django._transaction_failures"
WRITES = ("categories.create", "categories.update", "items.create", "items.place_in", "tags.create", "tags.delete")
REPOSITORY_ERROR = {"error": "TaxomeshRepositoryError", "taxomesh": True, "cause": "OperationalError"}


@pytest.fixture(scope="module")
def unreachable(tmp_path_factory: pytest.TempPathFactory) -> Printed:
    return run_helper(HELPER, str(tmp_path_factory.mktemp("unreachable")), "unreachable")


@pytest.mark.parametrize("write", WRITES)
def test_a_write_raises_a_repository_error_when_the_database_cannot_be_reached(
    write: str, unreachable: Printed
) -> None:
    assert unreachable[write] == REPOSITORY_ERROR


def test_a_write_whose_commit_the_database_refuses_raises_a_repository_error_and_stores_nothing(
    tmp_path: Path,
) -> None:
    held = run_helper(HELPER, str(tmp_path), "locked-commit")

    assert held["outcome"] == REPOSITORY_ERROR
    assert "INSERT" in held["completed"], "the write's statements ran, so the commit is what failed"
    assert held["stored"] == []


@pytest.mark.django_db
@pytest.mark.parametrize("raised", [ValueError("body"), KeyboardInterrupt(), TaxomeshValidationError("body")])
def test_an_error_that_the_body_of_a_block_raises_keeps_its_type(raised: BaseException) -> None:
    with pytest.raises(type(raised)) as caught, DjangoRepository().atomic():
        raise raised

    assert caught.value is raised


@pytest.mark.django_db
def test_a_database_error_of_the_callers_own_query_inside_a_block_keeps_its_type() -> None:
    with pytest.raises(OperationalError), DjangoRepository().atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT * FROM a_table_that_is_not_there")
