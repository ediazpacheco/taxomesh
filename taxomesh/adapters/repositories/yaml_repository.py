"""File-backed YAML repository for taxomesh.

The store is one YAML document in one file, read once when the repository is built and written
whole after every write. :class:`~taxomesh.adapters.repositories._file.FileRepositoryBase` holds the
port; this module says how YAML text becomes data and back.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import yaml

from taxomesh.adapters.repositories._file import FileRepositoryBase

DEFAULT_YAML_PATH: Final[Path] = Path("data/taxomesh.yaml")

# The value of ``type`` in the ``[repository]`` section of ``taxomesh.toml`` that selects this backend.
YAML_REPO_TYPE: Final[str] = "yaml"


class YamlRepository(FileRepositoryBase):
    """A repository that stores taxomesh data in a YAML file.

    Every row and every link is in one YAML document. The repository reads the file once, when it
    is built, and writes the file atomically after every write.

    It reads and writes only with PyYAML's safe loader and dumper, so the content of a file cannot
    make it build an arbitrary Python object. It uses libyaml's, ``CSafeLoader`` and ``CSafeDumper``,
    when PyYAML has libyaml, as its wheels do: they are many times faster on a large store.

    Args:
        path: The path of the storage file. The default is ``data/taxomesh.yaml`` in the working
            directory. The repository creates the parent directories that are missing.

    Raises:
        TaxomeshRepositoryError: If ``path`` is a directory, if the file exists but cannot be
            read or parsed, or if a new file cannot be written.
    """

    def __init__(self, path: Path | str = DEFAULT_YAML_PATH) -> None:
        """Load the store from the file at ``path``, or create the file when it is not there.

        Args:
            path: The path of the storage file. The default is ``data/taxomesh.yaml`` in the
                working directory.

        Raises:
            TaxomeshRepositoryError: If ``path`` is a directory, if the file exists but cannot be
                read or parsed, or if a new file cannot be written.
        """
        super().__init__(path)

    def _parse(self, text: str) -> object:
        """Return the document a YAML text holds; an empty file holds an empty store."""
        loader = yaml.CSafeLoader if yaml.__with_libyaml__ else yaml.SafeLoader
        document: object = yaml.load(text, Loader=loader)
        return {} if document is None else document

    def _render(self, document: Mapping[str, object]) -> str:
        """Return a document as block-style YAML, its keys in their order and its text unescaped.

        libyaml writes a character outside the Basic Multilingual Plane, such as an emoji, as an
        escape, ``"\\U0001F3B5"``, which loads back as the character.
        """
        dumper = yaml.CSafeDumper if yaml.__with_libyaml__ else yaml.SafeDumper
        return yaml.dump(document, Dumper=dumper, default_flow_style=False, allow_unicode=True, sort_keys=False)
