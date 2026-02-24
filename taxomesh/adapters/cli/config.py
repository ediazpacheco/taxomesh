"""CLI configuration loading for taxomesh.

Reads taxomesh.toml from the current working directory (or a supplied override
path), constructs the appropriate repository adapter, and returns a BuildResult
containing the configured TaxomeshService and associated metadata for use by
CLI commands.
"""

import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from taxomesh import TaxomeshService
from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YAMLRepository
from taxomesh.exceptions import TaxomeshRepositoryError
from taxomesh.ports.repository import TaxomeshRepositoryBase

_CONFIG_FILENAME = "taxomesh.toml"
_DEFAULT_REPO_TYPE = "yaml"
_DEFAULT_REPO_PATH = "taxomesh.yaml"


@dataclass
class BuildResult:
    """Result returned by the CLI build() factory.

    Bundles the ready-to-use service, underlying repository adapter, and config
    file metadata so sub-commands can display verbose diagnostic information.

    Attributes:
        service: Fully configured TaxomeshService ready for use.
        repository: The underlying repository adapter instance.
        config_file_path: Absolute, resolved path to the TOML config file.
            The file may or may not exist on disk.
        config_file_exists: True if config_file_path existed on disk at the
            time build() was called; False otherwise.
    """

    service: TaxomeshService
    repository: TaxomeshRepositoryBase
    config_file_path: Path
    config_file_exists: bool


def build(config_path: Path | None = None) -> BuildResult:
    """Read taxomesh.toml and return a fully-configured BuildResult.

    Resolves the config file path, reads repository settings from it if present,
    constructs the repository adapter and service, and returns all artefacts
    bundled in a BuildResult for use by CLI sub-commands.

    Args:
        config_path: Explicit path to taxomesh.toml. If None, resolves
            taxomesh.toml relative to the current working directory.

    Returns:
        BuildResult containing the TaxomeshService, repository adapter,
        absolute config file path, and a flag indicating whether the config
        file exists on disk.
    """
    resolved = (config_path if config_path is not None else Path.cwd() / _CONFIG_FILENAME).resolve()
    config_file_exists = resolved.exists()
    repo_type = _DEFAULT_REPO_TYPE
    repo_path = _DEFAULT_REPO_PATH
    if config_file_exists:
        try:
            config = tomllib.loads(resolved.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            print(f"Error: could not parse config file {resolved}: {exc}", file=sys.stderr)
            sys.exit(1)
        section = config.get("repository", {})
        repo_type = section.get("type", _DEFAULT_REPO_TYPE)
        repo_path = section.get("path", _DEFAULT_REPO_PATH)
    if repo_type == "yaml":
        try:
            repo: JsonRepository | YAMLRepository = YAMLRepository(Path(repo_path))
        except TaxomeshRepositoryError as exc:
            print(f"Error: could not open repository: {exc}", file=sys.stderr)
            sys.exit(1)
    elif repo_type == "json":
        try:
            repo = JsonRepository(Path(repo_path))
        except TaxomeshRepositoryError as exc:
            print(f"Error: could not open repository: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print(
            f"Error: unsupported repository type '{repo_type}'. Supported: 'yaml', 'json'.",
            file=sys.stderr,
        )
        sys.exit(1)
    svc = TaxomeshService(repository=repo)
    return BuildResult(
        service=svc,
        repository=repo,
        config_file_path=resolved,
        config_file_exists=config_file_exists,
    )
