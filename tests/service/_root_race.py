"""Two services built at the same moment over a store that holds no implicit root: the schedule and the outcome.

:func:`start_together` forces the order that left two roots: both builds read the store before either
one stores the root. Each thread's first ``list_categories`` waits until the other thread's has
returned; then the two stores run one at a time, so that a build that does not read again inside a
block stores a second root rather than meet an error of the database. Each service then creates one
category, and the outcome records how many roots storage holds and what each service shows.

``tests/service/test_root_race.py`` runs it on one YAML or JSON repository that the two threads share.
``tests/contrib/django/_root_race.py`` runs it on two ``DjangoRepository``, as two workers do.
"""

import threading
from collections.abc import Callable, Sequence
from typing import Final, TypedDict
from unittest import mock

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import Category
from taxomesh.ports.repository import TaxomeshRepositoryBase

# The longest a thread waits for the other one at the forced point, and the longest a thread is
# waited for. Above SQLite's busy timeout of 5 seconds, so a thread that SQLite makes wait goes on or
# fails first.
JOIN_TIMEOUT: Final[float] = 10.0

# The names of the category that each service creates once both are built.
FIRST: Final[str] = "made by the first"
SECOND: Final[str] = "made by the second"


class StartOutcome(TypedDict):
    """What two services built at the same moment leave.

    Attributes:
        roots: The number of rows named ``__root__`` that a repository opened afterwards reads.
        first: The names that the first service's ``categories.roots()`` lists, sorted.
        second: The names that the second service's ``categories.roots()`` lists, sorted.
        listed: The names that a service built afterwards lists with ``categories.list(enabled=None)``,
            sorted.
        errors: The class name of each error that a build raised.
    """

    roots: int
    first: list[str]
    second: list[str]
    listed: list[str]
    errors: list[str]


def stored_roots(repository: TaxomeshRepositoryBase) -> int:
    """Return how many rows named ``__root__`` the repository holds."""
    return sum(category.name == ROOT_CATEGORY_NAME for category in repository.list_categories(enabled=None))


def start_together[R: TaxomeshRepositoryBase](
    kind: type[R],
    open_repository: Callable[[], R],
    reopen: Callable[[], R],
    finish: Callable[[], None] = lambda: None,
) -> StartOutcome:
    """Build two services at the same moment, each over ``open_repository()``, in the forced order.

    Args:
        kind: The repository class: its ``list_categories`` and ``save_category`` are wrapped while
            the services are built, for every instance.
        open_repository: Returns the repository of one service: the same one each time for a store
            that threads share, or a new one for each worker.
        reopen: Returns a new repository over the same store, which reads what storage holds.
        finish: Called at the end of each thread, as closing its database connection.

    Returns:
        The outcome, read after both builds ended.
    """
    real_list = kind.list_categories
    real_save = kind.save_category
    both_read = threading.Barrier(2, timeout=JOIN_TIMEOUT)
    read_once: set[int] = set()
    one_store = threading.Lock()

    def list_categories(self: R, *, enabled: bool | None = True) -> Sequence[Category]:
        rows = real_list(self, enabled=enabled)
        if threading.get_ident() not in read_once:
            read_once.add(threading.get_ident())
            both_read.wait()
        return rows

    def save_category(self: R, category: Category, *, expected_version: int | None = None) -> Category:
        with one_store:
            return real_save(self, category, expected_version=expected_version)

    services: dict[str, TaxomeshService] = {}
    errors: list[str] = []

    def build(name: str) -> None:
        try:
            services[name] = TaxomeshService(open_repository(), cache_ttl=0)
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            finish()

    with (
        mock.patch.object(kind, "list_categories", list_categories),
        mock.patch.object(kind, "save_category", save_category),
    ):
        threads = [threading.Thread(target=build, args=(name,)) for name in (FIRST, SECOND)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(JOIN_TIMEOUT)
    if errors:
        return {"roots": stored_roots(reopen()), "first": [], "second": [], "listed": [], "errors": errors}
    for name, svc in services.items():
        svc.categories.create(name)
    later = TaxomeshService(reopen(), cache_ttl=0)
    return {
        "roots": stored_roots(reopen()),
        "first": sorted(category.name for category in services[FIRST].categories.roots()),
        "second": sorted(category.name for category in services[SECOND].categories.roots()),
        "listed": sorted(category.name for category in later.categories.list(enabled=None)),
        "errors": [],
    }


def race_naturally(open_repository: Callable[[], TaxomeshRepositoryBase], finish: Callable[[], None]) -> str:
    """Build two services at once, released together by a barrier, and say how it ended.

    Returns:
        ``"one root"`` when both builds ended and one root is stored, ``"two roots"`` when both ended
        and more are stored, or the class name of the first error that a build raised.
    """
    together = threading.Barrier(2, timeout=JOIN_TIMEOUT)
    errors: list[str] = []

    def build() -> None:
        try:
            together.wait()
            TaxomeshService(open_repository(), cache_ttl=0)
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            finish()

    threads = [threading.Thread(target=build) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_TIMEOUT)
    if errors:
        return errors[0]
    return "one root" if stored_roots(open_repository()) == 1 else "two roots"
