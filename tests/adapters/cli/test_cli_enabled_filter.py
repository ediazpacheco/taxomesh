"""The ``--state`` filter on ``category list``, ``item list`` and ``graph``.

One vocabulary on every edge: ``--state enabled`` (the default) lists enabled rows,
``--state disabled`` lists disabled rows, ``--state all`` lists both. A two-state flag could not
ask for "disabled only".

A single enum-valued option rather than three boolean flags, deliberately: the three-flag form
needs a mutual-exclusion guard, and the paired ``--enabled/--disabled`` form was measured to
accept a contradiction silently and answer with whichever flag parsed last. Here a contradiction
cannot be written down.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer.testing

from taxomesh.adapters.cli.config import BuildResult
from taxomesh.adapters.cli.main import app
from taxomesh.application.service import TaxomeshService
from tests.service.conftest import InMemoryRepository

runner = typer.testing.CliRunner()


def _build_result(repo: InMemoryRepository) -> BuildResult:
    svc = TaxomeshService(repository=repo)
    return BuildResult(
        service=svc,
        repository=repo,
        config_file_path=Path("/fake/taxomesh.toml"),
        config_file_exists=False,
    )


def _make_repo_with_disabled_category() -> InMemoryRepository:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    svc.categories.create(name="ActiveCategory")
    cat_off = svc.categories.create(name="DisabledCategory")
    svc.categories.update(cat_off.category_id, enabled=False)
    return repo


def _make_repo_with_disabled_item() -> InMemoryRepository:
    repo = InMemoryRepository()
    svc = TaxomeshService(repository=repo)
    svc.items.create(name="ActiveItem")
    item_off = svc.items.create(name="DisabledItem")
    svc.items.update(item_off.item_id, enabled=False)
    return repo


class TestCategoryListState:
    def test_default_hides_disabled(self) -> None:
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["category", "list"])
        assert result.exit_code == 0
        assert "ActiveCategory" in result.output
        assert "DisabledCategory" not in result.output

    def test_all_shows_every_state(self) -> None:
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["category", "list", "--state", "all"])
        assert result.exit_code == 0
        assert "ActiveCategory" in result.output
        assert "DisabledCategory" in result.output

    def test_disabled_shows_only_disabled(self) -> None:
        """Disabled only, the state a two-state flag could not ask for."""
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["category", "list", "--state", "disabled"])
        assert result.exit_code == 0
        assert "DisabledCategory" in result.output
        assert "ActiveCategory" not in result.output


class TestItemListState:
    def test_default_hides_disabled(self) -> None:
        repo = _make_repo_with_disabled_item()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list"])
        assert result.exit_code == 0
        assert "ActiveItem" in result.output
        assert "DisabledItem" not in result.output

    def test_all_shows_every_state(self) -> None:
        repo = _make_repo_with_disabled_item()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list", "--state", "all"])
        assert result.exit_code == 0
        assert "ActiveItem" in result.output
        assert "DisabledItem" in result.output

    def test_disabled_shows_only_disabled(self) -> None:
        repo = _make_repo_with_disabled_item()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["item", "list", "--state", "disabled"])
        assert result.exit_code == 0
        assert "DisabledItem" in result.output
        assert "ActiveItem" not in result.output


class TestGraphState:
    def test_disabled_shows_only_disabled(self) -> None:
        """``--state disabled`` renders the disabled rows, which the tree could not show before."""
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, ["graph", "--state", "disabled"])
        assert result.exit_code == 0
        assert "DisabledCategory" in result.output
        assert "ActiveCategory" not in result.output


COMMANDS: list[list[str]] = [["category", "list"], ["item", "list"], ["graph"]]


class TestRejectsAnUnknownState:
    """Every command that takes the filter must reject a value outside the three states.

    Parametrized over all three so a command that simply forgot the option is caught: that
    failure also exits 2, and asserting only on the exit code would not tell the two apart.
    Hence the assertion on the message naming the valid choices.
    """

    @pytest.mark.parametrize("command", COMMANDS, ids=[" ".join(c) for c in COMMANDS])
    def test_unknown_state_is_refused(self, command: list[str]) -> None:
        repo = _make_repo_with_disabled_category()
        with patch("taxomesh.adapters.cli.main.build", return_value=_build_result(repo)):
            result = runner.invoke(app, [*command, "--state", "nonsense"])
        assert result.exit_code == 2
        assert "enabled" in result.output, "the error must name the valid choices, not just fail"
