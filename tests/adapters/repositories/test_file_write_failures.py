"""A failed write to a file store raises ``TaxomeshRepositoryError`` and leaves no trace.

A file store changes memory, then writes the whole store to a temporary file and renames it into
place. When any step of that write fails, the file still holds the last good state, so the store
puts back the copy of memory it took before the write: memory and file agree again, even when the
clean-up fails too, and the next write cannot carry the failed change to disk. The error is
``TaxomeshRepositoryError``, whichever public write met it.
"""

import errno
import os
import stat
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.exceptions import TaxomeshError, TaxomeshRepositoryError

type FileKind = Literal["json", "yaml"]
type FileRepository = JsonRepository | YamlRepository
type Snapshot = dict[str, list[dict[str, object]]]

# What a directory nobody may write into allows: reading and listing.
_READ_ONLY: Final[int] = stat.S_IRUSR | stat.S_IXUSR

# The rename a file store's write ends with, where the store looks it up.
REPLACE: Final[str] = "taxomesh.adapters.repositories._file.os.replace"


@dataclass(frozen=True)
class World:
    """A small store, and the rows each write below changes."""

    path: Path
    repo: FileRepository
    svc: TaxomeshService
    p: Category
    q: Category
    a: Category
    b: Category
    first: Item
    second: Item
    featured: Tag
    spare: Tag


def _open(kind: FileKind, path: Path) -> FileRepository:
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


def _world(kind: FileKind, tmp_path: Path, *, cache_ttl: float = 0) -> World:
    """P and Q at the top, A and B under P; two items in A; one tagged, one related."""
    path = tmp_path / "store" / f"store.{kind}"
    repo = _open(kind, path)
    svc = TaxomeshService(repo, cache_ttl=cache_ttl)
    p, q = svc.categories.create("P"), svc.categories.create("Q")
    a, b = svc.categories.create("A"), svc.categories.create("B")
    svc.categories.add_parent(a, p, sort_index=0)
    svc.categories.add_parent(b, p, sort_index=1)
    first, second = svc.items.create("first"), svc.items.create("second")
    svc.items.place_in(first, a, sort_index=0)
    svc.items.place_in(second, a, sort_index=1)
    featured, spare = svc.tags.create("featured"), svc.tags.create("spare")
    svc.items.tag(first, featured)
    svc.items.relate(first, second, "see-also")
    return World(path, repo, svc, p, q, a, b, first, second, featured, spare)


# Every public write of the three collections, each changing something in the world above.
WRITES: Final[dict[str, Callable[[World], object]]] = {
    "categories.create": lambda w: w.svc.categories.create("New"),
    "categories.update": lambda w: w.svc.categories.update(w.a, name="A2"),
    "categories.delete": lambda w: w.svc.categories.delete(w.b),
    "categories.add_parent": lambda w: w.svc.categories.add_parent(w.q, w.p),
    "categories.remove_parent": lambda w: w.svc.categories.remove_parent(w.a, w.p),
    "categories.move": lambda w: w.svc.categories.move(w.a, from_parent=w.p, to_parent=w.q),
    "categories.reorder": lambda w: w.svc.categories.reorder(w.p, [w.b, w.a]),
    "items.create": lambda w: w.svc.items.create("new"),
    "items.update": lambda w: w.svc.items.update(w.first, name="renamed"),
    "items.delete": lambda w: w.svc.items.delete(w.second),
    "items.place_in": lambda w: w.svc.items.place_in(w.first, w.b),
    "items.remove_from": lambda w: w.svc.items.remove_from(w.first, w.a),
    "items.move": lambda w: w.svc.items.move(w.first, from_category=w.a, to_category=w.b),
    "items.reorder": lambda w: w.svc.items.reorder(w.a, [w.second, w.first]),
    "items.tag": lambda w: w.svc.items.tag(w.second, w.featured),
    "items.untag": lambda w: w.svc.items.untag(w.first, w.featured),
    "items.relate": lambda w: w.svc.items.relate(w.second, w.first, "see-also"),
    "items.unrelate": lambda w: w.svc.items.unrelate(w.first, w.second, "see-also"),
    "tags.create": lambda w: w.svc.tags.create("new"),
    "tags.update": lambda w: w.svc.tags.update(w.featured, name="renamed"),
    "tags.delete": lambda w: w.svc.tags.delete(w.spare),
}

# The writes that make more than one file write: a failure after the first leaves that one on disk.
MULTI_WRITES: Final[tuple[str, ...]] = (
    "categories.add_parent",
    "categories.remove_parent",
    "categories.move",
    "categories.reorder",
    "items.move",
    "items.reorder",
)

# The writes that run inside ``atomic()``: a failure after their first file write leaves that one on disk.
ATOMIC_WRITES: Final[dict[str, Callable[[World], object]]] = {
    **{write: WRITES[write] for write in MULTI_WRITES},
    "categories.create": WRITES["categories.create"],
    "categories.delete, with children": lambda w: w.svc.categories.delete(w.p),
}


def _names(read: Callable[[], Sequence[Category] | Sequence[Item]]) -> list[str] | str:
    """The names a read returns, in its order, or the error it raises."""
    try:
        return [row.name for row in read()]
    except TaxomeshError as exc:
        return type(exc).__name__


def _seen(svc: TaxomeshService, world: World) -> dict[str, list[str] | str]:
    """What a caller of ``svc`` sees of the world: the top level, each category's rows, and a search."""
    reads: dict[str, Callable[[], Sequence[Category] | Sequence[Item]]] = {
        "the top level": svc.categories.roots,
        "under P": lambda: svc.categories.list(parent=world.p),
        "under Q": lambda: svc.categories.list(parent=world.q),
        "in A": lambda: svc.items.list(category=world.a),
        "in B": lambda: svc.items.list(category=world.b),
        "holding first": lambda: svc.categories.list(item=world.first),
        "found by a search": lambda: svc.categories.search("New"),
    }
    return {name: _names(read) for name, read in reads.items()}


def _snapshot(repo: FileRepository) -> Snapshot:
    """Everything the port reads back, in a fixed order."""
    items = repo.list_items(enabled=None)
    relations = repo.list_item_relation_links_batch([i.item_id for i in items], direction="both")
    return {
        "categories": [c.model_dump(mode="json") for c in repo.list_categories(enabled=None)],
        "items": [i.model_dump(mode="json") for i in items],
        "tags": [t.model_dump(mode="json") for t in sorted(repo.list_tags(), key=lambda t: str(t.tag_id))],
        "tag_links": [lnk.model_dump(mode="json") for lnk in repo.list_item_tag_links()],
        "parent_links": [lnk.model_dump(mode="json") for lnk in repo.list_category_parent_links()],
        "placements": [lnk.model_dump(mode="json") for lnk in repo.list_item_parent_links()],
        "relations": [lnk.model_dump(mode="json") for lnk in relations],
    }


def _without_tags(snapshot: Snapshot) -> Snapshot:
    return {section: rows for section, rows in snapshot.items() if section != "tags"}


@contextmanager
def _read_only(directory: Path) -> Iterator[None]:
    """Make ``directory`` refuse new files, as a full or read-only disk does, until the block ends."""
    mode = directory.stat().st_mode
    directory.chmod(_READ_ONLY)
    try:
        yield
    finally:
        directory.chmod(mode)


@contextmanager
def _unreachable(directory: Path) -> Iterator[None]:
    """Make ``directory`` refuse even a look inside, as a wrong owner or mode does, until the block ends."""
    mode = directory.stat().st_mode
    directory.chmod(0)
    try:
        yield
    finally:
        directory.chmod(mode)


def _failing_replace(failing_call: int) -> Callable[[str | os.PathLike[str], str | os.PathLike[str]], None]:
    """An ``os.replace`` that fails on its ``failing_call``-th call and renames on the others."""
    real_replace = os.replace
    calls = 0

    def replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == failing_call:
            raise OSError(errno.ENOSPC, "No space left on device")
        real_replace(src, dst)

    return replace


def _replace_failing_after(
    spoil: Callable[[], None],
) -> Callable[[str | os.PathLike[str], str | os.PathLike[str]], None]:
    """An ``os.replace`` that runs ``spoil`` and then fails, so the clean-up after it meets ``spoil``'s harm."""

    def replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        spoil()
        raise OSError(errno.ENOSPC, "No space left on device")

    return replace


@pytest.fixture(params=["json", "yaml"])
def kind(request: pytest.FixtureRequest) -> FileKind:
    """Each file format."""
    file_kind: FileKind = request.param
    return file_kind


class TestAWriteThatCannotReachTheDisk:
    """In a directory that refuses new files, or any look inside, every write raises and changes nothing."""

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_the_write_raises_and_changes_nothing(self, kind: FileKind, tmp_path: Path, write: str) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)
        text_before = world.path.read_bytes()

        with _read_only(world.path.parent), pytest.raises(TaxomeshRepositoryError, match="Could not write"):
            WRITES[write](world)

        assert _snapshot(world.repo) == before
        assert world.path.read_bytes() == text_before

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_the_next_write_does_not_carry_it_to_disk(self, kind: FileKind, tmp_path: Path, write: str) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)
        with _read_only(world.path.parent), pytest.raises(TaxomeshRepositoryError):
            WRITES[write](world)

        world.svc.tags.create("unrelated")

        on_disk = _snapshot(_open(kind, world.path))
        assert on_disk == _snapshot(world.repo)
        assert _without_tags(on_disk) == _without_tags(before)

    def test_a_new_store_that_cannot_be_written_raises(self, kind: FileKind, tmp_path: Path) -> None:
        with _read_only(tmp_path), pytest.raises(TaxomeshRepositoryError, match="Could not write"):
            _open(kind, tmp_path / f"store.{kind}")

    def test_a_new_store_whose_directory_cannot_be_made_raises(self, kind: FileKind, tmp_path: Path) -> None:
        with _read_only(tmp_path), pytest.raises(TaxomeshRepositoryError, match="Could not write"):
            _open(kind, tmp_path / "new" / f"store.{kind}")

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_a_directory_that_cannot_be_looked_into_raises_and_changes_nothing(
        self, kind: FileKind, tmp_path: Path, write: str
    ) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)
        text_before = world.path.read_bytes()

        with _unreachable(world.path.parent), pytest.raises(TaxomeshRepositoryError, match="Could not read"):
            WRITES[write](world)

        assert _snapshot(world.repo) == before
        assert world.path.read_bytes() == text_before

    def test_a_store_in_a_directory_that_cannot_be_looked_into_raises(self, kind: FileKind, tmp_path: Path) -> None:
        locked = tmp_path / "locked"
        locked.mkdir()

        with _unreachable(locked), pytest.raises(TaxomeshRepositoryError):
            _open(kind, locked / f"store.{kind}")


class TestAFailedRename:
    """A rename that fails partway through an operation leaves memory equal to the file."""

    @pytest.mark.parametrize("failing_call", [1, 2])
    @pytest.mark.parametrize("write", MULTI_WRITES)
    def test_memory_equals_the_file(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: str, failing_call: int
    ) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)

        with monkeypatch.context() as patch:
            patch.setattr(REPLACE, _failing_replace(failing_call))
            with pytest.raises(TaxomeshRepositoryError, match="No space left on device"):
                WRITES[write](world)

        assert _snapshot(world.repo) == _snapshot(_open(kind, world.path))
        if failing_call == 1:
            assert _snapshot(world.repo) == before

    def test_a_category_moved_off_the_top_level_stays_listed(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _world(kind, tmp_path)

        with monkeypatch.context() as patch:
            patch.setattr(REPLACE, _failing_replace(1))
            with pytest.raises(TaxomeshRepositoryError):
                world.svc.categories.move(world.q, from_parent=None, to_parent=world.p)

        assert world.q.category_id in {c.category_id for c in world.svc.categories.roots()}
        assert world.q.category_id not in {c.category_id for c in world.svc.categories.list(parent=world.p)}

    def test_a_file_spoiled_by_the_failed_rename_is_not_written_over(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)

        def replace_badly(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            Path(dst).write_text("{{{{ neither json: nor yaml", encoding="utf-8")
            raise OSError(errno.EIO, "Input/output error")

        with monkeypatch.context() as patch:
            patch.setattr(REPLACE, replace_badly)
            with pytest.raises(TaxomeshRepositoryError, match="Could not write"):
                world.svc.tags.create("lost")

        assert _snapshot(world.repo) == before
        with pytest.raises(TaxomeshRepositoryError, match="changed since this repository read it"):
            world.svc.tags.create("later")


class TestAFailedCleanUp:
    """A failed write whose clean-up fails too still raises the one error and leaves no trace."""

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_a_temporary_file_that_cannot_be_removed(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: str
    ) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)
        directory = world.path.parent
        mode = directory.stat().st_mode

        try:
            with monkeypatch.context() as patch:
                patch.setattr(REPLACE, _replace_failing_after(lambda: directory.chmod(_READ_ONLY)))
                with pytest.raises(TaxomeshRepositoryError, match="No space left on device"):
                    WRITES[write](world)
        finally:
            directory.chmod(mode)

        assert _snapshot(world.repo) == before
        world.svc.tags.create("unrelated")
        assert _without_tags(_snapshot(_open(kind, world.path))) == _without_tags(before)

    @pytest.mark.parametrize("write", sorted(WRITES))
    def test_a_file_that_cannot_be_read_at_that_moment(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: str
    ) -> None:
        world = _world(kind, tmp_path)
        before = _snapshot(world.repo)
        mode = world.path.stat().st_mode

        try:
            with monkeypatch.context() as patch:
                patch.setattr(REPLACE, _replace_failing_after(lambda: world.path.chmod(0)))
                with pytest.raises(TaxomeshRepositoryError):
                    WRITES[write](world)
        finally:
            world.path.chmod(mode)

        assert _snapshot(world.repo) == before
        world.svc.tags.create("unrelated")
        assert _without_tags(_snapshot(_open(kind, world.path))) == _without_tags(before)


class TestAFailedOperationAndTheCache:
    """An operation whose later file write fails leaves its service reading what storage kept."""

    @pytest.mark.parametrize("write", sorted(ATOMIC_WRITES))
    def test_the_service_reads_what_storage_kept(
        self, kind: FileKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write: str
    ) -> None:
        world = _world(kind, tmp_path, cache_ttl=60)
        _seen(world.svc, world)

        with monkeypatch.context() as patch:
            patch.setattr(REPLACE, _failing_replace(2))
            with pytest.raises(TaxomeshRepositoryError):
                ATOMIC_WRITES[write](world)

        assert _seen(world.svc, world) == _seen(TaxomeshService(_open(kind, world.path), cache_ttl=0), world)
