"""A data migration changes the database being migrated, and no other.

``migrate --database other`` runs each migration on ``other``: its data steps read and write
through that connection, not through ``default``. The external-id migration also takes rows that
hold no external id: its column accepts NULL before their empty ids become NULL, and turns unique
after. Each case runs ``_two_databases.py`` in a process of its own, with two SQLite files, so the
second database stays out of the other Django tests.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("django", reason="Django is not installed")

REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER = "tests.contrib.django._two_databases"


# Any: the helper's JSON, whose shape each case knows.
def _run(directory: Path, case: str) -> Any:
    """Run one case of the helper and return what it printed."""
    env = {key: value for key, value in os.environ.items() if key != "DJANGO_SETTINGS_MODULE"}
    result = subprocess.run(
        [sys.executable, "-m", HELPER, str(directory), case],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_root_invariant_migration_changes_only_the_database_it_migrates(tmp_path: Path) -> None:
    held = _run(tmp_path, "root-invariant")
    seeded = ["Bop -> Jazz", "Bop -> __root__", "Jazz -> __root__", "Song -> __root__"]

    assert held["default"] == {"before": seeded, "after": seeded, "recorded": False}
    assert held["other"] == {
        "before": seeded,
        "after": ["Bop -> Jazz", "Jazz -> __root__", "Orphan -> __root__"],
        "recorded": True,
    }


def test_the_external_id_migration_nulls_an_empty_id_only_in_the_database_it_migrates(tmp_path: Path) -> None:
    assert _run(tmp_path, "empty-external-ids") == {
        "default": {"ItemModel": ["", ""], "CategoryModel": ["", ""]},
        "other": {"ItemModel": [None, None], "CategoryModel": [None, None]},
    }


def test_the_external_id_migration_reversed_changes_only_the_database_it_migrates(tmp_path: Path) -> None:
    assert _run(tmp_path, "null-external-ids") == {
        "default": {"ItemModel": [None, None], "CategoryModel": [None, None]},
        "other": {"ItemModel": ["", ""], "CategoryModel": ["", ""]},
    }


def test_every_migration_runs_on_a_database_that_alone_holds_taxomesh(tmp_path: Path) -> None:
    tables = _run(tmp_path, "only-other")

    assert tables["default"] == []
    assert "taxomesh_category" in tables["other"]
