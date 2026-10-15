"""With no position given, a new link goes after the last one, and a position that is given still wins.

The top level, a parent's children, a category's items and an item's relations are each listed by
position. A member that adds a link with no position puts it after the last link of the same parent,
category or source item, so a store lists them in the order they were made. A link that is stored
already keeps its position unless a position is given. ``node.parents`` lists a category's parents
in the order of their identifiers: a position orders a child under its parent, not the parents of a
child.
"""

from typing import Final

from taxomesh import TaxomeshService

# Not in the order of the alphabet, so an order by name would show.
NAMES: Final[list[str]] = ["D", "A", "F", "B", "C", "E"]


def test_the_top_level_lists_the_categories_in_the_order_they_were_created(service: TaxomeshService) -> None:
    for name in NAMES:
        service.categories.create(name)

    assert [category.name for category in service.categories.roots()] == NAMES
    assert [node.category.name for node in service.graph().roots] == NAMES


def test_a_parents_children_list_in_the_order_they_were_added(service: TaxomeshService) -> None:
    top = service.categories.create("Top")
    for name in NAMES:
        service.categories.add_parent(service.categories.create(name), top)

    assert [category.name for category in service.categories.list(parent=top)] == NAMES
    assert [node.category.name for node in service.graph()[top].children] == NAMES


def test_a_categorys_items_list_in_the_order_they_were_placed(service: TaxomeshService) -> None:
    shelf = service.categories.create("Shelf")
    for name in NAMES:
        service.items.place_in(service.items.create(name), shelf)

    assert [item.name for item in service.items.list(category=shelf)] == NAMES
    assert [item.name for item in service.graph()[shelf].items] == NAMES


def test_an_items_relations_list_in_the_order_they_were_made(service: TaxomeshService) -> None:
    source = service.items.create("Source")
    for n, name in enumerate(NAMES):
        service.items.relate(source, service.items.create(name), "covers" if n % 2 else "quotes")

    assert [item.name for item in service.items.list_related(source)] == NAMES
    assert [link.sort_index for link in service.items.list_relations(source)] == list(range(len(NAMES)))


def test_a_position_that_is_given_still_wins(service: TaxomeshService) -> None:
    shelf = service.categories.create("Shelf")
    first, second, third = (service.items.create(name) for name in ("first", "second", "third"))
    service.items.place_in(first, shelf)
    service.items.place_in(second, shelf)
    service.items.place_in(third, shelf, sort_index=-1)

    assert [item.name for item in service.items.list(category=shelf)] == ["third", "first", "second"]
    assert service.items.place_in(service.items.create("fourth"), shelf).sort_index == 2


def test_after_the_last_is_after_the_largest_position(service: TaxomeshService) -> None:
    top = service.categories.create("Top")
    service.categories.add_parent(service.categories.create("far"), top, sort_index=10)

    link = service.categories.add_parent(service.categories.create("next"), top)

    assert link.sort_index == 11


def test_after_the_last_is_after_a_negative_largest_position(service: TaxomeshService) -> None:
    top, shelf, source = (
        service.categories.create("Top"),
        service.categories.create("Shelf"),
        service.items.create("s"),
    )
    service.categories.add_parent(service.categories.create("far"), top, sort_index=-5)
    service.items.place_in(service.items.create("far"), shelf, sort_index=-5)
    service.items.relate(source, service.items.create("far"), "r", sort_index=-5)

    positions = (
        service.categories.add_parent(service.categories.create("next"), top).sort_index,
        service.items.place_in(service.items.create("next"), shelf).sort_index,
        service.items.relate(source, service.items.create("next"), "r").sort_index,
    )

    assert positions == (-4, -4, -4)


def test_a_link_that_is_stored_keeps_its_position(service: TaxomeshService) -> None:
    shelf = service.categories.create("Shelf")
    first, second = (service.items.create(name) for name in ("first", "second"))
    service.items.place_in(first, shelf)
    service.items.place_in(second, shelf)

    again = service.items.place_in(first, shelf)

    assert again.sort_index == 0
    assert [item.name for item in service.items.list(category=shelf)] == ["first", "second"]


def test_a_relation_that_is_stored_keeps_its_position_and_takes_its_new_metadata(service: TaxomeshService) -> None:
    source, a, b = (service.items.create(name) for name in ("source", "a", "b"))
    service.items.relate(source, a, "covers")
    service.items.relate(source, b, "covers")

    again = service.items.relate(source, a, "covers", metadata={"year": 1941})

    assert (again.sort_index, again.metadata) == (0, {"year": 1941})
    assert [link.metadata for link in service.items.list_relations(source)] == [{"year": 1941}, {}]


def test_a_category_that_comes_back_to_the_top_level_goes_last(service: TaxomeshService) -> None:
    a, b, c = (service.categories.create(name) for name in "ABC")
    service.categories.add_parent(a, b)

    service.categories.remove_parent(a, b)

    assert [category.name for category in service.categories.roots()] == ["B", "C", "A"]


def test_the_children_of_a_deleted_category_come_back_last_in_their_order(service: TaxomeshService) -> None:
    doomed = service.categories.create("Doomed")
    service.categories.create("Kept")
    for name in ("x", "y"):
        service.categories.add_parent(service.categories.create(name), doomed)

    service.categories.delete(doomed)

    assert [category.name for category in service.categories.roots()] == ["Kept", "x", "y"]


def test_node_parents_are_in_the_order_of_their_identifiers(service: TaxomeshService) -> None:
    child = service.categories.create("Child")
    parents = [service.categories.create(name) for name in NAMES]
    for parent in parents:
        service.categories.add_parent(child, parent)

    held = [node.category.category_id for node in service.graph()[child].parents]

    assert held == sorted(parent.category_id for parent in parents)
