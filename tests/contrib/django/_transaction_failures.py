"""Make a Django write fail as its transaction opens or commits, and print the outcomes as JSON.

``python -m tests.contrib.django._transaction_failures <directory> <case>`` builds one SQLite database,
a file in ``<directory>``, migrates it and builds a service over it. It runs in a process of its own,
so that a write's transaction opens and commits for real: each test of the suite runs inside a
transaction that is never committed.

- ``unreachable``: after the service stores a few rows, the database's file goes out of reach, so
  each write fails as its transaction opens.
- ``locked-commit``: a second connection holds a read transaction, so the write's ``COMMIT`` cannot
  take the write lock of the database, and fails when the writer's short timeout ends.
"""

import json
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Final

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.backends.utils import CursorWrapper

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshError

# How long the writer waits for a lock, in seconds: short, so that the refused commit fails soon.
TIMEOUT: Final[float] = 0.2

type Outcome = dict[str, str | bool | None]


def _configure(database: Path) -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "taxomesh.contrib.django"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str(database),
                "OPTIONS": {"timeout": TIMEOUT},
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()
    call_command("migrate", verbosity=0)


def _outcome(call: Callable[[], object]) -> Outcome:
    """How the call ended: the class of its error, whether that is a taxomesh error, and its cause's class."""
    try:
        call()
    except Exception as exc:
        cause = exc.__cause__
        return {
            "error": type(exc).__name__,
            "taxomesh": isinstance(exc, TaxomeshError),
            "cause": None if cause is None else type(cause).__name__,
        }
    return {"error": None, "taxomesh": False, "cause": None}


def unreachable(svc: TaxomeshService, database: Path) -> dict[str, object]:
    """Each write's outcome once the database's file is out of reach."""
    category = svc.categories.create("C")
    item = svc.items.create("I")
    tag = svc.tags.create("T")
    connection.close()
    connection.settings_dict["NAME"] = str(database.parent / "missing" / database.name)
    writes: dict[str, Callable[[], object]] = {
        "categories.create": lambda: svc.categories.create("X"),
        "categories.update": lambda: svc.categories.update(category, name="Y"),
        "items.create": lambda: svc.items.create("X"),
        "items.place_in": lambda: svc.items.place_in(item, category),
        "tags.create": lambda: svc.tags.create("X"),
        "tags.delete": lambda: svc.tags.delete(tag),
    }
    return {name: _outcome(write) for name, write in writes.items()}


def locked_commit(svc: TaxomeshService, database: Path) -> dict[str, object]:
    """The outcome of a write whose commit the database refuses, the statements that ran, and what is stored."""
    completed: list[str] = []

    def record(
        execute: Callable[..., object], sql: str, params: object, many: bool, context: dict[str, CursorWrapper]
    ) -> object:
        result = execute(sql, params, many, context)
        completed.append(sql.split(maxsplit=1)[0])
        return result

    reader = sqlite3.connect(database, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM taxomesh_category").fetchall()
        with connection.execute_wrapper(record):
            outcome = _outcome(lambda: svc.categories.create("X"))
    finally:
        reader.close()
    return {
        "outcome": outcome,
        "completed": completed,
        "stored": [category.name for category in svc.categories.list()],
    }


CASES: dict[str, Callable[[TaxomeshService, Path], dict[str, object]]] = {
    "unreachable": unreachable,
    "locked-commit": locked_commit,
}


def main(directory: str, case: str) -> None:
    database = Path(directory) / "taxomesh.sqlite3"
    _configure(database)
    print(json.dumps(CASES[case](TaxomeshService(DjangoRepository(), cache_ttl=0), database)))


if __name__ == "__main__":
    main(*sys.argv[1:])
