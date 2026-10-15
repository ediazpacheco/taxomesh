"""Run a helper module of the Django tests in a process of its own, and return the JSON it prints.

A helper configures Django itself, with SQLite files of its own, so the test's settings module is left
out of its environment. A process of its own keeps those databases away from the settings that the
other Django tests share, and lets a transaction commit for real, or a second writer wait.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Any: the helper's JSON, whose shape each test knows.
type Printed = Any


def run_helper(module: str, *args: str) -> Printed:
    """Run ``python -m <module> <args>`` from the repository root and return what it printed.

    Args:
        module: The helper's module, such as ``tests.contrib.django._two_databases``.
        args: The helper's arguments.

    Returns:
        The JSON value that the helper printed.
    """
    env = {key: value for key, value in os.environ.items() if key != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)
