"""Read through a shared service inside a transaction that is rolled back, and print what it serves as JSON.

``python -m tests.contrib.django._transaction_cache <directory>`` builds one SQLite database, a file in
``<directory>``, migrates it, and runs each case on a new service with the default cache lifetime.
It runs in a process of its own, so that a read outside the caller's transaction is a read outside
any transaction, as in a view: each test of the suite runs inside a transaction of its own.

- ``rolled back``: inside the caller's ``transaction.atomic()``, an item is created and read, and a
  category is created and listed; the block rolls back; the same service is read again.
- ``uncommitted``: thread A creates and reads an item inside its open transaction; thread B, which
  shares the service and is in no transaction of its own, reads it before A ends; then A rolls back,
  and B reads again.
- ``cached``: outside a transaction, two reads of one item read storage once.
- ``closed``: with every connection closed, whether a repository is in a transaction, and whether
  asking opened a connection.
"""

import json
import sys
import threading
from pathlib import Path
from typing import Final

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.application.service import TaxomeshService
from tests.service.conftest import CountingRepository

# How long a thread waits for the other one.
WAIT: Final[float] = 10.0


class RolledBack(Exception):
    """Raised inside the caller's block to roll it back."""


def _configure(directory: Path) -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "taxomesh.contrib.django"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(directory / "taxomesh.sqlite3")}},
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()
    call_command("migrate", verbosity=0)


def rolled_back() -> dict[str, object]:
    """What a service serves after the caller's block that wrote and read through it rolls back."""
    svc = TaxomeshService(DjangoRepository())
    try:
        with transaction.atomic():
            item = svc.items.create("Phantom", external_id="phantom")
            category = svc.categories.create("Phantom category")
            inside = {
                "item": svc.items.get_by_external_id("phantom") is not None,
                "listed": [c.name for c in svc.categories.list()],
                "found": [i.name for i in svc.items.search("phantom")],
            }
            raise RolledBack
    except RolledBack:
        pass
    return {
        "inside": inside,
        "by external id": svc.items.get_by_external_id("phantom") is not None,
        "item": svc.items.get(item.item_id) is not None,
        "category": svc.categories.get(category.category_id) is not None,
        "listed": [c.name for c in svc.categories.list()],
        "found": [i.name for i in svc.items.search("phantom")],
    }


def uncommitted() -> dict[str, object]:
    """What thread B reads through a shared service while thread A's transaction is open, and after."""
    svc = TaxomeshService(DjangoRepository())
    a_has_read, b_has_read = threading.Event(), threading.Event()
    seen: dict[str, object] = {}

    def a() -> None:
        try:
            with transaction.atomic():
                svc.items.create("Uncommitted", external_id="uncommitted")
                seen["A"] = svc.items.get_by_external_id("uncommitted") is not None
                a_has_read.set()
                b_has_read.wait(WAIT)
                raise RolledBack
        except RolledBack:
            pass
        finally:
            connections.close_all()

    def b() -> None:
        a_has_read.wait(WAIT)
        seen["B in a transaction"] = svc.repository.in_transaction
        seen["B while A is open"] = svc.items.get_by_external_id("uncommitted") is not None
        b_has_read.set()
        connections.close_all()

    threads = [threading.Thread(target=a), threading.Thread(target=b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)
    seen["after A rolled back"] = svc.items.get_by_external_id("uncommitted") is not None
    return seen


def cached() -> dict[str, object]:
    """How many reads two lookups of one item make outside a transaction."""
    reads = CountingRepository(DjangoRepository())
    svc = TaxomeshService(reads)
    item = svc.items.create("Kept")
    reads.reset()
    svc.items.get(item.item_id)
    svc.items.get(item.item_id)
    return {"reads": reads.calls}


def closed() -> dict[str, object]:
    """Whether a repository is in a transaction with no connection open, and whether asking opened one."""
    connections.close_all()
    in_transaction = DjangoRepository().in_transaction
    return {"in transaction": in_transaction, "connected": connections["default"].connection is not None}


def main(directory: str) -> None:
    _configure(Path(directory))
    cases = {"rolled back": rolled_back, "uncommitted": uncommitted, "cached": cached, "closed": closed}
    print(json.dumps({name: case() for name, case in cases.items()}))


if __name__ == "__main__":
    main(*sys.argv[1:])
