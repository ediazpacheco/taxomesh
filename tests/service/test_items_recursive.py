"""``svc.items.list(recursive=True)`` — the subtree listing.

``list`` takes ``recursive`` as ``search`` does. The traversal it needs is the private candidate
loader ``search`` uses, and the read cost below is asserted as a constant that was *measured*,
not one this file invented.

Three things are pinned here that a naive delegation would get wrong:

* **The order is subtree order, then ``sort_index``.** The repository returns placements ordered
  ``(category_id ASC, sort_index ASC, item_id ASC)`` — *category identifier first*. Ordering the
  result that way makes it a function of randomly generated UUIDs: holding the data fixed and
  swapping which category owns the lower identifier reorders the output, with every other
  assertion still green. ``TestTheOrderDoesNotDependOnIdentifiers`` is what catches that.
* **A dangling placement raises**, exactly as the non-recursive listing already does, so one
  method has one contract. ``search``'s candidate loader keeps skipping silently — the two want
  different things from corrupt data, and the difference is deliberate rather than accidental.
* **The implicit root is refused.** Descending from it would return *every item placed in the
  root or in a category below it*. Subscript is the door that refuses it, as every member that
  takes a category does, and it costs the same single read for every legal identifier.

Read costs are asserted as an **ordered call list** on all four backends, never as a bare total:
a total of four is reproduced by any four reads, including the wrong four.
"""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError
from tests.service.conftest import CountedService, InMemoryRepository

# A recursive listing issues exactly these four reads, in this order, once each — whatever the
# depth of the subtree. Measured at depths 1, 2, 4 and 8 before being written down.
RECURSIVE_READS = 4
RECURSIVE_CALLS = [
    "find_category",
    "list_category_parent_links",
    "list_item_parent_links",
    "map_items_by_id",
]

# The non-recursive listing costs one read fewer: it needs no category-parent links, because it
# never leaves the category it was given.
NON_RECURSIVE_READS = 3

# Depths the constant is asserted at. A subtree deep enough that a per-level read would be
# obvious, and cheap enough to build on every backend.
DEPTHS = [1, 2, 4, 8]


def build_chain(service: TaxomeshService, depth: int) -> list[Category]:
    """Build a chain of ``depth`` categories, each holding one item, and return it top-first."""
    chain: list[Category] = []
    parent: Category | None = None
    for level in range(depth):
        category = service.categories.create(f"c{level}")
        if parent is not None:
            service.categories.add_parent(category.category_id, parent.category_id)
        item = service.items.create(f"i{level}")
        service.items.place_in(item.item_id, category.category_id)
        chain.append(category)
        parent = category
    return chain


class TestTheSubtreeIsReturnedWhole:
    """Every descendant's items, and each item exactly once."""

    def test_it_returns_the_items_of_every_descendant(self, service: TaxomeshService) -> None:
        chain = build_chain(service, 3)
        service._cache.clear()

        rows = service.items.list(category=chain[0].category_id, recursive=True)

        assert [row.name for row in rows] == ["i0", "i1", "i2"]

    def test_the_default_lists_only_the_category_itself(self, service: TaxomeshService) -> None:
        """``recursive`` defaults to ``False``: the category's own items only."""
        chain = build_chain(service, 3)
        service._cache.clear()

        assert [row.name for row in service.items.list(category=chain[0].category_id)] == ["i0"]

    def test_an_item_in_a_category_and_its_descendant_appears_once(self, service: TaxomeshService) -> None:
        """The DAG double-counts it in the placements; the listing must not."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        item = service.items.create("Shared")
        service.items.place_in(item.item_id, parent.category_id)
        service.items.place_in(item.item_id, child.category_id)
        service._cache.clear()

        rows = service.items.list(category=parent.category_id, recursive=True)

        assert [row.item_id for row in rows] == [item.item_id]

    def test_a_leaf_returns_what_the_non_recursive_listing_returns(self, service: TaxomeshService) -> None:
        """A leaf: the same items, though not the same read count, see below."""
        chain = build_chain(service, 1)
        service._cache.clear()

        recursive = service.items.list(category=chain[0].category_id, recursive=True)
        service._cache.clear()
        direct = service.items.list(category=chain[0].category_id)

        assert [row.item_id for row in recursive] == [row.item_id for row in direct]

    def test_a_category_with_no_items_anywhere_in_its_subtree_is_empty(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        service._cache.clear()

        assert service.items.list(category=parent.category_id, recursive=True) == ()


class TestTheOrder:
    """Subtree order, then ``sort_index`` — and first placement wins."""

    def test_items_come_in_subtree_order_then_sort_index(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        for name, category, sort_index in (
            ("second", parent, 1),
            ("first", parent, 0),
            ("fourth", child, 1),
            ("third", child, 0),
        ):
            item = service.items.create(name)
            service.items.place_in(item.item_id, category.category_id, sort_index=sort_index)
        service._cache.clear()

        rows = service.items.list(category=parent.category_id, recursive=True)

        assert [row.name for row in rows] == ["first", "second", "third", "fourth"]

    def test_the_first_placement_decides_where_a_shared_item_appears(self, service: TaxomeshService) -> None:
        """An item in both a category and its descendant takes the ancestor's position."""
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        shared = service.items.create("Shared")
        other = service.items.create("Other")
        service.items.place_in(shared.item_id, parent.category_id, sort_index=0)
        service.items.place_in(other.item_id, child.category_id, sort_index=0)
        service.items.place_in(shared.item_id, child.category_id, sort_index=1)
        service._cache.clear()

        rows = service.items.list(category=parent.category_id, recursive=True)

        assert [row.name for row in rows] == ["Shared", "Other"]


class TestTheOrderDoesNotDependOnIdentifiers:
    """The order must not be a function of randomly generated UUIDs.

    In-memory only, and deliberately so: this builds categories with *chosen* identifiers below
    the service boundary, which is a statement about ordering rather than about backend parity.
    The behaviour every backend shares is asserted by the classes above, which run on all four.

    The repository orders placements ``(category_id ASC, sort_index ASC, item_id ASC)``. Ordering
    the result that way passes every other test in this file while making the answer depend on
    which category happened to be allocated the lower identifier — so this pins both
    arrangements and requires the same answer from each.
    """

    @staticmethod
    def _service_with(parent_int: int, child_int: int) -> tuple[TaxomeshService, UUID]:
        """Return a service whose parent/child categories carry exactly these identifiers."""
        repository = InMemoryRepository()
        service = TaxomeshService(repository=repository)
        parent_id, child_id = UUID(int=parent_int), UUID(int=child_int)
        repository.save_category(Category(category_id=parent_id, name="Parent"))
        repository.save_category(Category(category_id=child_id, name="Child"))
        repository.save_category_parent_link(CategoryParentLink(category_id=child_id, parent_category_id=parent_id))
        in_parent, in_child = UUID(int=101), UUID(int=102)
        repository.save_item(Item(item_id=in_parent, name="in-parent"))
        repository.save_item(Item(item_id=in_child, name="in-child"))
        repository.save_item_parent_link(ItemParentLink(item_id=in_parent, category_id=parent_id, sort_index=0))
        repository.save_item_parent_link(ItemParentLink(item_id=in_child, category_id=child_id, sort_index=0))
        service._cache.clear()
        return service, parent_id

    @pytest.mark.parametrize(
        ("parent_int", "child_int"),
        [(1, 2), (9, 2)],
        ids=["parent_id_below_child_id", "parent_id_above_child_id"],
    )
    def test_the_parent_comes_first_whichever_identifier_is_lower(self, parent_int: int, child_int: int) -> None:
        service, parent_id = self._service_with(parent_int, child_int)

        rows = service.items.list(category=parent_id, recursive=True)

        assert [row.name for row in rows] == ["in-parent", "in-child"]


class TestTheReadCost:
    """A constant four reads at every depth, on all four backends."""

    @pytest.mark.parametrize("depth", DEPTHS)
    def test_it_costs_four_reads_in_order_at_every_depth(self, counting_service: CountedService, depth: int) -> None:
        """The ordered list is the assertion. A bare total of four proves nothing about which four."""
        chain = build_chain(counting_service.service, depth)
        counting_service.cold()

        rows = counting_service.service.items.list(category=chain[0].category_id, recursive=True)

        assert len(rows) == depth
        assert counting_service.reads.total == RECURSIVE_READS
        assert counting_service.reads.calls == RECURSIVE_CALLS

    def test_it_costs_one_read_more_than_the_non_recursive_listing(self, counting_service: CountedService) -> None:
        """Recorded rather than glossed: the extra read is the category-parent links.

        A recursive listing of a *leaf* answers the items the non-recursive listing does, but
        not at the same cost. Descending needs the adjacency, and the traversal cannot know a
        category is a leaf until it has read the links that would say otherwise.
        """
        chain = build_chain(counting_service.service, 1)
        counting_service.cold()

        counting_service.service.items.list(category=chain[0].category_id)
        assert counting_service.reads.total == NON_RECURSIVE_READS

        counting_service.cold()
        counting_service.service.items.list(category=chain[0].category_id, recursive=True)

        assert counting_service.reads.total == RECURSIVE_READS
        assert counting_service.reads.total == NON_RECURSIVE_READS + 1

    def test_a_second_identical_call_is_free(self, counting_service: CountedService) -> None:
        """``list`` is memoized, so the repeat reads nothing."""
        chain = build_chain(counting_service.service, 3)
        counting_service.cold()

        counting_service.service.items.list(category=chain[0].category_id, recursive=True)
        counting_service.service.items.list(category=chain[0].category_id, recursive=True)

        assert counting_service.reads.total == RECURSIVE_READS

    def test_spelling_the_default_shares_the_cache_entry(self, counting_service: CountedService) -> None:
        """``list(category=X)`` and ``list(category=X, recursive=False)`` are one cache entry.

        ``list`` passes every argument, defaults included, to the cached read behind it, so a
        default written out keys the same entry as one left out, and the second call reads nothing.
        """
        chain = build_chain(counting_service.service, 2)
        counting_service.cold()

        counting_service.service.items.list(category=chain[0].category_id)
        counting_service.service.items.list(category=chain[0].category_id, recursive=False)

        assert counting_service.reads.calls == ["find_category", "list_item_parent_links", "map_items_by_id"]
        assert counting_service.reads.total == NON_RECURSIVE_READS


class TestTheEnabledFilter:
    """One ``enabled``, one meaning — ``True`` only, ``False`` only, ``None`` all."""

    @pytest.mark.parametrize(
        ("enabled", "expected"),
        [(True, ["i0"]), (False, ["i1"]), (None, ["i0", "i1"])],
        ids=["enabled", "disabled", "all"],
    )
    def test_it_filters_the_subtree_by_enabled_state(
        self, service: TaxomeshService, enabled: bool | None, expected: list[str]
    ) -> None:
        chain = build_chain(service, 2)
        disabled = service.items.list(category=chain[1].category_id)[0]
        service.items.update(disabled.item_id, enabled=False)
        service._cache.clear()

        rows = service.items.list(category=chain[0].category_id, recursive=True, enabled=enabled)

        assert [row.name for row in rows] == expected


class TestBrokenData:
    """What a subtree listing does with data the write path would have refused."""

    def test_a_stored_cycle_terminates(self, service: TaxomeshService) -> None:
        """``check_no_cycle`` guards writes only; rows also arrive by SQL, migration or restore.

        The link is written below the service boundary for exactly that reason — the service
        would refuse it, and the point is that a listing survives data the service never made.
        """
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        service.repository.save_category_parent_link(
            CategoryParentLink(category_id=parent.category_id, parent_category_id=child.category_id)
        )
        item = service.items.create("Thing")
        service.items.place_in(item.item_id, child.category_id)
        service._cache.clear()

        rows = service.items.list(category=parent.category_id, recursive=True)

        assert [row.item_id for row in rows] == [item.item_id]

    def test_a_dangling_placement_raises(self) -> None:
        """Like the non-recursive listing, and unlike ``search``'s candidate loader.

        In-memory only: the link points at an item row that never existed, which a backend
        enforcing referential integrity would refuse to store in the first place.
        """
        repository = InMemoryRepository()
        service = TaxomeshService(repository=repository)
        parent = service.categories.create("Parent")
        child = service.categories.create("Child")
        service.categories.add_parent(child.category_id, parent.category_id)
        repository.save_item_parent_link(ItemParentLink(item_id=uuid4(), category_id=child.category_id))
        service._cache.clear()

        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.list(category=parent.category_id, recursive=True)

    def test_an_unknown_category_raises_before_any_traversal(self, service: TaxomeshService) -> None:
        service.categories.create("Parent")
        service._cache.clear()

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.list(category=uuid4(), recursive=True)


class TestTheImplicitRoot:
    """The implicit root is invisible to every public read, this one included."""

    def test_the_root_is_refused_as_a_subtree_root(self, service: TaxomeshService) -> None:
        """Permitting it returns every item in or below the root, under a listing asked for one subtree."""
        build_chain(service, 3)
        service._cache.clear()

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.list(category=service._root_id, recursive=True)
