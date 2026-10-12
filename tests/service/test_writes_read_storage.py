"""A write reads what it changes from storage, so another service's change is never undone.

Two services share one repository here, each with its own cache at the default lifetime. Service
``a`` reads a row, so its cache holds it; service ``b`` then changes or deletes that row. Whatever
``a`` writes next is built on, and checked against, the stored row rather than the one ``a``'s cache
still holds: an update keeps ``b``'s rename, an update of a deleted row raises not-found, and a link
write naming a deleted row raises not-found and stores no link. On all four backends;
``tests/contrib/django/test_django_two_repositories.py`` runs the same cases over two Django
repositories on one database.
"""

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError


@pytest.fixture
def other(service: TaxomeshService) -> TaxomeshService:
    """A second service over the same repository, with its own cache."""
    return TaxomeshService(repository=service.repository)


class TestAnUpdateKeepsAnotherServicesChange:
    """``update`` builds the new row from the stored row, not from the cached one."""

    @pytest.mark.parametrize("by_row", [True, False], ids=["row", "uuid"])
    @pytest.mark.parametrize("with_version", [True, False], ids=["version", "no-version"])
    def test_items_update(
        self, service: TaxomeshService, other: TaxomeshService, by_row: bool, with_version: bool
    ) -> None:
        held = service.items.create("Percanta")
        assert service.items[held] == held
        renamed = other.items.update(held, name="Mina")
        version = renamed.version if with_version else None
        target = held if by_row else held.item_id
        updated = service.items.update(target, metadata={"k": 1}, expected_version=version)
        stored = service.repository.find_item(held.item_id)
        assert stored is not None
        assert (updated.name, stored.name, stored.version, dict(stored.metadata)) == ("Mina", "Mina", 2, {"k": 1})

    @pytest.mark.parametrize("by_row", [True, False], ids=["row", "uuid"])
    @pytest.mark.parametrize("with_version", [True, False], ids=["version", "no-version"])
    def test_categories_update(
        self, service: TaxomeshService, other: TaxomeshService, by_row: bool, with_version: bool
    ) -> None:
        held = service.categories.create("Tango")
        assert service.categories[held] == held
        renamed = other.categories.update(held, name="Milonga")
        version = renamed.version if with_version else None
        target = held if by_row else held.category_id
        updated = service.categories.update(target, description="danced", expected_version=version)
        stored = service.repository.find_category(held.category_id)
        assert stored is not None
        assert (updated.name, stored.name, stored.version, stored.description) == ("Milonga", "Milonga", 2, "danced")

    def test_tags_update(self, service: TaxomeshService, other: TaxomeshService) -> None:
        held = service.tags.create("featured")
        assert service.tags[held] == held
        other.tags.update(held, name="pinned")
        service.tags.update(held, metadata={"k": 1})
        stored = service.repository.find_tag(held.tag_id)
        assert stored is not None
        assert (stored.name, dict(stored.metadata)) == ("pinned", {"k": 1})


class TestAnUpdateOfADeletedRow:
    """A row another service deleted is not stored again."""

    def test_an_item(self, service: TaxomeshService, other: TaxomeshService) -> None:
        held = service.items.create("Percanta")
        assert service.items[held] == held
        other.items.delete(held)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.update(held, name="Mina")
        assert service.repository.find_item(held.item_id) is None

    def test_a_category(self, service: TaxomeshService, other: TaxomeshService) -> None:
        held = service.categories.create("Tango")
        assert service.categories[held] == held
        other.categories.delete(held)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.update(held, name="Milonga")
        assert service.repository.find_category(held.category_id) is None


class TestALinkWriteNamingADeletedRow:
    """Each row a link write names is checked in storage, so no link names a deleted row."""

    def test_place_in_a_deleted_item(self, service: TaxomeshService, other: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        category = service.categories.create("Tango")
        assert (service.items[item], service.categories[category]) == (item, category)
        other.items.delete(item)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.place_in(item, category)
        assert not service.repository.list_item_parent_links(item_ids=[item.item_id])

    def test_place_in_a_deleted_category(self, service: TaxomeshService, other: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        category = service.categories.create("Tango")
        assert (service.items[item], service.categories[category]) == (item, category)
        other.categories.delete(category)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.place_in(item, category)
        assert not service.repository.list_item_parent_links(category_ids=[category.category_id])

    def test_relate_to_a_deleted_item(self, service: TaxomeshService, other: TaxomeshService) -> None:
        source = service.items.create("Percanta")
        target = service.items.create("Mina")
        assert (service.items[source], service.items[target]) == (source, target)
        other.items.delete(target)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.relate(source, target, "related_to")
        assert not service.repository.list_item_relation_links(source.item_id)

    def test_items_move_a_deleted_item(self, service: TaxomeshService, other: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        leaving = service.categories.create("Tango")
        joining = service.categories.create("Milonga")
        service.items.place_in(item, leaving)
        assert service.items[item] == item
        other.items.delete(item)
        with pytest.raises(TaxomeshItemNotFoundError):
            service.items.move(item, from_category=leaving, to_category=joining)
        assert not service.repository.list_item_parent_links(item_ids=[item.item_id])

    def test_items_move_into_a_deleted_category(self, service: TaxomeshService, other: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        leaving = service.categories.create("Tango")
        joining = service.categories.create("Milonga")
        service.items.place_in(item, leaving)
        assert service.categories[joining] == joining
        other.categories.delete(joining)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.move(item, from_category=leaving, to_category=joining)
        links = service.repository.list_item_parent_links(item_ids=[item.item_id])
        assert [link.category_id for link in links] == [leaving.category_id]

    def test_categories_move_under_a_deleted_parent(self, service: TaxomeshService, other: TaxomeshService) -> None:
        category = service.categories.create("Tango")
        parent = service.categories.create("Music")
        assert (service.categories[category], service.categories[parent]) == (category, parent)
        other.categories.delete(parent)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(category, from_parent=None, to_parent=parent)
        assert not service.repository.list_category_parent_links(parent_category_ids=[parent.category_id])
        assert [row.name for row in other.categories.roots()] == ["Tango"]

    def test_categories_move_a_deleted_category(self, service: TaxomeshService, other: TaxomeshService) -> None:
        category = service.categories.create("Tango")
        parent = service.categories.create("Music")
        assert (service.categories[category], service.categories[parent]) == (category, parent)
        other.categories.delete(category)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.move(category, from_parent=None, to_parent=parent)
        assert not service.repository.list_category_parent_links(category_ids=[category.category_id])
