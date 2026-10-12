"""File-backed JSON repository for taxomesh.

The store is one JSON document in one file, read once when the repository is built and written
whole after every write. :class:`~taxomesh.adapters.repositories._file.FileRepositoryBase` holds the
port; this module says how JSON text becomes data and back.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from taxomesh.adapters.repositories._file import FileRepositoryBase

DEFAULT_JSON_PATH: Final[Path] = Path("data/taxomesh.json")

# The value of ``type`` in the ``[repository]`` section of ``taxomesh.toml`` that selects this backend.
JSON_REPO_TYPE: Final[str] = "json"

# The spaces each nesting level of the file is indented by.
DEFAULT_JSON_INDENT: Final[int] = 2


class JsonRepository(FileRepositoryBase):
    """A repository that stores taxomesh data in a JSON file.

    Every row and every link is in one JSON document. The repository reads the file once, when it
    is built, and writes the file atomically after every write.

    Args:
        path: The path of the storage file. The default is ``data/taxomesh.json`` in the working
            directory. The repository creates the parent directories that are missing.

    Raises:
        TaxomeshRepositoryError: If ``path`` is a directory, if the file exists but cannot be
            read or parsed, or if a new file cannot be written.
    """

    def __init__(self, path: Path | str = DEFAULT_JSON_PATH) -> None:
        """Load the store from the file at ``path``, or create the file when it is not there.

        Args:
            path: The path of the storage file. The default is ``data/taxomesh.json`` in the
                working directory.

        Raises:
            TaxomeshRepositoryError: If ``path`` is a directory, if the file exists but cannot be
                read or parsed, or if a new file cannot be written.
        """
        super().__init__(path)

    def _parse(self, text: str) -> object:
        """Return the document a JSON text holds."""
        return json.loads(text)

    def _render(self, document: Mapping[str, object]) -> str:
        """Return a document as indented JSON, its non-ASCII text written as it is."""
        return json.dumps(document, indent=DEFAULT_JSON_INDENT, ensure_ascii=False)
