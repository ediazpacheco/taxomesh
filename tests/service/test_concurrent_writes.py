"""Two writes at the same moment on one YAML or JSON repository run one after the other.

A host that runs a service on several threads shares one repository between them. Every write reads
what it decides on, checks it, and writes, all while it holds the repository's lock. So a second
thread's write waits, and then sees what the first one stored: it refuses a cycle or a key that the
first write took, it does not bring back a link or a row that the first write removed, and it builds
on the row that the first write saved. ``_concurrent_writes.py`` holds the schedules.

The races show what two threads do. That every member that writes makes each call of the port inside
one ``atomic()`` block is asserted on its own, below: on a database whose lock covers one row, such as
PostgreSQL, a write outside a block would not wait for one, and the suite's databases cannot show it.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final, Literal

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.service._concurrent_writes import SCHEDULES, Scene, Schedule, build_scene, run, snapshot

type FileKind = Literal["json", "yaml"]


def _open(kind: FileKind, path: Path) -> JsonRepository | YamlRepository:
    return JsonRepository(path) if kind == "json" else YamlRepository(path)


@pytest.mark.parametrize("kind", ["json", "yaml"])
@pytest.mark.parametrize("schedule", SCHEDULES, ids=[schedule.name for schedule in SCHEDULES])
def test_the_second_write_waits_for_the_first_and_sees_what_it_stored(
    kind: FileKind, schedule: Schedule, tmp_path: Path
) -> None:
    path = tmp_path / f"store.{kind}"
    repository = _open(kind, path)
    svc = TaxomeshService(repository)
    scene = build_scene(svc)

    assert run(schedule, scene, svc, svc) == schedule.expected
    # The file holds what memory holds: a store that broke the root invariant is not repaired on load.
    assert snapshot(_open(kind, path), scene) == snapshot(repository, scene)


class BlockWatcher:
    """Pass every call to a repository, and record the blocks opened and each call made outside one."""

    def __init__(self, wrapped: TaxomeshRepositoryBase) -> None:
        self._wrapped = wrapped
        self._open = 0
        self.blocks = 0
        self.outside: list[str] = []

    def reset(self) -> None:
        """Forget what was recorded, so a measurement leaves out the scene's own writes."""
        self.blocks = 0
        self.outside.clear()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Open a block of the wrapped repository, and count it."""
        self.blocks += 1
        self._open += 1
        try:
            with self._wrapped.atomic():
                yield
        finally:
            self._open -= 1

    # Any: a proxy passes on whatever attribute the wrapped repository has, called with whatever it takes.
    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped, name)
        if not callable(attr):
            return attr

        # Any: the call takes and returns whatever the port member does.
        def call(*args: Any, **kwargs: Any) -> Any:
            if not self._open:
                self.outside.append(name)
            return attr(*args, **kwargs)

        return call


# Every member that writes, called on the scene as a caller would.
WRITES: Final[dict[str, Callable[[TaxomeshService, Scene], object]]] = {
    "categories.create": lambda svc, s: svc.categories.create("N", slug="n"),
    "categories.update": lambda svc, s: svc.categories.update(s.a, slug="a", external_id="a"),
    "categories.delete": lambda svc, s: svc.categories.delete(s.p),
    "categories.add_parent": lambda svc, s: svc.categories.add_parent(s.a, s.b),
    "categories.remove_parent": lambda svc, s: svc.categories.remove_parent(s.c, s.p),
    "categories.move": lambda svc, s: svc.categories.move(s.c, from_parent=s.p, to_parent=s.a),
    "categories.reorder": lambda svc, s: svc.categories.reorder(s.p, [s.d, s.c]),
    "items.create": lambda svc, s: svc.items.create("N", slug="n"),
    "items.update": lambda svc, s: svc.items.update(s.i, slug="i", external_id="i"),
    "items.delete": lambda svc, s: svc.items.delete(s.i),
    "items.place_in": lambda svc, s: svc.items.place_in(s.i, s.y),
    "items.remove_from": lambda svc, s: svc.items.remove_from(s.j, s.y),
    "items.move": lambda svc, s: svc.items.move(s.i, from_category=s.x, to_category=s.y),
    "items.reorder": lambda svc, s: svc.items.reorder(s.y, [s.k, s.j]),
    "items.tag": lambda svc, s: svc.items.tag(s.i, s.t),
    "items.untag": lambda svc, s: svc.items.untag(s.i, s.t),
    "items.relate": lambda svc, s: svc.items.relate(s.i, s.j, "covers"),
    "items.unrelate": lambda svc, s: svc.items.unrelate(s.i, s.j, "covers"),
    "tags.create": lambda svc, s: svc.tags.create("U"),
    "tags.update": lambda svc, s: svc.tags.update(s.t, name="T2"),
    "tags.delete": lambda svc, s: svc.tags.delete(s.t),
}


@pytest.mark.parametrize("member", WRITES)
def test_a_write_calls_the_port_only_inside_one_block(member: str, tmp_path: Path) -> None:
    watcher = BlockWatcher(JsonRepository(tmp_path / "store.json"))
    svc = TaxomeshService(watcher)
    scene = build_scene(svc)
    watcher.reset()

    WRITES[member](svc, scene)

    assert (watcher.blocks, watcher.outside) == (1, [])
