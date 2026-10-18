"""Ordering and moving: ``items.reorder``, ``categories.reorder``, ``items.move`` and ``categories.move``."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError, TaxomeshValidationError


class TestItemsReorder:
    def test_reorder_writes_correct_sort_indices(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="fruit")
        item_a = service.items.create(name="apple")
        item_b = service.items.create(name="banana")
        item_c = service.items.create(name="cherry")
        service.items.place_in(item_a.item_id, cat.category_id, sort_index=0)
        service.items.place_in(item_b.item_id, cat.category_id, sort_index=1)
        service.items.place_in(item_c.item_id, cat.category_id, sort_index=2)

        service.items.reorder(cat.category_id, [item_c.item_id, item_a.item_id, item_b.item_id])

        ordered = service.items.list(category=cat.category_id)
        assert [i.item_id for i in ordered] == [item_c.item_id, item_a.item_id, item_b.item_id]

        links = service._repo.list_item_parent_links()
        by_item: dict[UUID, int] = {lnk.item_id: lnk.sort_index for lnk in links if lnk.category_id == cat.category_id}
        assert by_item[item_c.item_id] == 0
        assert by_item[item_a.item_id] == 1
        assert by_item[item_b.item_id] == 2

    def test_reorder_unknown_category_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.reorder(uuid4(), [uuid4()])

    def test_reorder_uuid_not_in_category_raises(self, service: TaxomeshService) -> None:
        cat = service.categories.create(name="veg")
        item_a = service.items.create(name="artichoke")
        item_b = service.items.create(name="broccoli")
        service.items.place_in(item_a.item_id, cat.category_id, sort_index=0)
        service.items.place_in(item_b.item_id, cat.category_id, sort_index=1)

        with pytest.raises(ValueError):
            service.items.reorder(cat.category_id, [item_a.item_id, uuid4()])


class TestCategoriesReorder:
    def test_categories_reorder_writes_correct_sort_indices(self, service: TaxomeshService) -> None:
        parent = service.categories.create(name="parent")
        child_a = service.categories.create(name="child_a")
        child_b = service.categories.create(name="child_b")
        child_c = service.categories.create(name="child_c")
        service.categories.add_parent(child_a.category_id, parent.category_id, sort_index=0)
        service.categories.add_parent(child_b.category_id, parent.category_id, sort_index=1)
        service.categories.add_parent(child_c.category_id, parent.category_id, sort_index=2)

        service.categories.reorder(
            parent.category_id,
            [child_c.category_id, child_a.category_id, child_b.category_id],
        )

        ordered = service.categories.list(parent=parent.category_id)
        assert [c.category_id for c in ordered] == [
            child_c.category_id,
            child_a.category_id,
            child_b.category_id,
        ]

        links = service._repo.list_category_parent_links()
        by_child: dict[UUID, int] = {
            lnk.category_id: lnk.sort_index for lnk in links if lnk.parent_category_id == parent.category_id
        }
        assert by_child[child_c.category_id] == 0
        assert by_child[child_a.category_id] == 1
        assert by_child[child_b.category_id] == 2

    def test_categories_reorder_unknown_parent_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.reorder(uuid4(), [uuid4()])

    def test_categories_reorder_uuid_not_a_child_raises(self, service: TaxomeshService) -> None:
        parent = service.categories.create(name="parent")
        child_a = service.categories.create(name="child_a")
        child_b = service.categories.create(name="child_b")
        service.categories.add_parent(child_a.category_id, parent.category_id, sort_index=0)
        service.categories.add_parent(child_b.category_id, parent.category_id, sort_index=1)

        with pytest.raises(ValueError):
            service.categories.reorder(parent.category_id, [child_a.category_id, uuid4()])


class TestItemsMove:
    def test_items_move_relocates_from_old_to_new_category(self, service: TaxomeshService) -> None:
        cat_a = service.categories.create(name="A")
        cat_b = service.categories.create(name="B")
        item_x = service.items.create(name="X")
        item_y = service.items.create(name="Y")
        service.items.place_in(item_x.item_id, cat_a.category_id, sort_index=0)
        service.items.place_in(item_y.item_id, cat_b.category_id, sort_index=0)

        service.items.move(item_x.item_id, from_category=cat_a.category_id, to_category=cat_b.category_id, before=None)

        items_in_a = service.items.list(category=cat_a.category_id)
        assert item_x.item_id not in [i.item_id for i in items_in_a]

        items_in_b = service.items.list(category=cat_b.category_id)
        assert item_x.item_id in [i.item_id for i in items_in_b]

    def test_items_move_inserts_at_correct_position(self, service: TaxomeshService) -> None:
        cat_b = service.categories.create(name="B")
        item_y = service.items.create(name="Y")
        item_z = service.items.create(name="Z")
        service.items.place_in(item_y.item_id, cat_b.category_id, sort_index=0)
        service.items.place_in(item_z.item_id, cat_b.category_id, sort_index=1)

        cat_a = service.categories.create(name="A")
        item_x = service.items.create(name="X")
        service.items.place_in(item_x.item_id, cat_a.category_id, sort_index=0)

        service.items.move(
            item_x.item_id,
            from_category=cat_a.category_id,
            to_category=cat_b.category_id,
            before=item_y.item_id,
        )

        ordered = service.items.list(category=cat_b.category_id)
        assert [i.item_id for i in ordered] == [item_x.item_id, item_y.item_id, item_z.item_id]

        links = service._repo.list_item_parent_links()
        by_item = {lnk.item_id: lnk.sort_index for lnk in links if lnk.category_id == cat_b.category_id}
        assert by_item[item_x.item_id] == 0
        assert by_item[item_y.item_id] == 1
        assert by_item[item_z.item_id] == 2

    def test_items_move_inserts_at_end_when_before_id_is_none(self, service: TaxomeshService) -> None:
        cat_b = service.categories.create(name="B")
        item_y = service.items.create(name="Y")
        item_z = service.items.create(name="Z")
        service.items.place_in(item_y.item_id, cat_b.category_id, sort_index=0)
        service.items.place_in(item_z.item_id, cat_b.category_id, sort_index=1)

        cat_a = service.categories.create(name="A")
        item_x = service.items.create(name="X")
        service.items.place_in(item_x.item_id, cat_a.category_id, sort_index=0)

        service.items.move(item_x.item_id, from_category=cat_a.category_id, to_category=cat_b.category_id, before=None)

        ordered = service.items.list(category=cat_b.category_id)
        assert [i.item_id for i in ordered] == [item_y.item_id, item_z.item_id, item_x.item_id]

    def test_items_move_unknown_item_raises(self, service: TaxomeshService) -> None:
        cat_a = service.categories.create(name="A")
        cat_b = service.categories.create(name="B")

        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.move(uuid4(), from_category=cat_a.category_id, to_category=cat_b.category_id, before=None)

    def test_items_move_unknown_from_category_raises(self, service: TaxomeshService) -> None:
        item_x = service.items.create(name="X")
        cat_b = service.categories.create(name="B")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.move(item_x.item_id, from_category=uuid4(), to_category=cat_b.category_id, before=None)


class TestCategoriesMove:
    def test_categories_move_relocates_from_old_to_new_parent(self, service: TaxomeshService) -> None:
        old_parent = service.categories.create(name="RCOldParent")
        new_parent = service.categories.create(name="RCNewParent")
        child = service.categories.create(name="RCChild")
        service.categories.add_parent(child.category_id, old_parent.category_id, sort_index=0)

        service.categories.move(
            child.category_id,
            from_parent=old_parent.category_id,
            to_parent=new_parent.category_id,
            before=None,
        )

        old_children = service.categories.list(parent=old_parent.category_id)
        assert child.category_id not in [c.category_id for c in old_children]

        new_children = service.categories.list(parent=new_parent.category_id)
        assert child.category_id in [c.category_id for c in new_children]

    def test_categories_move_inserts_at_correct_position(self, service: TaxomeshService) -> None:
        new_parent = service.categories.create(name="RCNewParentPos")
        sibling_a = service.categories.create(name="RCSibA")
        sibling_b = service.categories.create(name="RCSibB")
        service.categories.add_parent(sibling_a.category_id, new_parent.category_id, sort_index=0)
        service.categories.add_parent(sibling_b.category_id, new_parent.category_id, sort_index=1)

        old_parent = service.categories.create(name="RCOldParentPos")
        child = service.categories.create(name="RCChildPos")
        service.categories.add_parent(child.category_id, old_parent.category_id, sort_index=0)

        service.categories.move(
            child.category_id,
            from_parent=old_parent.category_id,
            to_parent=new_parent.category_id,
            before=sibling_a.category_id,
        )

        ordered = service.categories.list(parent=new_parent.category_id)
        assert [c.category_id for c in ordered] == [
            child.category_id,
            sibling_a.category_id,
            sibling_b.category_id,
        ]

    def test_categories_move_cycle_raises(self, service: TaxomeshService) -> None:
        from taxomesh.exceptions import TaxomeshCyclicDependencyError  # noqa: PLC0415

        ancestor_parent = service.categories.create(name="RCAncestorParent")
        ancestor = service.categories.create(name="RCAncestor")
        descendant = service.categories.create(name="RCDescendant")
        service.categories.add_parent(ancestor.category_id, ancestor_parent.category_id, sort_index=0)
        service.categories.add_parent(descendant.category_id, ancestor.category_id, sort_index=0)

        # Moving ancestor under descendant would create a cycle
        with pytest.raises(TaxomeshCyclicDependencyError):
            service.categories.move(
                ancestor.category_id,
                from_parent=ancestor_parent.category_id,
                to_parent=descendant.category_id,
                before=None,
            )

    def test_categories_move_unknown_category_raises(self, service: TaxomeshService) -> None:
        parent = service.categories.create(name="RCParentNF")
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(uuid4(), from_parent=parent.category_id, to_parent=parent.category_id, before=None)

    def test_categories_move_unknown_from_parent_raises(self, service: TaxomeshService) -> None:
        child = service.categories.create(name="RCChildOldNF")
        new_parent = service.categories.create(name="RCNewParentOldNF")
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(
                child.category_id, from_parent=uuid4(), to_parent=new_parent.category_id, before=None
            )


def _stored_links(service: TaxomeshService) -> tuple[set[tuple[UUID, UUID, int]], set[tuple[UUID, UUID, int]]]:
    """Every stored parent link and placement, as ``(child, parent, sort_index)``."""
    repository = service.repository
    return (
        {(lnk.category_id, lnk.parent_category_id, lnk.sort_index) for lnk in repository.list_category_parent_links()},
        {(lnk.item_id, lnk.category_id, lnk.sort_index) for lnk in repository.list_item_parent_links()},
    )


class TestMoveBefore:
    """A ``before`` that is not a sibling in the destination is refused, and the move changes nothing.

    One that names no stored row is a wrong address, and raises the not-found error of its kind. A
    stored row that is not in the destination, the moving row included, is a refused value.
    """

    def test_an_item_not_placed_in_the_destination_is_refused(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved, stayed, elsewhere = (service.items.create(name) for name in ("Moved", "Stayed", "Elsewhere"))
        service.items.place_in(moved, left)
        service.items.place_in(stayed, right)
        service.items.place_in(elsewhere, left)
        links = _stored_links(service)

        with pytest.raises(TaxomeshValidationError) as caught:
            service.items.move(moved, from_category=left, to_category=right, before=elsewhere)

        assert str(elsewhere.item_id) in str(caught.value)
        assert str(right.category_id) in str(caught.value)
        assert _stored_links(service) == links

    def test_the_moving_item_is_refused(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved = service.items.create("Moved")
        service.items.place_in(moved, left)
        service.items.place_in(moved, right)
        links = _stored_links(service)

        with pytest.raises(TaxomeshValidationError) as caught:
            service.items.move(moved, from_category=left, to_category=right, before=moved)

        assert str(moved.item_id) in str(caught.value)
        assert _stored_links(service) == links

    def test_an_unknown_item_changes_nothing(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved = service.items.create("Moved")
        service.items.place_in(moved, left)
        links = _stored_links(service)

        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.move(moved, from_category=left, to_category=right, before=uuid4())

        assert _stored_links(service) == links

    def test_a_category_not_a_child_of_the_destination_is_refused(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved, stayed, elsewhere = (service.categories.create(name) for name in ("Moved", "Stayed", "Elsewhere"))
        service.categories.add_parent(moved, left)
        service.categories.add_parent(stayed, right)
        service.categories.add_parent(elsewhere, left)
        links = _stored_links(service)

        with pytest.raises(TaxomeshValidationError) as caught:
            service.categories.move(moved, from_parent=left, to_parent=right, before=elsewhere)

        assert str(elsewhere.category_id) in str(caught.value)
        assert str(right.category_id) in str(caught.value)
        assert _stored_links(service) == links

    def test_a_category_not_at_the_top_level_is_refused(self, service: TaxomeshService) -> None:
        parent = service.categories.create("Parent")
        moved, child = service.categories.create("Moved"), service.categories.create("Child")
        service.categories.add_parent(moved, parent)
        service.categories.add_parent(child, parent)
        links = _stored_links(service)

        with pytest.raises(TaxomeshValidationError) as caught:
            service.categories.move(moved, from_parent=parent, to_parent=None, before=child)

        assert str(child.category_id) in str(caught.value)
        assert "top level" in str(caught.value)
        assert _stored_links(service) == links

    def test_the_moving_category_is_refused(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved = service.categories.create("Moved")
        service.categories.add_parent(moved, left)
        service.categories.add_parent(moved, right)
        links = _stored_links(service)

        with pytest.raises(TaxomeshValidationError) as caught:
            service.categories.move(moved, from_parent=left, to_parent=right, before=moved)

        assert str(moved.category_id) in str(caught.value)
        assert _stored_links(service) == links

    def test_an_unknown_category_changes_nothing(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved = service.categories.create("Moved")
        service.categories.add_parent(moved, left)
        links = _stored_links(service)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(moved, from_parent=left, to_parent=right, before=uuid4())

        assert _stored_links(service) == links

    def test_a_sibling_is_taken(self, service: TaxomeshService) -> None:
        left, right = service.categories.create("Left"), service.categories.create("Right")
        moved, first, second = (service.items.create(name) for name in ("Moved", "First", "Second"))
        service.items.place_in(moved, left)
        service.items.place_in(first, right)
        service.items.place_in(second, right)

        service.items.move(moved, from_category=left, to_category=right, before=second)

        assert [i.name for i in service.items.list(category=right)] == ["First", "Moved", "Second"]
        assert service.items.list(category=left) == ()
