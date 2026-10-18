"""A move or a reorder reads the links of the one category or parent it orders, as a placement does.

``items.place_in`` reads the placements of its category only. ``items.move``, ``items.reorder`` and
``categories.reorder`` each order one category's items or one parent's children, so each reads those
links and no others: the other links of the store cost them nothing. ``categories.add_parent`` and
``categories.move`` read every parent link, since their cycle check needs the whole category graph.

Each test stores a busy category and a busy parent beside the ones it orders, and counts the links
that the listing returns, on the four backends.
"""

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category
from tests.service.conftest import CountedService

BUSY = 6


def _busy(svc: TaxomeshService) -> None:
    """Store a category holding ``BUSY`` items and a parent holding ``BUSY`` children."""
    items_category = svc.categories.create("Busy items")
    parent = svc.categories.create("Busy parent")
    for n in range(BUSY):
        svc.items.place_in(svc.items.create(f"Busy {n}"), items_category)
        svc.categories.add_parent(svc.categories.create(f"Busy child {n}"), parent)


def test_an_item_move_reads_the_placements_of_the_category_it_joins(counting_service: CountedService) -> None:
    svc = counting_service.service
    _busy(svc)
    left, right = svc.categories.create("Left"), svc.categories.create("Right")
    moved, stayed = svc.items.create("Moved"), svc.items.create("Stayed")
    svc.items.place_in(moved, left)
    svc.items.place_in(stayed, right)

    counting_service.cold()
    svc.items.move(moved, from_category=left, to_category=right)

    assert counting_service.reads.rows_of("list_item_parent_links") == 1
    assert [i.name for i in svc.items.list(category=right)] == ["Stayed", "Moved"]


def test_an_item_reorder_reads_the_placements_of_its_category(counting_service: CountedService) -> None:
    svc = counting_service.service
    _busy(svc)
    shelf = svc.categories.create("Shelf")
    first, second = svc.items.create("First"), svc.items.create("Second")
    svc.items.place_in(first, shelf)
    svc.items.place_in(second, shelf)

    counting_service.cold()
    svc.items.reorder(shelf, [second, first])

    assert counting_service.reads.rows_of("list_item_parent_links") == 2
    assert [i.name for i in svc.items.list(category=shelf)] == ["Second", "First"]


def test_a_category_reorder_reads_the_links_of_its_parent(counting_service: CountedService) -> None:
    svc = counting_service.service
    _busy(svc)
    parent = svc.categories.create("Parent")
    children: list[Category] = [svc.categories.create(name) for name in ("One", "Two")]
    for child in children:
        svc.categories.add_parent(child, parent)

    counting_service.cold()
    svc.categories.reorder(parent, children[::-1])

    assert counting_service.reads.rows_of("list_category_parent_links") == 2
    assert [c.name for c in svc.categories.list(parent=parent)] == ["Two", "One"]


def test_a_reorder_of_the_top_level_reads_the_top_level_links(counting_service: CountedService) -> None:
    svc = counting_service.service
    _busy(svc)
    top_level = svc.categories.roots()

    counting_service.cold()
    svc.categories.reorder(None, top_level[::-1])

    assert counting_service.reads.rows_of("list_category_parent_links") == len(top_level)
    assert svc.categories.roots() == top_level[::-1]
