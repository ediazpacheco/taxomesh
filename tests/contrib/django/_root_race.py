"""Build two services at the same moment on a Django database that holds no implicit root, and print the outcomes.

``python -m tests.contrib.django._root_race <directory>`` builds two SQLite databases, ``default`` and
``other``, as files in ``<directory>``, and migrates both. On each alias it deletes the implicit root
that the migrations stored, runs the forced schedule of ``tests/service/_root_race.py`` with two
``DjangoRepository`` on that alias, and then the natural race ``ROUNDS`` times, each round on a store
with no root. Each thread opens a connection of its own and closes it at its end. It runs in a
process of its own: the suite's test database is SQLite in memory, which refuses a second writer at
once instead of making it wait. It prints one JSON object, by alias.
"""

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Final

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connections

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from tests.service._root_race import race_naturally, start_together

ALIASES: Final[tuple[str, ...]] = ("default", "other")

# How many times the natural race runs on each alias.
ROUNDS: Final[int] = 20


def _configure(directory: Path) -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "taxomesh.contrib.django"],
        DATABASES={
            alias: {"ENGINE": "django.db.backends.sqlite3", "NAME": str(directory / f"{alias}.sqlite3")}
            for alias in ALIASES
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()
    for alias in ALIASES:
        call_command("migrate", database=alias, verbosity=0)


def _empty(alias: str) -> None:
    """Delete every row of the alias's store, the implicit root included."""
    call_command("flush", database=alias, interactive=False, verbosity=0)


def _race(alias: str) -> dict[str, object]:
    _empty(alias)
    forced = start_together(
        DjangoRepository, lambda: DjangoRepository(alias), lambda: DjangoRepository(alias), connections.close_all
    )
    natural: Counter[str] = Counter()
    for _ in range(ROUNDS):
        _empty(alias)
        natural[race_naturally(lambda: DjangoRepository(alias), connections.close_all)] += 1
    return {"forced": forced, "natural": dict(natural)}


def main(directory: str) -> None:
    _configure(Path(directory))
    print(json.dumps({alias: _race(alias) for alias in ALIASES}))


if __name__ == "__main__":
    main(*sys.argv[1:])
