"""Execute the runnable code examples of every user documentation page.

A clean environment must be able to copy each example and run it. The pages are ``README.md`` and
every ``docs/*.md``. A page's fenced ``python`` blocks are concatenated in document order and
executed in an isolated temporary working directory; a block tagged ``python notest`` is an
illustrative fragment and is left out. ``RUNNABLE_BLOCKS`` pins how many blocks each page runs, and
each test id reports it: a block dropped or tagged ``notest`` fails the build until the count is
changed on purpose, and a new page fails until it is registered.

The command line runs against the Typer application: once with commands that need no identifier,
and once with every command, against identifiers read back from the CLI's own output.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.testing

from taxomesh.adapters.cli.main import app
from tests.docs._reference import REPO_ROOT, cli_command_paths

# Fenced ``python`` blocks. The info string after ``python`` (e.g. " notest") selects
# whether the block participates in the runnable script.
_PYTHON_BLOCK = re.compile(
    r"^```python(?P<info>[^\n]*)\n(?P<code>.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)

# Every documentation page, with the number of python blocks it runs.
RUNNABLE_BLOCKS = {
    "README.md": 1,
    "docs/cli.md": 0,
    "docs/configuration.md": 0,
    "docs/design.md": 4,
    "docs/django-integration.md": 2,
    "docs/http-api-integration.md": 2,
    "docs/python-api.md": 18,
    "docs/repositories.md": 1,
}


def _pages() -> list[str]:
    """``README.md`` and every page under ``docs/``, as paths from the repository root."""
    return sorted(["README.md", *(f"docs/{page.name}" for page in (REPO_ROOT / "docs").glob("*.md"))])


def _runnable_blocks(markdown: str) -> list[str]:
    """Every fenced python block that is not tagged ``notest``, in document order."""
    return [m.group("code") for m in _PYTHON_BLOCK.finditer(markdown) if "notest" not in m.group("info")]


def test_every_page_has_a_pinned_count() -> None:
    assert _pages() == sorted(RUNNABLE_BLOCKS), "register every documentation page in RUNNABLE_BLOCKS"


@pytest.mark.parametrize(
    "rel_path",
    sorted(RUNNABLE_BLOCKS),
    ids=[f"{page}, {count} block{'' if count == 1 else 's'}" for page, count in sorted(RUNNABLE_BLOCKS.items())],
)
def test_doc_python_examples_run(rel_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = REPO_ROOT / rel_path
    blocks = _runnable_blocks(path.read_text(encoding="utf-8"))
    expected = RUNNABLE_BLOCKS[rel_path]
    assert len(blocks) == expected, f"{rel_path} runs {len(blocks)} python blocks; RUNNABLE_BLOCKS pins {expected}"
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {"__name__": "__doc_example__"}
    exec(compile("\n\n".join(blocks), str(path), "exec"), namespace)


def test_cli_examples_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The commands that need no identifier run cleanly, the global ``--verbose`` included."""
    monkeypatch.chdir(tmp_path)
    runner = typer.testing.CliRunner()
    commands = [
        ["category", "create", "--name", "Music"],
        ["category", "list"],
        ["category", "roots"],
        ["item", "create", "--name", "Kind of Blue", "--external-id", "catalog:42"],
        ["tag", "create", "--name", "classic"],
        ["tag", "list"],
        ["graph"],
        ["--verbose", "category", "list"],
    ]
    for cmd in commands:
        result = runner.invoke(app, cmd)
        assert result.exit_code == 0, f"`taxomesh {' '.join(cmd)}` failed:\n{result.output}"


# A command prints each row as its label, ``<name> (id: <uuid>)``.
_MODEL_ID = re.compile(r"\(id: ([0-9a-f-]{36})")


def _run(runner: typer.testing.CliRunner, cmd: list[str]) -> str:
    """Invoke one documented command, require it to succeed, and return its output."""
    result = runner.invoke(app, cmd)
    assert result.exit_code == 0, f"`taxomesh {' '.join(cmd)}` failed:\n{result.output}"
    return result.output


def _captured_id(pattern: re.Pattern[str], output: str, what: str) -> str:
    """Read an identifier back out of what the CLI just printed."""
    match = pattern.search(output)
    assert match is not None, f"could not read the {what} id from:\n{output}"
    return match.group(1)


def test_every_cli_command_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every command of the application runs, against real identifiers.

    A command naming a row needs an identifier that does not exist until something has been
    created, which is why ``docs/cli.md`` writes it as a placeholder. Creating the rows here and
    reading their identifiers back out of the CLI's own output lets each command run as the page
    spells it. The last assertion checks that no command of the application was left out.
    """
    monkeypatch.chdir(tmp_path)
    runner = typer.testing.CliRunner()
    ran: list[list[str]] = []

    def run(cmd: list[str]) -> str:
        ran.append(cmd)
        return _run(runner, cmd)

    category_id = _captured_id(_MODEL_ID, run(["category", "create", "--name", "Music"]), "category")
    item_id = _captured_id(_MODEL_ID, run(["item", "create", "--name", "Kind of Blue"]), "item")
    other_id = _captured_id(_MODEL_ID, run(["item", "create", "--name", "Blue in Green"]), "item")
    tag_id = _captured_id(_MODEL_ID, run(["tag", "create", "--name", "classic"]), "tag")

    child_id = _captured_id(_MODEL_ID, run(["category", "create", "--name", "Jazz"]), "child category")
    run(["category", "add-parent", child_id, "--parent-id", category_id])
    run(["category", "list", "--parent-id", category_id])
    run(["category", "update", child_id, "--name", "World Music"])
    run(["item", "place-in", item_id, "--category-id", child_id])
    run(["item", "list", "--category-id", category_id, "--recursive"])
    run(["item", "tag", item_id, "--tag-id", tag_id])
    run(["tag", "list", "--item-id", item_id])
    run(["item", "list", "--tag-id", tag_id])
    run(["item", "relate", item_id, other_id, "covers"])
    run(["item", "list-relations", item_id])
    run(["item", "list-related", item_id])
    run(["item", "unrelate", item_id, other_id, "covers"])
    run(["item", "untag", item_id, "--tag-id", tag_id])
    run(["item", "remove-from", item_id, "--category-id", child_id])
    run(["item", "update", item_id, "--disable"])
    run(["category", "remove-parent", child_id, "--parent-id", category_id])
    run(["item", "delete", item_id])
    run(["category", "delete", child_id])
    run(["category", "roots"])
    run(["tag", "update", tag_id, "--name", "classics"])
    run(["tag", "delete", tag_id])
    run(["graph"])
    run(["version"])

    missing = [path for path in cli_command_paths() if not any(cmd[: len(path)] == list(path) for cmd in ran)]
    assert not missing, f"these commands never ran: {missing}"
