"""The command line over Django sets Django up itself, and names a settings module it cannot import.

Each case runs the command in a process of its own: the suite configures Django in its own process,
so a case in it would not find an application registry that nobody set up.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("django", reason="Django is not installed")
pytest.importorskip("typer", reason="the cli extra is not installed")

REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = """\
INSTALLED_APPS = ["django.contrib.contenttypes", "taxomesh.contrib.django"]
DATABASES = {{"default": {{"ENGINE": "django.db.backends.sqlite3", "NAME": {database!r}}}}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A directory with ``taxomesh.toml`` for Django and a settings module on a SQLite file."""
    (tmp_path / "taxomesh.toml").write_text('[repository]\ntype = "django"\n', encoding="utf-8")
    (tmp_path / "cli_settings.py").write_text(SETTINGS.format(database=str(tmp_path / "db.sqlite3")), encoding="utf-8")
    return tmp_path


def _run(project: Path, settings: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "GITHUB_ACTIONS"}
    env["DJANGO_SETTINGS_MODULE"] = settings
    env["PYTHONPATH"] = os.pathsep.join([str(project), str(REPO_ROOT)])
    return subprocess.run(
        [sys.executable, "-c", "from taxomesh.adapters.cli import run; run()", *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_command_creates_and_lists_a_row_through_django(project: Path) -> None:
    migrate = subprocess.run(
        [sys.executable, "-m", "django", "migrate", "--verbosity", "0"],
        cwd=project,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "cli_settings",
            "PYTHONPATH": os.pathsep.join([str(project), str(REPO_ROOT)]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert migrate.returncode == 0, migrate.stderr

    created = _run(project, "cli_settings", "category", "create", "--name", "Music")
    assert created.returncode == 0, created.stderr
    listed = _run(project, "cli_settings", "category", "list")
    assert listed.returncode == 0, listed.stderr
    assert "Music" in listed.stdout


def test_a_settings_module_that_cannot_be_imported_is_named(project: Path) -> None:
    result = _run(project, "no_such_settings", "category", "list")
    assert result.returncode == 1
    assert "no_such_settings" in result.stderr
    assert "Traceback" not in result.stderr
    assert "not installed" not in result.stderr
