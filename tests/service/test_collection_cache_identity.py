"""The cache-identity gate for the collections.

A collection's memoized reads keep their entries in the service's cache, which the service hands
each collection when it builds it. Nothing about correctness fails when a read misses: a total
cache miss still returns the right row. What fails is the exact-constant read gates, which must
pass with their constants unmodified. That is why the assertions here are about **identity and
hits**, never about values:

* a collection is the same object on every access;
* a read through the collection is served by a **memoized accessor**, not by a fresh port
  call — asserted as zero repository reads after priming;
* the collection declares a memoized read. The check is shape-independent, so it names no
  member.
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.utils.memoize import MemoizedFunction
from tests.service.conftest import CountedService


def test_each_collection_is_the_same_object_on_every_access(service: TaxomeshService) -> None:
    """Two accesses yield the identical object, holding the state the service injected."""
    assert service.categories is service.categories
    assert service.items is service.items
    assert service.tags is service.tags


def test_subscript_is_served_by_the_memoized_accessor(counting_service: CountedService) -> None:
    """A primed row read through ``svc.categories[...]`` costs no repository read.

    The assertion is about the **cost** of the read rather than its route. It fails if the
    collection reaches past its own ``_lookup`` for the port's ``find_category``, which would be
    correct and would silently pay for every row again.

    Asserting the hit rather than the value is the whole point — a total miss returns the same
    rows.
    """
    svc = counting_service.service
    parent = svc.categories.create("P")
    for index in range(3):
        child = svc.categories.create(f"K{index}")
        svc.categories.add_parent(child.category_id, parent.category_id)

    counting_service.cold()
    listed = svc.categories.list(parent=parent.category_id)
    counting_service.reads.reset()

    for child_category in listed:
        assert svc.categories[child_category.category_id] == child_category

    assert counting_service.reads.total == 0


def test_the_category_read_is_memoized_on_the_collection(service: TaxomeshService) -> None:
    """The memoized category read lives on ``CategoryCollection`` itself.

    Deliberately shape-independent: it asks only whether the class declares a memoized read,
    not what that read is called.
    """
    memoized = [
        f"{cls.__name__}.{name}"
        for cls in type(service.categories).__mro__
        for name, member in vars(cls).items()
        if isinstance(member, MemoizedFunction)
    ]

    assert memoized, "CategoryCollection declares no memoized read; the body is still on the service"
