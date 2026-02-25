"""CLI configuration loading for taxomesh.

Resolves the taxomesh.toml config file path, delegates all repository
construction to TaxomeshService, and returns a BuildResult containing the
configured TaxomeshService and associated metadata for use by CLI commands.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from taxomesh import TaxomeshService
from taxomesh.exceptions import TaxomeshConfigError, TaxomeshRepositoryError
from taxomesh.ports.repository import TaxomeshRepositoryBase

_CONFIG_FILENAME: Final[str] = "taxomesh.toml"


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
    """Resolve taxomesh.toml and return a fully-configured BuildResult.

    Resolves the config file path and delegates repository construction to
    TaxomeshService. On configuration or repository errors, prints a message
    to stderr and exits with code 1.

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
    try:
        svc = TaxomeshService(config_path=resolved)
    except (TaxomeshConfigError, TaxomeshRepositoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    return BuildResult(
        service=svc,
        repository=svc.repository,
        config_file_path=resolved,
        config_file_exists=config_file_exists,
    )
