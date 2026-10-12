"""A write to a file store that an interrupt stops leaves no trace, and a write keeps the file's mode."""

import os
import stat
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService

type FileKind = Literal["json", "yaml"]

REPLACE = "taxomesh.adapters.repositories._file.os.replace"

pytestmark = pytest.mark.parametrize("kind", ["json", "yaml"])


def _open(kind: FileKind, path: Path) -> JsonRepository | YamlRepository:
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


def _names(repo: JsonRepository | YamlRepository) -> list[str]:
    return sorted(category.name for category in repo.list_categories(enabled=None))


def test_an_interrupted_write_is_not_carried_to_disk_by_the_next_write(kind: FileKind, tmp_path: Path) -> None:
    path = tmp_path / f"store.{kind}"
    repo = _open(kind, path)
    svc = TaxomeshService(repo, cache_ttl=0)
    svc.categories.create("kept")

    with patch(REPLACE, side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
        svc.categories.create("interrupted")
    svc.categories.create("after")

    expected = ["__root__", "after", "kept"]
    assert _names(repo) == expected
    assert _names(_open(kind, path)) == expected
    assert [entry.name for entry in tmp_path.iterdir()] == [path.name]


def test_a_write_keeps_the_mode_of_the_file(kind: FileKind, tmp_path: Path) -> None:
    path = tmp_path / f"store.{kind}"
    svc = TaxomeshService(_open(kind, path), cache_ttl=0)
    svc.categories.create("first")
    os.chmod(path, 0o644)

    svc.categories.create("second")

    assert stat.S_IMODE(path.stat().st_mode) == 0o644
