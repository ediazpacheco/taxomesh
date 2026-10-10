"""The port's category-parent link filters.

``list_category_parent_links`` filters by either end of the edge: ``category_ids`` and
``parent_category_ids``, as ``list_item_parent_links`` takes ``item_ids`` and ``category_ids``.

What is worth pinning, and why:

* **An empty collection matches nothing.** It is *not* "no filter". The trap is a falsy check
  (``if category_ids:``), which would silently return every link in the store. Each filter has
  its own test, because the bug would be written once per parameter.
* **The two filters AND.** Naming both ends addresses one edge, not the union of two sets.
* **Ordering survives every filter combination.** The docstring promises
  ``(parent_category_id, sort_index, category_id)`` unconditionally, and a filter pushed into a
  database query is exactly where an ``ORDER BY`` gets lost.

These run through the parametrised ``service`` fixture, so every assertion here is made four
times — once per backend, the fourth being ``InMemoryRepository``.
"""

from taxomesh.application.service import TaxomeshService


class TestCategoryIdsFilter:
    """The new filter, on the child end of the edge."""

    def test_none_applies_no_filter(self, service: TaxomeshService) -> None:
        """The default reads every link, unchanged from before the filter existed."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        links = service.repository.list_category_parent_links(category_ids=None)

        assert any(
            link.category_id == child.category_id and link.parent_category_id == parent.category_id for link in links
        )

    def test_empty_collection_matches_nothing(self, service: TaxomeshService) -> None:
        """An EMPTY collection is 'match nothing', NOT 'no filter'.

        The trap is the falsy check ``if category_ids:``, which would return every link in
        the store instead of none.
        """
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        assert service.repository.list_category_parent_links(category_ids=[]) == []

    def test_filters_to_the_named_children(self, service: TaxomeshService) -> None:
        """Only links whose ``category_id`` is a member come back."""
        parent = service.categories.create("Parent")
        wanted = service.categories.create("Wanted")
        other = service.categories.create("Other")
        service.categories.add_parent(wanted.category_id, parent.category_id)
        service.categories.add_parent(other.category_id, parent.category_id)

        links = service.repository.list_category_parent_links(category_ids=[wanted.category_id])

        assert {link.category_id for link in links} == {wanted.category_id}

    def test_a_multi_parent_child_returns_every_placement(self, service: TaxomeshService) -> None:
        """The filter names a child, not an edge — a child under two parents yields two links.

        Categories form a DAG, so this is the normal case, not a corner one. Both named parents
        come back through the filter.
        """
        first = service.categories.create("First Parent")
        second = service.categories.create("Second Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, first.category_id)
        service.categories.add_parent(child.category_id, second.category_id)

        links = service.repository.list_category_parent_links(category_ids=[child.category_id])

        assert {link.category_id for link in links} == {child.category_id}
        assert {first.category_id, second.category_id} <= {link.parent_category_id for link in links}

    def test_ordering_contract_holds_under_the_filter(self, service: TaxomeshService) -> None:
        """``(parent_category_id, sort_index, category_id)`` survives filtering by child.

        Read within the parent's group, since the contract sorts by parent first. Relative order
        inside a group is what a dropped ``ORDER BY`` would destroy.
        """
        parent = service.categories.create("Ordered Parent")
        children = [service.categories.create(f"Child {index}") for index in range(3)]
        for index, child in zip((2, 0, 1), children, strict=True):
            service.categories.add_parent(child.category_id, parent.category_id, sort_index=index)

        links = service.repository.list_category_parent_links(category_ids=[child.category_id for child in children])
        under_parent = [link for link in links if link.parent_category_id == parent.category_id]

        assert [link.sort_index for link in under_parent] == [0, 1, 2]


class TestBothFiltersTogether:
    """Naming both ends addresses one edge — AND, never union."""

    def test_the_filters_are_anded(self, service: TaxomeshService) -> None:
        """A child under one parent is invisible when the other parent is named."""
        mine = service.categories.create("My Parent")
        theirs = service.categories.create("Their Parent")
        child = service.categories.create("Child")
        stranger = service.categories.create("Stranger")
        service.categories.add_parent(child.category_id, mine.category_id)
        service.categories.add_parent(stranger.category_id, theirs.category_id)

        matched = service.repository.list_category_parent_links(
            category_ids=[child.category_id], parent_category_ids=[mine.category_id]
        )
        crossed = service.repository.list_category_parent_links(
            category_ids=[child.category_id], parent_category_ids=[theirs.category_id]
        )

        assert [link.category_id for link in matched] == [child.category_id]
        assert crossed == []

    def test_an_empty_collection_on_either_side_matches_nothing(self, service: TaxomeshService) -> None:
        """Whichever end is empty, the answer is ``[]`` — AND with an empty set is empty."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)

        assert (
            service.repository.list_category_parent_links(category_ids=[], parent_category_ids=[parent.category_id])
            == []
        )
        assert (
            service.repository.list_category_parent_links(category_ids=[child.category_id], parent_category_ids=[])
            == []
        )

    def test_ordering_contract_holds_under_both_filters(self, service: TaxomeshService) -> None:
        """The ordering promise is unconditional, so it holds with both filters applied."""
        parent = service.categories.create("Ordered Parent")
        children = [service.categories.create(f"Child {index}") for index in range(3)]
        for index, child in zip((2, 0, 1), children, strict=True):
            service.categories.add_parent(child.category_id, parent.category_id, sort_index=index)

        links = service.repository.list_category_parent_links(
            category_ids=[child.category_id for child in children],
            parent_category_ids=[parent.category_id],
        )

        assert [link.sort_index for link in links] == [0, 1, 2]
