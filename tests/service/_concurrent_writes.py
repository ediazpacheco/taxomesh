"""Two writes at the same moment, on two threads: the schedules, and the runner that interleaves them.

A write reads what it decides on first: the row it updates, the slug or external id it checks, the
parent links its cycle check reads, the siblings it orders, the rows it links. Each schedule below
runs one write on a first thread and, right after a read of that write, starts a second write on a
second thread. The second write must wait until the first one ends, and must then see what the first
one stored: refuse a cycle or a key that the first write took, build on the row that the first write
saved, or delete it for good. The runner records whether the second thread was still waiting after
:data:`BLOCKED_FOR`, how each call ended, and which rows and links changed.

``tests/service/test_concurrent_writes.py`` runs the schedules on one YAML or JSON repository that the
two threads share. ``tests/contrib/django/_concurrent_writes.py`` runs them on two
``DjangoRepository`` over one SQLite file, as two workers do.
"""

import threading
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Final, TypedDict
from unittest import mock
from uuid import UUID

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import Category, Item, Tag
from taxomesh.ports.repository import TaxomeshRepositoryBase

# How long the second thread must still be waiting, while the first thread is inside its write.
BLOCKED_FOR: Final[float] = 0.1

# The longest any thread is waited for. It is above SQLite's busy timeout of 5 seconds, so a thread
# that SQLite makes wait either goes on or fails before the runner gives up on it.
JOIN_TIMEOUT: Final[float] = 10.0

# How a call ended: it returned, or it raised the error class named instead.
RETURNED: Final[str] = "ok"

# The outcome of a call that did not end within JOIN_TIMEOUT, or of one that never started.
NOT_ENDED: Final[str] = "did not end"


@dataclass(frozen=True)
class Scene:
    """The rows stored before a race, by identifier, and the name each identifier shows as.

    Categories A, B, P, X, Y and Z are at the top level; C and D are the children of P, with no other
    parent. Item I is placed in X, and J and K in Y, in that order. T is a tag on no item.
    """

    a: UUID
    b: UUID
    p: UUID
    c: UUID
    d: UUID
    x: UUID
    y: UUID
    z: UUID
    i: UUID
    j: UUID
    k: UUID
    t: UUID
    names: Mapping[UUID, str]

    @property
    def items(self) -> Collection[UUID]:
        """The identifiers of the scene's items."""
        return (self.i, self.j, self.k)


def build_scene(svc: TaxomeshService) -> Scene:
    """Store the rows and the links of a :class:`Scene` through ``svc``, and return it."""
    categories = {name: svc.categories.create(name).category_id for name in "ABPCDXYZ"}
    svc.categories.add_parent(categories["C"], categories["P"])
    svc.categories.add_parent(categories["D"], categories["P"])
    items = {name: svc.items.create(name).item_id for name in "IJK"}
    svc.items.place_in(items["I"], categories["X"])
    svc.items.place_in(items["J"], categories["Y"], sort_index=0)
    svc.items.place_in(items["K"], categories["Y"], sort_index=1)
    tag = svc.tags.create("T").tag_id
    root = next(c.category_id for c in svc.repository.list_categories(enabled=None) if c.name == ROOT_CATEGORY_NAME)
    names = {uid: name for name, uid in (*categories.items(), *items.items())} | {tag: "T", root: ROOT_CATEGORY_NAME}
    return Scene(
        a=categories["A"],
        b=categories["B"],
        p=categories["P"],
        c=categories["C"],
        d=categories["D"],
        x=categories["X"],
        y=categories["Y"],
        z=categories["Z"],
        i=items["I"],
        j=items["J"],
        k=items["K"],
        t=tag,
        names=names,
    )


def _row_line(label: str, row: Category | Item | Tag) -> str:
    """Return how a stored row shows in a snapshot: ``"I = 'I2' slug='s'"``.

    ``label`` names the row as the scene does, so a rename shows as a new value of the same row.
    """
    line = f"{label} = {row.name!r}"
    if isinstance(row, Tag):
        return line
    if row.slug:
        line += f" slug={row.slug!r}"
    if row.external_id is not None:
        line += f" external_id={row.external_id!r}"
    return line


def snapshot(repository: TaxomeshRepositoryBase, scene: Scene) -> set[str]:
    """Return every stored row, and every stored link between rows of the scene, by name, read through the port.

    A row reads ``"I = 'I'"``, with its slug and external id when it has them. A parent link reads
    ``"C -> P"``, a placement ``"I in X"``, a relation ``"I covers J"`` and a tag link ``"I tagged T"``.
    A row of the scene shows under its name in the scene, and a row that a write created under its own
    name. A link to a row that was deleted after the scene was built keeps that row's name, so a link
    left behind by a delete shows.
    """
    stored: dict[UUID, Category | Item | Tag] = {
        **{row.category_id: row for row in repository.list_categories(enabled=None)},
        **{row.item_id: row for row in repository.list_items(enabled=None)},
        **{row.tag_id: row for row in repository.list_tags()},
    }
    names = {uid: row.name for uid, row in stored.items()} | dict(scene.names)
    held = {_row_line(names[uid], row) for uid, row in stored.items()}
    held |= {
        f"{names[link.category_id]} -> {names[link.parent_category_id]}"
        for link in repository.list_category_parent_links()
        if link.category_id in names and link.parent_category_id in names
    }
    held |= {
        f"{names[link.item_id]} in {names[link.category_id]}"
        for link in repository.list_item_parent_links()
        if link.item_id in names and link.category_id in names
    }
    held |= {
        f"{names[link.source_item_id]} {link.relation_type} {names[link.target_item_id]}"
        for link in repository.list_item_relation_links_batch(scene.items, direction="both")
    }
    held |= {
        f"{names[link.item_id]} tagged {names[link.tag_id]}"
        for link in repository.list_item_tag_links()
        if link.item_id in names and link.tag_id in names
    }
    return held


class Outcome(TypedDict):
    """How a race ended: each call's end, whether the second waited, and the rows and links that changed."""

    first: str
    second: str
    blocked: bool
    added: list[str]
    removed: list[str]


type Write = Callable[[TaxomeshService, Scene], object]

# A call of the port, by member name, positional arguments and keyword arguments, that a write makes.
# ``mock.ANY`` stands for an argument that the schedule cannot name before the race, such as the row
# that a create saves.
type Read = tuple[str, tuple[object, ...], Mapping[str, object]]


def _call(name: str, *args: object, **kwargs: object) -> Read:
    """Name one call of the port, as a write makes it."""
    return name, args, kwargs


@dataclass(frozen=True)
class Schedule:
    """One race: the first write, the read of it that the second write starts after, and the result.

    Attributes:
        name: The test's identifier.
        first: The write on the first thread.
        after: The call of the port that the first write makes, after which the second thread starts.
        second: The write on the second thread.
        expected: The outcome when the second write waits for the first and then sees it.
    """

    name: str
    first: Write
    after: Callable[[Scene], Read]
    second: Write
    expected: Outcome


def _ended(*, second: str = RETURNED, added: tuple[str, ...] = (), removed: tuple[str, ...] = ()) -> Outcome:
    """The outcome of a race in which the second write waited for the first."""
    return Outcome(first=RETURNED, second=second, blocked=True, added=sorted(added), removed=sorted(removed))


def _every_parent_link(scene: Scene) -> Read:
    return _call("list_category_parent_links")


# The first write makes A a child of B, so the second write, which would make B a child of A, is a
# cycle; A leaves the top level.
_CYCLE_REFUSED: Final = _ended(second="TaxomeshCyclicDependencyError", added=("A -> B",), removed=("A -> __root__",))

SCHEDULES: Final[tuple[Schedule, ...]] = (
    Schedule(
        name="add_parent/add_parent",
        first=lambda svc, s: svc.categories.add_parent(s.a, s.b),
        after=_every_parent_link,
        second=lambda svc, s: svc.categories.add_parent(s.b, s.a),
        expected=_CYCLE_REFUSED,
    ),
    Schedule(
        name="move/move",
        first=lambda svc, s: svc.categories.move(s.a, from_parent=None, to_parent=s.b),
        after=_every_parent_link,
        second=lambda svc, s: svc.categories.move(s.b, from_parent=None, to_parent=s.a),
        expected=_CYCLE_REFUSED,
    ),
    Schedule(
        name="add_parent/move",
        first=lambda svc, s: svc.categories.add_parent(s.a, s.b),
        after=_every_parent_link,
        second=lambda svc, s: svc.categories.move(s.b, from_parent=None, to_parent=s.a),
        expected=_CYCLE_REFUSED,
    ),
    Schedule(
        name="move to the top level/add_parent",
        first=lambda svc, s: svc.categories.move(s.b, from_parent=None, to_parent=None),
        after=_every_parent_link,
        second=lambda svc, s: svc.categories.add_parent(s.b, s.a),
        expected=_ended(added=("B -> A",), removed=("B -> __root__",)),
    ),
    Schedule(
        name="categories.reorder/remove_parent",
        first=lambda svc, s: svc.categories.reorder(s.p, [s.d, s.c]),
        after=lambda s: _call("list_category_parent_links", parent_category_ids=[s.p]),
        second=lambda svc, s: svc.categories.remove_parent(s.c, s.p),
        expected=_ended(added=("C -> __root__",), removed=("C -> P",)),
    ),
    Schedule(
        name="items.move/remove_from",
        first=lambda svc, s: svc.items.move(s.i, from_category=s.x, to_category=s.y),
        after=lambda s: _call("list_item_parent_links", category_ids=[s.y]),
        second=lambda svc, s: svc.items.remove_from(s.j, s.y),
        expected=_ended(added=("I in Y",), removed=("I in X", "J in Y")),
    ),
    Schedule(
        name="items.reorder/remove_from",
        first=lambda svc, s: svc.items.reorder(s.y, [s.k, s.j]),
        after=lambda s: _call("list_item_parent_links", category_ids=[s.y]),
        second=lambda svc, s: svc.items.remove_from(s.j, s.y),
        expected=_ended(removed=("J in Y",)),
    ),
    Schedule(
        name="place_in/categories.delete",
        first=lambda svc, s: svc.items.place_in(s.i, s.z),
        after=lambda s: _call("find_category", s.z),
        second=lambda svc, s: svc.categories.delete(s.z),
        expected=_ended(removed=("Z = 'Z'", "Z -> __root__")),
    ),
    Schedule(
        name="relate/items.delete",
        first=lambda svc, s: svc.items.relate(s.i, s.j, "covers"),
        after=lambda s: _call("find_item", s.j),
        second=lambda svc, s: svc.items.delete(s.j),
        expected=_ended(removed=("J = 'J'", "J in Y")),
    ),
    Schedule(
        name="tag/items.delete",
        first=lambda svc, s: svc.items.tag(s.i, s.t),
        after=lambda s: _call("find_item", s.i),
        second=lambda svc, s: svc.items.delete(s.i),
        expected=_ended(removed=("I = 'I'", "I in X")),
    ),
    # An update builds on the row it reads, so a delete that lands after the read must wait: else the
    # save stores the deleted row again, or a rename that lands there is lost.
    Schedule(
        name="items.update/items.delete",
        first=lambda svc, s: svc.items.update(s.i, slug="s"),
        after=lambda s: _call("find_item", s.i),
        second=lambda svc, s: svc.items.delete(s.i),
        expected=_ended(removed=("I = 'I'", "I in X")),
    ),
    Schedule(
        name="categories.update/categories.delete",
        first=lambda svc, s: svc.categories.update(s.a, slug="s"),
        after=lambda s: _call("find_category", s.a),
        second=lambda svc, s: svc.categories.delete(s.a),
        expected=_ended(removed=("A = 'A'", "A -> __root__")),
    ),
    Schedule(
        name="tags.update/tags.delete",
        first=lambda svc, s: svc.tags.update(s.t, name="T2"),
        after=lambda s: _call("find_tag", s.t),
        second=lambda svc, s: svc.tags.delete(s.t),
        expected=_ended(removed=("T = 'T'",)),
    ),
    Schedule(
        name="items.update/items.update",
        first=lambda svc, s: svc.items.update(s.i, slug="s"),
        after=lambda s: _call("find_item", s.i),
        second=lambda svc, s: svc.items.update(s.i, name="I2"),
        expected=_ended(added=("I = 'I2' slug='s'",), removed=("I = 'I'",)),
    ),
    Schedule(
        name="categories.update/categories.update",
        first=lambda svc, s: svc.categories.update(s.a, slug="s"),
        after=lambda s: _call("find_category", s.a),
        second=lambda svc, s: svc.categories.update(s.a, name="A2"),
        expected=_ended(added=("A = 'A2' slug='s'",), removed=("A = 'A'",)),
    ),
    # A slug or an external id is unique within its kind, so of two writes that give one to two rows,
    # the second must wait and then be refused. A create reads no external id: the save checks it.
    Schedule(
        name="items.create/items.create, one slug",
        first=lambda svc, s: svc.items.create("N1", slug="s"),
        after=lambda s: _call("find_item_by_slug", "s"),
        second=lambda svc, s: svc.items.create("N2", slug="s"),
        expected=_ended(second="TaxomeshDuplicateSlugError", added=("N1 = 'N1' slug='s'",)),
    ),
    Schedule(
        name="categories.create/categories.create, one slug",
        first=lambda svc, s: svc.categories.create("N1", slug="s"),
        after=lambda s: _call("find_category_by_slug", "s"),
        second=lambda svc, s: svc.categories.create("N2", slug="s"),
        expected=_ended(second="TaxomeshDuplicateSlugError", added=("N1 = 'N1' slug='s'", "N1 -> __root__")),
    ),
    Schedule(
        name="items.update/items.update, one slug",
        first=lambda svc, s: svc.items.update(s.i, slug="s"),
        after=lambda s: _call("find_item_by_slug", "s"),
        second=lambda svc, s: svc.items.update(s.j, slug="s"),
        expected=_ended(second="TaxomeshDuplicateSlugError", added=("I = 'I' slug='s'",), removed=("I = 'I'",)),
    ),
    Schedule(
        name="categories.update/categories.update, one slug",
        first=lambda svc, s: svc.categories.update(s.a, slug="s"),
        after=lambda s: _call("find_category_by_slug", "s"),
        second=lambda svc, s: svc.categories.update(s.b, slug="s"),
        expected=_ended(second="TaxomeshDuplicateSlugError", added=("A = 'A' slug='s'",), removed=("A = 'A'",)),
    ),
    Schedule(
        name="items.create/items.create, one external id",
        first=lambda svc, s: svc.items.create("N1", external_id="e"),
        after=lambda s: _call("save_item", mock.ANY),
        second=lambda svc, s: svc.items.create("N2", external_id="e"),
        expected=_ended(second="TaxomeshExternalIdConflictError", added=("N1 = 'N1' external_id='e'",)),
    ),
    Schedule(
        name="categories.create/categories.create, one external id",
        first=lambda svc, s: svc.categories.create("N1", external_id="e"),
        after=lambda s: _call("save_category", mock.ANY),
        second=lambda svc, s: svc.categories.create("N2", external_id="e"),
        expected=_ended(
            second="TaxomeshExternalIdConflictError", added=("N1 = 'N1' external_id='e'", "N1 -> __root__")
        ),
    ),
    Schedule(
        name="items.update/items.update, one external id",
        first=lambda svc, s: svc.items.update(s.i, external_id="e"),
        after=lambda s: _call("find_item_by_external_id", "e"),
        second=lambda svc, s: svc.items.update(s.j, external_id="e"),
        expected=_ended(
            second="TaxomeshExternalIdConflictError", added=("I = 'I' external_id='e'",), removed=("I = 'I'",)
        ),
    ),
    Schedule(
        name="categories.update/categories.update, one external id",
        first=lambda svc, s: svc.categories.update(s.a, external_id="e"),
        after=lambda s: _call("find_category_by_external_id", "e"),
        second=lambda svc, s: svc.categories.update(s.b, external_id="e"),
        expected=_ended(
            second="TaxomeshExternalIdConflictError", added=("A = 'A' external_id='e'",), removed=("A = 'A'",)
        ),
    ),
)


def _nothing() -> None:
    """Do nothing: the end of a thread on a backend that holds no connection per thread."""


def run(
    schedule: Schedule,
    scene: Scene,
    first: TaxomeshService,
    second: TaxomeshService,
    *,
    finish: Callable[[], None] = _nothing,
) -> Outcome:
    """Run one schedule on two threads and return how it ended.

    The first thread calls ``schedule.first`` on ``first``. Right after the first thread's call that
    ``schedule.after`` names, made through ``first.repository``, the second thread starts and calls
    ``schedule.second`` on ``second``. The first thread then waits :data:`BLOCKED_FOR` and records
    whether the second thread is still running, before its call returns. The two services can share a
    repository.

    Args:
        schedule: The race to run.
        scene: The rows that the writes name, stored before the call.
        first: The service of the first thread. The read is watched on its repository.
        second: The service of the second thread.
        finish: Called last on each thread, such as to close a connection that the thread opened.

    Returns:
        How each call ended, whether the second thread waited, and the links that changed.
    """
    repository = first.repository
    before = snapshot(repository, scene)
    ended: dict[str, str] = {}
    blocked: list[bool] = []

    def thread(key: str, call: Callable[[], object]) -> threading.Thread:
        def target() -> None:
            try:
                call()
                ended[key] = RETURNED
            except Exception as exc:
                ended[key] = type(exc).__name__
            finally:
                finish()

        return threading.Thread(target=target, daemon=True)

    first_thread = thread("first", lambda: schedule.first(first, scene))
    second_thread = thread("second", lambda: schedule.second(second, scene))
    name, arguments, keywords = schedule.after(scene)
    read: Callable[..., object] = getattr(repository, name)

    def watched(*args: object, **kwargs: object) -> object:
        result = read(*args, **kwargs)
        if threading.current_thread() is first_thread and not blocked and args == arguments and kwargs == keywords:
            second_thread.start()
            second_thread.join(BLOCKED_FOR)
            blocked.append(second_thread.is_alive())
        return result

    with mock.patch.object(repository, name, side_effect=watched):
        first_thread.start()
        first_thread.join(JOIN_TIMEOUT)
        if second_thread.ident is not None:
            second_thread.join(JOIN_TIMEOUT)
    after = snapshot(repository, scene)
    return Outcome(
        first=ended.get("first", NOT_ENDED),
        second=ended.get("second", NOT_ENDED),
        blocked=blocked == [True],
        added=sorted(after - before),
        removed=sorted(before - after),
    )
