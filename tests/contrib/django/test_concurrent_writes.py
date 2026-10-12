"""Two Django workers that write at the same moment run one after the other.

Each worker has its own service and its own ``DjangoRepository`` over one database. ``atomic()``
starts its transaction by locking the implicit root's row, and every write reads, checks and writes
inside that block. So the second worker's write waits until the first one commits, and then reads
what it stored: it refuses a cycle or a key that the first write took, it does not bring back a link
or a row that the first write removed, and it builds on the row that the first write saved. The race
runs in ``_concurrent_writes.py``, in a process of its own, on a SQLite file, since the suite's
database cannot make a writer wait.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.service._concurrent_writes import SCHEDULES, Outcome, Schedule

pytest.importorskip("django", reason="Django is not installed")

REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER = "tests.contrib.django._concurrent_writes"


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Outcome]:
    """Race every schedule once, in one process of its own, and return each outcome by name."""
    env = {key: value for key, value in os.environ.items() if key != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-m", HELPER, str(tmp_path_factory.mktemp("concurrent_writes"))],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    held: dict[str, Outcome] = json.loads(result.stdout)
    return held


@pytest.mark.parametrize("schedule", SCHEDULES, ids=[schedule.name for schedule in SCHEDULES])
def test_the_second_workers_write_waits_for_the_first_and_sees_what_it_stored(
    outcomes: dict[str, Outcome], schedule: Schedule
) -> None:
    assert outcomes[schedule.name] == schedule.expected
