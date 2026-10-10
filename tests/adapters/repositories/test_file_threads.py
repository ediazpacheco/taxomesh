"""Threads sharing one file store: each write is one step, and a block held open keeps them out.

A host that runs a service on several threads, as a threaded web server does, shares one
repository between them. Each of the store's members runs whole before another thread's starts,
so a version check and its write are one step, and the whole store is never written while another
thread changes it. The tests switch threads as often as the interpreter allows, which turns a rare
interleaving into a frequent one.
"""

import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Final, Literal

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item
from taxomesh.exceptions import TaxomeshVersionConflictError

type FileKind = Literal["json", "yaml"]
type FileRepository = JsonRepository | YamlRepository

# Threads racing in each test.
THREADS: Final[int] = 4

# Rows stored before a race, so that each write of the whole store takes long enough to be interrupted.
SEED_ROWS: Final[int] = 50

# Races run by the version test; one double success among them fails it.
TRIALS: Final[int] = 10

# Rows each thread creates in the create test.
CREATES_PER_THREAD: Final[int] = 40

# How long a read is given to finish while another thread holds the store; it must not.
BLOCKED_FOR: Final[float] = 0.1

# The longest any thread below is waited for before the test gives up on it.
JOIN_TIMEOUT: Final[float] = 30.0


def _open(kind: FileKind, path: Path) -> FileRepository:
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


def _race(work: Callable[[int], None]) -> None:
    """Run ``work(0)`` … ``work(THREADS - 1)`` on as many threads, released together."""
    start = threading.Barrier(THREADS)

    def run(k: int) -> None:
        start.wait()
        work(k)

    threads = [threading.Thread(target=run, args=(k,), daemon=True) for k in range(THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_TIMEOUT)


def _update_on_every_thread(svc: TaxomeshService, row: Item) -> list[str]:
    """Update ``row`` from every thread at version 0; each thread's outcome, in finishing order."""
    outcomes: list[str] = []

    def write(k: int) -> None:
        try:
            svc.items.update(row, name=f"writer {k}", expected_version=0)
            outcomes.append("stored")
        except TaxomeshVersionConflictError:
            outcomes.append("conflict")

    _race(write)
    return outcomes


@pytest.fixture(params=["json", "yaml"])
def kind(request: pytest.FixtureRequest) -> FileKind:
    """Each file format."""
    file_kind: FileKind = request.param
    return file_kind


@pytest.fixture
def fast_switching() -> Iterator[None]:
    """Switch threads as often as the interpreter allows, and restore the interval afterwards."""
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(interval)


@pytest.mark.usefixtures("fast_switching")
class TestThreadsSharingAStore:
    """Several threads, one repository, one service."""

    def test_one_of_the_writers_holding_one_version_succeeds(self, kind: FileKind, tmp_path: Path) -> None:
        repo = _open(kind, tmp_path / f"store.{kind}")
        svc = TaxomeshService(repo, cache_ttl=0)
        for n in range(SEED_ROWS):
            svc.items.create(f"seed {n}")

        for trial in range(TRIALS):
            row = svc.items.create(f"raced {trial}")

            outcomes = _update_on_every_thread(svc, row)

            assert sorted(outcomes) == ["conflict"] * (THREADS - 1) + ["stored"]
            assert svc.items[row].version == 1

    def test_creates_on_every_thread_all_land_and_none_raises(self, kind: FileKind, tmp_path: Path) -> None:
        path = tmp_path / f"store.{kind}"
        repo = _open(kind, path)
        svc = TaxomeshService(repo, cache_ttl=0)
        failures: list[Exception] = []

        def create(k: int) -> None:
            for n in range(CREATES_PER_THREAD):
                try:
                    svc.items.create(f"thread {k} row {n}")
                except Exception as exc:
                    failures.append(exc)

        _race(create)

        assert failures == []
        assert len(repo.list_items()) == THREADS * CREATES_PER_THREAD
        assert len(_open(kind, path).list_items()) == THREADS * CREATES_PER_THREAD

    def test_a_read_waits_while_another_thread_holds_the_store(self, kind: FileKind, tmp_path: Path) -> None:
        repo = _open(kind, tmp_path / f"store.{kind}")
        holding, release, read_done = threading.Event(), threading.Event(), threading.Event()

        def hold() -> None:
            with repo.atomic():
                holding.set()
                release.wait(JOIN_TIMEOUT)

        def read() -> None:
            repo.list_items()
            read_done.set()

        holder = threading.Thread(target=hold, daemon=True)
        holder.start()
        assert holding.wait(JOIN_TIMEOUT)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            assert not read_done.wait(BLOCKED_FOR)
        finally:
            release.set()
        holder.join(JOIN_TIMEOUT)
        reader.join(JOIN_TIMEOUT)
        assert read_done.is_set()
