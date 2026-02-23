"""CLI configuration loading for taxomesh.

Reads taxomesh.toml from the current working directory (or a supplied override
path), constructs the appropriate repository adapter, and returns a configured
TaxomeshService ready for use by CLI commands.
"""

import sys
import tomllib
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.exceptions import TaxomeshRepositoryError

_CONFIG_FILENAME = "taxomesh.toml"
_DEFAULT_REPO_TYPE = "json"
_DEFAULT_REPO_PATH = "taxomesh.json"


def build_service(config_path: Path | None = None) -> TaxomeshService:
    """Read taxomesh.toml and return a fully-configured TaxomeshService."""
    resolved = config_path if config_path is not None else Path.cwd() / _CONFIG_FILENAME
    repo_type = _DEFAULT_REPO_TYPE
    repo_path = _DEFAULT_REPO_PATH
    if resolved.exists():
        try:
            config = tomllib.loads(resolved.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            print(f"Error: could not parse config file {resolved}: {exc}", file=sys.stderr)
            sys.exit(1)
        section = config.get("repository", {})
        repo_type = section.get("type", _DEFAULT_REPO_TYPE)
        repo_path = section.get("path", _DEFAULT_REPO_PATH)
    if repo_type != "json":
        print(
            f"Error: unsupported repository type '{repo_type}'. Only 'json' is supported in this version.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        repo = JsonRepository(Path(repo_path))
    except TaxomeshRepositoryError as exc:
        print(f"Error: could not open repository: {exc}", file=sys.stderr)
        sys.exit(1)
    return TaxomeshService(repository=repo)
