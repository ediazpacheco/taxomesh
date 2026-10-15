"""Two Django workers that start at the same moment on a database with no implicit root store one.

Each worker builds its own service over its own ``DjangoRepository``. A build that finds no implicit
root reads again inside one ``atomic()`` block, whose first statement takes the database's lock, and
stores the root only if it is still absent. So the second build waits, then finds the root that the
first one stored. The races run in ``_root_race.py``, in a process of its own, on SQLite files, on the
``default`` alias and on another one.
"""

import pytest

from tests.service._root_race import FIRST, SECOND

pytest.importorskip("django", reason="Django is not installed")

from tests.contrib.django._process import Printed, run_helper
from tests.contrib.django._root_race import ALIASES, ROUNDS


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> Printed:
    """Race on both aliases once, in one process of its own, and return the outcomes by alias."""
    return run_helper("tests.contrib.django._root_race", str(tmp_path_factory.mktemp("root_race")))


@pytest.mark.parametrize("alias", ALIASES)
def test_two_services_built_in_the_forced_order_store_one_root(outcomes: Printed, alias: str) -> None:
    both = sorted([FIRST, SECOND])
    assert outcomes[alias]["forced"] == {"roots": 1, "first": both, "second": both, "listed": both, "errors": []}


@pytest.mark.parametrize("alias", ALIASES)
def test_two_services_built_at_once_store_one_root_every_time(outcomes: Printed, alias: str) -> None:
    assert outcomes[alias]["natural"] == {"one root": ROUNDS}
