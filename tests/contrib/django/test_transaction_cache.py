"""A service caches no read made inside a transaction, so it serves no row that is rolled back or not committed.

A Django transaction sees its own writes before they commit, and a rollback takes them back. So a
read inside one is neither stored in the service's cache nor served from it: no lookup, listing or
search corpus. Outside a transaction, a read is cached as before. The cases run in
``_transaction_cache.py``, in a process of its own, so that "outside a transaction" is real.
"""

from typing import Any

import pytest

pytest.importorskip("django", reason="Django is not installed")

from django.db import transaction  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from tests.contrib.django._process import run_helper  # noqa: E402


@pytest.fixture(scope="module")
def held(tmp_path_factory: pytest.TempPathFactory) -> Any:
    return run_helper("tests.contrib.django._transaction_cache", str(tmp_path_factory.mktemp("transaction_cache")))


def test_a_transaction_reads_its_own_writes(held: Any) -> None:
    assert held["rolled back"]["inside"] == {"item": True, "listed": ["Phantom category"], "found": ["Phantom"]}


def test_nothing_that_a_rolled_back_transaction_read_is_served_afterwards(held: Any) -> None:
    after = {key: value for key, value in held["rolled back"].items() if key != "inside"}
    assert after == {"by external id": False, "item": False, "category": False, "listed": [], "found": []}


def test_another_thread_never_reads_a_row_that_is_not_committed(held: Any) -> None:
    assert held["uncommitted"] == {
        "A": True,
        "B in a transaction": False,
        "B while A is open": False,
        "after A rolled back": False,
    }


def test_outside_a_transaction_a_read_is_cached_as_before(held: Any) -> None:
    assert held["cached"] == {"reads": ["find_item"]}


@pytest.mark.django_db(transaction=True)
def test_django_is_in_a_transaction_inside_the_callers_block_and_while_autocommit_is_off() -> None:
    repo = DjangoRepository()
    with transaction.atomic():
        in_block = repo.in_transaction
    transaction.set_autocommit(False)
    try:
        without_autocommit = repo.in_transaction
    finally:
        transaction.rollback()
        transaction.set_autocommit(True)

    assert (in_block, without_autocommit, repo.in_transaction) == (True, True, False)


def test_reading_whether_a_transaction_is_open_opens_no_connection(held: Any) -> None:
    assert held["closed"] == {"in transaction": False, "connected": False}
