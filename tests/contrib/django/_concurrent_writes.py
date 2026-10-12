"""Race the schedules of ``tests/service/_concurrent_writes.py`` on Django, and print the outcomes as JSON.

``python -m tests.contrib.django._concurrent_writes <directory>`` builds one SQLite database, a file
in ``<directory>``, and migrates it. For each schedule it empties the database and stores a scene,
then races the two writes from two services, each over its own ``DjangoRepository``, as two workers
do. Each thread opens a connection of its own and closes it at its end. It runs in a process of its
own: the suite's test database is SQLite in memory, which refuses a second writer at once instead of
making it wait.
"""

import json
import sys
from pathlib import Path

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connections

from taxomesh.adapters.repositories.django_repository import DjangoRepository
from taxomesh.application.service import TaxomeshService
from tests.service._concurrent_writes import SCHEDULES, Outcome, build_scene, run


def _configure(directory: Path) -> None:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "taxomesh.contrib.django"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(directory / "taxomesh.sqlite3")}},
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()
    call_command("migrate", verbosity=0)


def main(directory: str) -> None:
    _configure(Path(directory))
    outcomes: dict[str, Outcome] = {}
    for schedule in SCHEDULES:
        # The rows of an earlier race would show in this race's snapshot under the same names.
        call_command("flush", interactive=False, verbosity=0)
        first = TaxomeshService(DjangoRepository())
        second = TaxomeshService(DjangoRepository())
        scene = build_scene(first)
        outcomes[schedule.name] = run(schedule, scene, first, second, finish=connections.close_all)
    print(json.dumps(outcomes))


if __name__ == "__main__":
    main(*sys.argv[1:])
