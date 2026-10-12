"""The help of the commands shows every option name whole at 80 columns, the width of a narrow terminal."""

import click
import pytest
import typer.testing

from taxomesh.adapters.cli.main import app

runner = typer.testing.CliRunner(env={"COLUMNS": "80", "TERMINAL_WIDTH": "80"})


@pytest.mark.parametrize("command", [["graph"], ["category", "list"], ["item", "list"], ["item", "list-relations"]])
def test_the_help_cuts_no_option_name(command: list[str]) -> None:
    result = runner.invoke(app, [*command, "--help"])
    output = click.unstyle(result.output)

    assert result.exit_code == 0
    assert "…" not in output


def test_the_graph_help_shows_both_names_of_the_relations_option() -> None:
    output = click.unstyle(runner.invoke(app, ["graph", "--help"]).output)

    assert "--show-relations" in output
    assert "--no-show-relations" in output
