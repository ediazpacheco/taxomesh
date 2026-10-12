"""One writer per file: a store whose file another writer changed refuses to write.

A file store reads its file once and writes it whole, so a second repository over the same file,
in this process or another, would write over the first one's change. Instead, a repository whose
file changed since it read it refuses every write with ``TaxomeshRepositoryError``, naming the cure:
build a new repository, which reads the change. It still answers reads from what it read.
"""

from pathlib import Path
from typing import Literal
from uuid import uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshRepositoryError

type FileKind = Literal["json", "yaml"]
type FileRepository = JsonRepository | YamlRepository

# What the refusal says to do.
CURE = "build a new repository"


def _open(kind: FileKind, path: Path) -> FileRepository:
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


def _names(repo: FileRepository) -> list[str]:
    return [item.name for item in repo.list_items()]


@pytest.fixture(params=["json", "yaml"])
def kind(request: pytest.FixtureRequest) -> FileKind:
    """Each file format."""
    file_kind: FileKind = request.param
    return file_kind


@pytest.fixture
def path(kind: FileKind, tmp_path: Path) -> Path:
    """A store holding one item, written by a repository that is gone."""
    store = tmp_path / f"store.{kind}"
    TaxomeshService(_open(kind, store), cache_ttl=0).items.create("first")
    return store


class TestTwoRepositoriesOnOneFile:
    """A reads the file, B writes it, then A tries to write."""

    def test_the_stale_write_is_refused_and_the_file_keeps_the_other_writers_row(
        self, kind: FileKind, path: Path
    ) -> None:
        a = TaxomeshService(_open(kind, path), cache_ttl=0)
        b = TaxomeshService(_open(kind, path), cache_ttl=0)
        b.items.create("from b")

        with pytest.raises(TaxomeshRepositoryError, match=CURE):
            a.items.create("from a")

        assert _names(_open(kind, path)) == ["first", "from b"]

    def test_the_stale_repository_still_answers_reads(self, kind: FileKind, path: Path) -> None:
        a = _open(kind, path)
        TaxomeshService(_open(kind, path), cache_ttl=0).items.create("from b")
        with pytest.raises(TaxomeshRepositoryError):
            TaxomeshService(a, cache_ttl=0).items.create("from a")

        assert _names(a) == ["first"]

    def test_a_new_repository_reads_the_change(self, kind: FileKind, path: Path) -> None:
        a = TaxomeshService(_open(kind, path), cache_ttl=0)
        TaxomeshService(_open(kind, path), cache_ttl=0).items.create("from b")
        with pytest.raises(TaxomeshRepositoryError):
            a.items.create("from a")

        rebuilt = TaxomeshService(_open(kind, path), cache_ttl=0)
        rebuilt.items.create("from a")

        assert _names(_open(kind, path)) == ["first", "from a", "from b"]

    def test_a_write_that_would_change_nothing_is_refused_too(self, kind: FileKind, path: Path) -> None:
        a = _open(kind, path)
        TaxomeshService(_open(kind, path), cache_ttl=0).items.create("from b")

        with pytest.raises(TaxomeshRepositoryError, match=CURE):
            a.delete_item(uuid4())

    def test_the_repository_stays_stale_until_it_is_rebuilt(self, kind: FileKind, path: Path) -> None:
        a = TaxomeshService(_open(kind, path), cache_ttl=0)
        TaxomeshService(_open(kind, path), cache_ttl=0).items.create("from b")
        with pytest.raises(TaxomeshRepositoryError):
            a.items.create("from a")

        with pytest.raises(TaxomeshRepositoryError, match=CURE):
            a.tags.create("later")

    def test_a_file_removed_by_another_writer_counts_as_changed(self, kind: FileKind, path: Path) -> None:
        a = TaxomeshService(_open(kind, path), cache_ttl=0)
        path.unlink()

        with pytest.raises(TaxomeshRepositoryError, match=CURE):
            a.items.create("from a")

        assert not path.exists()


class TestOneWriter:
    """A repository that is the file's only writer keeps writing."""

    def test_its_own_writes_never_count_as_a_change(self, kind: FileKind, path: Path) -> None:
        a = TaxomeshService(_open(kind, path), cache_ttl=0)

        for n in range(5):
            a.items.create(f"own {n}")

        assert len(_open(kind, path).list_items()) == 6
