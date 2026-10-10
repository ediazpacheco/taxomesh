"""Resolve the repository a service uses when it is given none.

``taxomesh.toml`` names the storage backend and where it keeps its data. Without the file, a YAML
file in ``./data/`` holds the taxonomy. This is the one module that reads the file:
``TaxomeshService`` imports it only when it is given no repository, and the command line reads the
file through it for ``--show-config``.

This module imports every adapter, so it is outside ``taxomesh.application``: the service depends
on the repository port, and this module chooses the adapter that the configuration names.
"""

import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

from taxomesh.adapters.repositories.django_repository import _USING_DEFAULT as DJANGO_USING_DEFAULT
from taxomesh.adapters.repositories.django_repository import DJANGO_REPO_TYPE, DjangoRepository
from taxomesh.adapters.repositories.json_repository import DEFAULT_JSON_PATH, JSON_REPO_TYPE, JsonRepository
from taxomesh.adapters.repositories.yaml_repository import DEFAULT_YAML_PATH, YAML_REPO_TYPE, YamlRepository
from taxomesh.exceptions import TaxomeshConfigError
from taxomesh.ports.repository import TaxomeshRepositoryBase

CONFIG_FILENAME: Final[str] = "taxomesh.toml"

# Each builder is handed the ``[repository]`` section. A file backend given no path is built
# with none, so its own module's default applies.
# Any: a TOML table's values are whatever the file holds, as tomllib types them.
_BUILDERS: Final[Mapping[str, Callable[[Mapping[str, Any]], TaxomeshRepositoryBase]]] = {
    YAML_REPO_TYPE: lambda section: YamlRepository(Path(section["path"])) if "path" in section else YamlRepository(),
    JSON_REPO_TYPE: lambda section: JsonRepository(Path(section["path"])) if "path" in section else JsonRepository(),
    DJANGO_REPO_TYPE: lambda section: DjangoRepository(using=section.get("using", DJANGO_USING_DEFAULT)),
}

SUPPORTED_REPO_TYPES: Final[tuple[str, ...]] = tuple(_BUILDERS)
"""The values ``[repository] type`` accepts."""


def config_file(config_path: Path | str | None) -> Path:
    """Return the config file to read: the one named, else ``taxomesh.toml`` in the working directory."""
    return Path(config_path) if config_path is not None else Path.cwd() / CONFIG_FILENAME


# Any: a TOML document's values are whatever the file holds, as tomllib types them.
def _read(path: Path) -> dict[str, Any]:
    """Return the parsed config file, or an empty document when there is no file.

    Raises:
        TaxomeshConfigError: If the file exists but cannot be read or parsed.
    """
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise TaxomeshConfigError(f"Could not parse config file {path}: {exc}") from exc
    except OSError as exc:
        raise TaxomeshConfigError(f"Could not read config file {path}: {exc}") from exc


# Any: a TOML document's values are whatever the file holds, as tomllib types them.
def _repository_section(document: Mapping[str, Any], path: Path) -> tuple[Mapping[str, Any], str]:
    """Return the document's ``[repository]`` section and the type it names, YAML when it names none.

    Raises:
        TaxomeshConfigError: If the section names a repository type that taxomesh does not support.
    """
    section: Mapping[str, Any] = document.get("repository", {})
    repo_type = section.get("type", YAML_REPO_TYPE)
    if repo_type not in _BUILDERS:
        supported = ", ".join(f"'{name}'" for name in SUPPORTED_REPO_TYPES)
        raise TaxomeshConfigError(
            f"Unsupported repository type '{repo_type}' in {path}: the supported types are {supported}"
        )
    return section, repo_type


def resolve_repository(config_path: Path | str | None) -> tuple[TaxomeshRepositoryBase, str | None]:
    """Build the repository the config file names, with the name the file declares.

    Args:
        config_path: The config file to read. When ``None``, ``taxomesh.toml`` in the working
            directory, which need not exist.

    Returns:
        The repository, and the file's ``[taxomesh] name``, or ``None`` when it declares none.
        Without a file, or without a ``[repository]`` section, the repository is a YAML file at
        its default path.

    Raises:
        TaxomeshConfigError: If the file cannot be read or parsed, or names a repository type that
            taxomesh does not support.
        TaxomeshRepositoryError: If the repository cannot be built.
    """
    path = config_file(config_path)
    document = _read(path)
    section, repo_type = _repository_section(document, path)
    name: str | None = document.get("taxomesh", {}).get("name")
    return _BUILDERS[repo_type](section), name


def effective_repository_config(config_path: Path | str | None) -> tuple[str, str]:
    """Return the repository type the config file resolves to, and its path or database alias.

    Builds nothing, and does not read or write storage. A file backend given no path reports the
    default path of its adapter, and a Django backend given no alias reports the default alias.

    Args:
        config_path: The config file to read. When ``None``, ``taxomesh.toml`` in the working
            directory, which need not exist.

    Returns:
        ``(repository type, path or alias)``, as the file states them or as they default.

    Raises:
        TaxomeshConfigError: If the file cannot be read or parsed, or names a repository type that
            taxomesh does not support.
    """
    path = config_file(config_path)
    section, repo_type = _repository_section(_read(path), path)
    if repo_type == DJANGO_REPO_TYPE:
        return repo_type, str(section.get("using", DJANGO_USING_DEFAULT))
    if "path" in section:
        return repo_type, str(section["path"])
    return repo_type, str(DEFAULT_JSON_PATH if repo_type == JSON_REPO_TYPE else DEFAULT_YAML_PATH)
