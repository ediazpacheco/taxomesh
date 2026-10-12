"""The command line of taxomesh.

:func:`run` is the ``taxomesh`` console script. The command line needs typer and rich, which the
``cli`` extra installs; without them the script says so, rather than failing with a traceback.
"""

from typing import Final

CLI_EXTRA_MESSAGE: Final[str] = "taxomesh: the command line needs the cli extra: pip install 'taxomesh[cli]'"

_CLI_DEPENDENCIES: Final[frozenset[str]] = frozenset({"typer", "rich"})


def run() -> None:
    """Run the command line, or exit naming the extra when typer or rich is not installed.

    Raises:
        SystemExit: With :data:`CLI_EXTRA_MESSAGE`, which exits with status 1, when typer or
            rich cannot be imported. Any other missing module is raised as it is.
    """
    try:
        from taxomesh.adapters.cli.main import app  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        if exc.name not in _CLI_DEPENDENCIES:
            raise
        raise SystemExit(CLI_EXTRA_MESSAGE) from exc
    app()
