"""Failing tests for TaxomeshService.reorder_items_in_category (TDD — method not yet implemented)."""

from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError


class TestReorderItemsInCategory:
    def test_reorder_writes_correct_sort_indices(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="fruit")
        item_a = service.create_item(name="apple")
        item_b = service.create_item(name="banana")
        item_c = service.create_item(name="cherry")
        service.place_item_in_category(item_a.item_id, cat.category_id, sort_index=0)
        service.place_item_in_category(item_b.item_id, cat.category_id, sort_index=1)
        service.place_item_in_category(item_c.item_id, cat.category_id, sort_index=2)

        service.reorder_items_in_category(cat.category_id, [item_c.item_id, item_a.item_id, item_b.item_id])

        ordered = service.list_items(category_id=cat.category_id)
        assert [i.item_id for i in ordered] == [item_c.item_id, item_a.item_id, item_b.item_id]

        links = service._repo.list_item_parent_links()
        by_item: dict[UUID, int] = {lnk.item_id: lnk.sort_index for lnk in links if lnk.category_id == cat.category_id}
        assert by_item[item_c.item_id] == 0
        assert by_item[item_a.item_id] == 1
        assert by_item[item_b.item_id] == 2

    def test_reorder_unknown_category_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.reorder_items_in_category(uuid4(), [uuid4()])

    def test_reorder_uuid_not_in_category_raises(self, service: TaxomeshService) -> None:
        cat = service.create_category(name="veg")
        item_a = service.create_item(name="artichoke")
        item_b = service.create_item(name="broccoli")
        service.place_item_in_category(item_a.item_id, cat.category_id, sort_index=0)
        service.place_item_in_category(item_b.item_id, cat.category_id, sort_index=1)

        with pytest.raises(ValueError):
            service.reorder_items_in_category(cat.category_id, [item_a.item_id, uuid4()])


class TestReorderSubcategories:
    def test_reorder_subcategories_writes_correct_sort_indices(self, service: TaxomeshService) -> None:
        parent = service.create_category(name="parent")
        child_a = service.create_category(name="child_a")
        child_b = service.create_category(name="child_b")
        child_c = service.create_category(name="child_c")
        service.add_category_parent(child_a.category_id, parent.category_id, sort_index=0)
        service.add_category_parent(child_b.category_id, parent.category_id, sort_index=1)
        service.add_category_parent(child_c.category_id, parent.category_id, sort_index=2)

        service.reorder_subcategories(
            parent.category_id,
            [child_c.category_id, child_a.category_id, child_b.category_id],
        )

        ordered = service.list_categories(parent_id=parent.category_id)
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

    def test_reorder_subcategories_unknown_parent_raises(self, service: TaxomeshService) -> None:
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.reorder_subcategories(uuid4(), [uuid4()])

    def test_reorder_subcategories_uuid_not_a_child_raises(self, service: TaxomeshService) -> None:
        parent = service.create_category(name="parent")
        child_a = service.create_category(name="child_a")
        child_b = service.create_category(name="child_b")
        service.add_category_parent(child_a.category_id, parent.category_id, sort_index=0)
        service.add_category_parent(child_b.category_id, parent.category_id, sort_index=1)

        with pytest.raises(ValueError):
            service.reorder_subcategories(parent.category_id, [child_a.category_id, uuid4()])


class TestReparentItem:
    def test_reparent_item_moves_from_old_to_new_category(self, service: TaxomeshService) -> None:
        cat_a = service.create_category(name="A")
        cat_b = service.create_category(name="B")
        item_x = service.create_item(name="X")
        item_y = service.create_item(name="Y")
        service.place_item_in_category(item_x.item_id, cat_a.category_id, sort_index=0)
        service.place_item_in_category(item_y.item_id, cat_b.category_id, sort_index=0)

        service.reparent_item(item_x.item_id, cat_a.category_id, cat_b.category_id, None)

        items_in_a = service.list_items(category_id=cat_a.category_id)
        assert item_x.item_id not in [i.item_id for i in items_in_a]

        items_in_b = service.list_items(category_id=cat_b.category_id)
        assert item_x.item_id in [i.item_id for i in items_in_b]

    def test_reparent_item_inserts_at_correct_position(self, service: TaxomeshService) -> None:
        cat_b = service.create_category(name="B")
        item_y = service.create_item(name="Y")
        item_z = service.create_item(name="Z")
        service.place_item_in_category(item_y.item_id, cat_b.category_id, sort_index=0)
        service.place_item_in_category(item_z.item_id, cat_b.category_id, sort_index=1)

        cat_a = service.create_category(name="A")
        item_x = service.create_item(name="X")
        service.place_item_in_category(item_x.item_id, cat_a.category_id, sort_index=0)

        service.reparent_item(item_x.item_id, cat_a.category_id, cat_b.category_id, item_y.item_id)

        ordered = service.list_items(category_id=cat_b.category_id)
        assert [i.item_id for i in ordered] == [item_x.item_id, item_y.item_id, item_z.item_id]

        links = service._repo.list_item_parent_links()
        by_item = {lnk.item_id: lnk.sort_index for lnk in links if lnk.category_id == cat_b.category_id}
        assert by_item[item_x.item_id] == 0
        assert by_item[item_y.item_id] == 1
        assert by_item[item_z.item_id] == 2

    def test_reparent_item_inserts_at_end_when_insert_before_is_none(self, service: TaxomeshService) -> None:
        cat_b = service.create_category(name="B")
        item_y = service.create_item(name="Y")
        item_z = service.create_item(name="Z")
        service.place_item_in_category(item_y.item_id, cat_b.category_id, sort_index=0)
        service.place_item_in_category(item_z.item_id, cat_b.category_id, sort_index=1)

        cat_a = service.create_category(name="A")
        item_x = service.create_item(name="X")
        service.place_item_in_category(item_x.item_id, cat_a.category_id, sort_index=0)

        service.reparent_item(item_x.item_id, cat_a.category_id, cat_b.category_id, None)

        ordered = service.list_items(category_id=cat_b.category_id)
        assert [i.item_id for i in ordered] == [item_y.item_id, item_z.item_id, item_x.item_id]

    def test_reparent_item_unknown_item_raises(self, service: TaxomeshService) -> None:
        cat_a = service.create_category(name="A")
        cat_b = service.create_category(name="B")

        with pytest.raises(TaxomeshItemNotFoundError):
            service.reparent_item(uuid4(), cat_a.category_id, cat_b.category_id, None)

    def test_reparent_item_unknown_old_category_raises(self, service: TaxomeshService) -> None:
        item_x = service.create_item(name="X")
        cat_b = service.create_category(name="B")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.reparent_item(item_x.item_id, uuid4(), cat_b.category_id, None)


class TestReparentCategory:
    def test_reparent_category_moves_from_old_to_new_parent(self, service: TaxomeshService) -> None:
        old_parent = service.create_category(name="RCOldParent")
        new_parent = service.create_category(name="RCNewParent")
        child = service.create_category(name="RCChild")
        service.add_category_parent(child.category_id, old_parent.category_id, sort_index=0)

        service.reparent_category(child.category_id, old_parent.category_id, new_parent.category_id, None)

        old_children = service.list_categories(parent_id=old_parent.category_id)
        assert child.category_id not in [c.category_id for c in old_children]

        new_children = service.list_categories(parent_id=new_parent.category_id)
        assert child.category_id in [c.category_id for c in new_children]

    def test_reparent_category_inserts_at_correct_position(self, service: TaxomeshService) -> None:
        new_parent = service.create_category(name="RCNewParentPos")
        sibling_a = service.create_category(name="RCSibA")
        sibling_b = service.create_category(name="RCSibB")
        service.add_category_parent(sibling_a.category_id, new_parent.category_id, sort_index=0)
        service.add_category_parent(sibling_b.category_id, new_parent.category_id, sort_index=1)

        old_parent = service.create_category(name="RCOldParentPos")
        child = service.create_category(name="RCChildPos")
        service.add_category_parent(child.category_id, old_parent.category_id, sort_index=0)

        service.reparent_category(
            child.category_id, old_parent.category_id, new_parent.category_id, sibling_a.category_id
        )

        ordered = service.list_categories(parent_id=new_parent.category_id)
        assert [c.category_id for c in ordered] == [
            child.category_id,
            sibling_a.category_id,
            sibling_b.category_id,
        ]

    def test_reparent_category_cycle_raises(self, service: TaxomeshService) -> None:
        from taxomesh.exceptions import TaxomeshCyclicDependencyError  # noqa: PLC0415

        ancestor_parent = service.create_category(name="RCAncestorParent")
        ancestor = service.create_category(name="RCAncestor")
        descendant = service.create_category(name="RCDescendant")
        service.add_category_parent(ancestor.category_id, ancestor_parent.category_id, sort_index=0)
        service.add_category_parent(descendant.category_id, ancestor.category_id, sort_index=0)

        # Moving ancestor under descendant would create a cycle
        with pytest.raises(TaxomeshCyclicDependencyError):
            service.reparent_category(ancestor.category_id, ancestor_parent.category_id, descendant.category_id, None)

    def test_reparent_category_unknown_category_raises(self, service: TaxomeshService) -> None:
        parent = service.create_category(name="RCParentNF")
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.reparent_category(uuid4(), parent.category_id, parent.category_id, None)

    def test_reparent_category_unknown_old_parent_raises(self, service: TaxomeshService) -> None:
        child = service.create_category(name="RCChildOldNF")
        new_parent = service.create_category(name="RCNewParentOldNF")
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.reparent_category(child.category_id, uuid4(), new_parent.category_id, None)
