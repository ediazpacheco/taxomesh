"""``docs/cli.md`` and ``llms.txt`` hold blocks rendered from the code, and neither drifts.

``docs/cli.md`` lists every global option and every command of the Typer application.
``llms.txt`` states the public surface: the ledger's signatures, the constructor, the graph, the
rows and the errors. Each page's generated block must equal its rendering by
``tests/docs/_reference.py``. When one does not, regenerate it as that module's docstring says, and
read the diff: it is the change to the command line or to the surface.
"""

import re

import click

import taxomesh
from tests.docs._reference import (
    CLI_PAGE,
    LLMS_PAGE,
    cli_command_paths,
    cli_root,
    generated_block,
    render_cli_reference,
    render_llms_reference,
)


def test_cli_page_matches_the_application() -> None:
    assert generated_block(CLI_PAGE.read_text(encoding="utf-8")) == render_cli_reference()


def test_cli_page_lists_every_command_and_global_option() -> None:
    block = generated_block(CLI_PAGE.read_text(encoding="utf-8"))
    for path in cli_command_paths():
        assert f"`taxomesh {' '.join(path)}" in block, f"docs/cli.md does not list `taxomesh {' '.join(path)}`"
    for option in cli_root().params:
        assert isinstance(option, click.Option)
        assert f"`{option.opts[0]}" in block, f"docs/cli.md does not list the global option {option.opts[0]}"


def test_llms_txt_matches_the_ledger() -> None:
    assert generated_block(LLMS_PAGE.read_text(encoding="utf-8")) == render_llms_reference()


def test_llms_txt_names_every_root_export() -> None:
    text = LLMS_PAGE.read_text(encoding="utf-8")
    missing = [name for name in taxomesh.__all__ if not re.search(rf"\b{name}\b", text)]
    assert not missing, f"llms.txt never names {missing}"
