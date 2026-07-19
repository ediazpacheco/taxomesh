"""Execute the runnable code examples embedded in the public docs.

Guards the "repair every public example" contract: a clean environment must be able to
copy-paste each primary example and have it run. Every fenced ``python`` block in the
listed Markdown files is concatenated in document order and executed in an isolated
temporary working directory. Blocks tagged ``python notest`` are illustrative fragments
(they reference objects defined elsewhere) and are skipped.

The CLI examples are smoke-tested separately against the Typer app, since the reference
commands use ``<uuid>`` placeholders that cannot be run verbatim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.testing

from taxomesh.adapters.cli.main import app

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Fenced ``python`` blocks. The info string after ``python`` (e.g. " notest") selects
# whether the block participates in the runnable script.
_PYTHON_BLOCK = re.compile(
    r"^```python(?P<info>[^\n]*)\n(?P<code>.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)

# Docs whose runnable ``python`` blocks form a valid top-to-bottom script.
_RUNNABLE_DOCS = ["README.md", "docs/python-api.md"]


def _runnable_script(markdown: str) -> str:
    """Concatenate every fenced python block that is not tagged ``notest``."""
    blocks = [m.group("code") for m in _PYTHON_BLOCK.finditer(markdown) if "notest" not in m.group("info")]
    return "\n\n".join(blocks)


@pytest.mark.parametrize("rel_path", _RUNNABLE_DOCS)
def test_doc_python_examples_run(rel_path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _REPO_ROOT / rel_path
    script = _runnable_script(path.read_text(encoding="utf-8"))
    assert script.strip(), f"No runnable python blocks found in {rel_path}"
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {"__name__": "__doc_example__"}
    exec(compile(script, str(path), "exec"), namespace)


def test_cli_examples_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The concrete (placeholder-free) CLI commands from docs/cli.md and the README run cleanly."""
    monkeypatch.chdir(tmp_path)
    runner = typer.testing.CliRunner()
    commands = [
        ["category", "add", "--name", "Music"],
        ["category", "list"],
        ["item", "add", "--name", "Kind of Blue", "--external-id", "catalog:42"],
        ["tag", "add", "--name", "classic"],
        ["tag", "list"],
        ["graph"],
        ["--verbose", "category", "list"],
    ]
    for cmd in commands:
        result = runner.invoke(app, cmd)
        assert result.exit_code == 0, f"`taxomesh {' '.join(cmd)}` failed:\n{result.output}"
