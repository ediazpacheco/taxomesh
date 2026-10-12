"""The four removal commands say what is true after the call, whether or not the link was stored.

Removing an absent link is a no-op, so a command that printed "Removed …" would report an act that
did not happen. Each command prints the state it leaves, which is the same line in both cases.
"""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
import typer.testing

from taxomesh import TaxomeshService
from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _run(repo: InMemoryRepository, arguments: list[str]) -> tuple[int, str]:
    result_of_build = BuildResult(
        service=TaxomeshService(repository=repo),
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=False,
    )
    with patch("taxomesh.adapters.cli.main.build", return_value=result_of_build):
        result = runner.invoke(app, arguments)
    return result.exit_code, result.output


def _cases(service: TaxomeshService) -> dict[str, tuple[list[str], str, Callable[[], object]]]:
    """Return, for each command: its arguments, the line it prints, and the call that stores its link."""
    parent = service.categories.create("Parent")
    child = service.categories.create("Child")
    item = service.items.create("Piece")
    other = service.items.create("Other")
    tag = service.tags.create("live")
    c, p, i, o, t = child.category_id, parent.category_id, item.item_id, other.item_id, tag.tag_id
    ids: tuple[UUID, ...] = (c, p, i, o, t)
    assert len(set(ids)) == len(ids)
    return {
        "remove-parent": (
            ["category", "remove-parent", str(c), "--parent-id", str(p)],
            f"Category {c} has no parent {p}",
            lambda: service.categories.add_parent(child, parent),
        ),
        "remove-from": (
            ["item", "remove-from", str(i), "--category-id", str(p)],
            f"Item {i} is not in category {p}",
            lambda: service.items.place_in(item, parent),
        ),
        "untag": (
            ["item", "untag", str(i), "--tag-id", str(t)],
            f"Item {i} has no tag {t}",
            lambda: service.items.tag(item, tag),
        ),
        "unrelate": (
            ["item", "unrelate", str(i), str(o), "covers"],
            f"No relation {i} --[covers]--> {o}",
            lambda: service.items.relate(item, other, "covers"),
        ),
    }


@pytest.mark.parametrize("command", ["remove-parent", "remove-from", "untag", "unrelate"])
class TestARemovalCommandPrintsTheStateItLeaves:
    def test_when_the_link_was_stored(self, command: str) -> None:
        repo = InMemoryRepository()
        arguments, line, store = _cases(TaxomeshService(repository=repo))[command]
        store()

        exit_code, output = _run(repo, arguments)

        assert exit_code == 0
        assert output.splitlines() == [line]

    def test_when_the_link_was_not_stored(self, command: str) -> None:
        repo = InMemoryRepository()
        arguments, line, _ = _cases(TaxomeshService(repository=repo))[command]

        exit_code, output = _run(repo, arguments)

        assert exit_code == 0
        assert output.splitlines() == [line]
        assert "Removed" not in output
