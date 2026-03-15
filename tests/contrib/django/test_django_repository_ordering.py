"""Ordering tests for DjangoRepository collection-returning methods (034-default-sort-index)."""

from uuid import uuid4

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink  # noqa: E402

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# US1 — Link-list ordering
# ---------------------------------------------------------------------------


class TestListCategoryParentLinksOrdering:
    """list_category_parent_links() groups by parent_category_id then sort_index."""

    def test_grouped_by_parent_then_sort_index(self) -> None:
        """Links spanning two parents are grouped by parent, ordered by sort_index within group."""
        repo = DjangoRepository()
        p1 = uuid4()
        p2 = uuid4()
        c_a = uuid4()
        c_b = uuid4()
        c_c = uuid4()
        repo.save_category(Category(category_id=p1, name="P1"))
        repo.save_category(Category(category_id=p2, name="P2"))
        repo.save_category(Category(category_id=c_a, name="CA"))
        repo.save_category(Category(category_id=c_b, name="CB"))
        repo.save_category(Category(category_id=c_c, name="CC"))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_c, parent_category_id=p2, sort_index=5))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_b, parent_category_id=p1, sort_index=2))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_a, parent_category_id=p1, sort_index=0))

        links = repo.list_category_parent_links()
        assert len(links) == 3
        p1_links = [lnk for lnk in links if lnk.parent_category_id == p1]
        p2_links = [lnk for lnk in links if lnk.parent_category_id == p2]
        assert [lnk.sort_index for lnk in p1_links] == [0, 2]
        first_group, second_group = (p1_links, p2_links) if str(p1) < str(p2) else (p2_links, p1_links)
        assert links.index(first_group[-1]) < links.index(second_group[0])

    def test_empty_returns_empty_list(self) -> None:
        repo = DjangoRepository()
        assert repo.list_category_parent_links() == []

    def test_negative_sort_index_sorts_first(self) -> None:
        repo = DjangoRepository()
        parent = uuid4()
        c_a = uuid4()
        c_b = uuid4()
        repo.save_category(Category(category_id=parent, name="Parent"))
        repo.save_category(Category(category_id=c_a, name="CA"))
        repo.save_category(Category(category_id=c_b, name="CB"))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_a, parent_category_id=parent, sort_index=5))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_b, parent_category_id=parent, sort_index=-1))

        links = repo.list_category_parent_links()
        assert links[0].sort_index == -1
        assert links[1].sort_index == 5


class TestListItemParentLinksOrdering:
    """list_item_parent_links() groups by category_id then sort_index."""

    def test_grouped_by_category_then_sort_index(self) -> None:
        """Links spanning two categories are grouped by category, ordered by sort_index within group."""
        repo = DjangoRepository()
        cat1 = uuid4()
        cat2 = uuid4()
        i_a = uuid4()
        i_b = uuid4()
        i_c = uuid4()
        repo.save_category(Category(category_id=cat1, name="Cat1"))
        repo.save_category(Category(category_id=cat2, name="Cat2"))
        repo.save_item(Item(item_id=i_a, name="IA"))
        repo.save_item(Item(item_id=i_b, name="IB"))
        repo.save_item(Item(item_id=i_c, name="IC"))
        repo.save_item_parent_link(ItemParentLink(item_id=i_c, category_id=cat2, sort_index=3))
        repo.save_item_parent_link(ItemParentLink(item_id=i_b, category_id=cat1, sort_index=10))
        repo.save_item_parent_link(ItemParentLink(item_id=i_a, category_id=cat1, sort_index=1))

        links = repo.list_item_parent_links()
        cat1_links = [lnk for lnk in links if lnk.category_id == cat1]
        cat2_links = [lnk for lnk in links if lnk.category_id == cat2]
        assert [lnk.sort_index for lnk in cat1_links] == [1, 10]
        first_group, second_group = (cat1_links, cat2_links) if str(cat1) < str(cat2) else (cat2_links, cat1_links)
        assert links.index(first_group[-1]) < links.index(second_group[0])

    def test_empty_returns_empty_list(self) -> None:
        repo = DjangoRepository()
        assert repo.list_item_parent_links() == []


class TestListItemRelationLinksOrdering:
    """list_item_relation_links() orders by sort_index."""

    def test_ordered_by_sort_index(self) -> None:
        repo = DjangoRepository()
        src = uuid4()
        t1, t2, t3 = uuid4(), uuid4(), uuid4()
        repo.save_item(Item(item_id=src, name="Src"))
        repo.save_item(Item(item_id=t1, name="T1"))
        repo.save_item(Item(item_id=t2, name="T2"))
        repo.save_item(Item(item_id=t3, name="T3"))
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t1, relation_type="ref", sort_index=10)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t2, relation_type="ref", sort_index=3)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t3, relation_type="ref", sort_index=7)
        )

        links = repo.list_item_relation_links(src)
        assert [lnk.sort_index for lnk in links] == [3, 7, 10]

    def test_ordering_preserved_with_filters(self) -> None:
        repo = DjangoRepository()
        src = uuid4()
        t1, t2 = uuid4(), uuid4()
        repo.save_item(Item(item_id=src, name="Src"))
        repo.save_item(Item(item_id=t1, name="T1"))
        repo.save_item(Item(item_id=t2, name="T2"))
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t1, relation_type="ref", sort_index=5)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t2, relation_type="ref", sort_index=1)
        )

        links = repo.list_item_relation_links(src, relation_type="ref")
        assert [lnk.sort_index for lnk in links] == [1, 5]

    def test_empty_returns_empty_list(self) -> None:
        repo = DjangoRepository()
        assert repo.list_item_relation_links(uuid4()) == []


# ---------------------------------------------------------------------------
# US2 — Category and item listing order
# ---------------------------------------------------------------------------


class TestListCategoriesOrdering:
    """list_categories() returns all categories ordered by name then category_id."""

    def test_ordered_by_name(self) -> None:
        repo = DjangoRepository()
        repo.save_category(Category(name="Zebra"))
        repo.save_category(Category(name="Alpha"))
        repo.save_category(Category(name="Mango"))

        cats = repo.list_categories()
        assert [c.name for c in cats] == ["Alpha", "Mango", "Zebra"]

    def test_tie_breaker_by_category_id(self) -> None:
        repo = DjangoRepository()
        c1 = Category(name="Same")
        c2 = Category(name="Same")
        repo.save_category(c2)
        repo.save_category(c1)

        cats = repo.list_categories()
        ids = [str(c.category_id) for c in cats]
        assert ids == sorted(ids)

    def test_empty_returns_empty_list(self) -> None:
        repo = DjangoRepository()
        assert repo.list_categories() == []


class TestListItemsOrdering:
    """list_items() returns all items ordered by name then item_id."""

    def test_ordered_by_name(self) -> None:
        repo = DjangoRepository()
        repo.save_item(Item(name="Zeta"))
        repo.save_item(Item(name="Alpha"))
        repo.save_item(Item(name="Mu"))

        items = repo.list_items()
        assert [i.name for i in items] == ["Alpha", "Mu", "Zeta"]

    def test_tie_breaker_by_item_id(self) -> None:
        repo = DjangoRepository()
        i1 = Item(name="Same")
        i2 = Item(name="Same")
        repo.save_item(i2)
        repo.save_item(i1)

        items = repo.list_items()
        ids = [str(i.item_id) for i in items]
        assert ids == sorted(ids)

    def test_empty_returns_empty_list(self) -> None:
        repo = DjangoRepository()
        assert repo.list_items() == []


# ---------------------------------------------------------------------------
# US3 — External-ID list ordering
# ---------------------------------------------------------------------------


class TestListItemsByExternalIdOrdering:
    """list_items_by_external_id() returns matches ordered by name then item_id."""

    def test_ordered_by_name(self) -> None:
        repo = DjangoRepository()
        ext = "shared-ext"
        repo.save_item(Item(name="Zeta", external_id=ext))
        repo.save_item(Item(name="Alpha", external_id=ext))
        repo.save_item(Item(name="Mu", external_id=ext))

        items = repo.list_items_by_external_id(ext)
        assert [i.name for i in items] == ["Alpha", "Mu", "Zeta"]

    def test_no_match_returns_empty(self) -> None:
        repo = DjangoRepository()
        assert repo.list_items_by_external_id("nonexistent") == []


class TestListCategoriesByExternalIdOrdering:
    """list_categories_by_external_id() returns matches ordered by name then category_id."""

    def test_ordered_by_name(self) -> None:
        repo = DjangoRepository()
        ext = "shared-cat-ext"
        repo.save_category(Category(name="Omega", external_id=ext))
        repo.save_category(Category(name="Beta", external_id=ext))
        repo.save_category(Category(name="Gamma", external_id=ext))

        cats = repo.list_categories_by_external_id(ext)
        assert [c.name for c in cats] == ["Beta", "Gamma", "Omega"]

    def test_no_match_returns_empty(self) -> None:
        repo = DjangoRepository()
        assert repo.list_categories_by_external_id("nonexistent") == []
