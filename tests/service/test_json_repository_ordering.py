"""Ordering tests for JsonRepository collection-returning methods (034-default-sort-index)."""

from pathlib import Path
from uuid import uuid4

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink

# ---------------------------------------------------------------------------
# US1 — Link-list ordering
# ---------------------------------------------------------------------------


class TestListCategoryParentLinksOrdering:
    """list_category_parent_links() groups by parent_category_id then sort_index."""

    def test_grouped_by_parent_then_sort_index(self, tmp_json_path: Path) -> None:
        """Links spanning two parents are grouped by parent, ordered by sort_index within group."""
        repo = JsonRepository(tmp_json_path)
        p1 = uuid4()
        p2 = uuid4()
        c_a = uuid4()
        c_b = uuid4()
        c_c = uuid4()
        # Insert in mixed order: p2/sort=5, p1/sort=2, p1/sort=0
        repo.save_category_parent_link(CategoryParentLink(category_id=c_c, parent_category_id=p2, sort_index=5))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_b, parent_category_id=p1, sort_index=2))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_a, parent_category_id=p1, sort_index=0))

        links = repo.list_category_parent_links()
        assert len(links) == 3
        p1_links = [lnk for lnk in links if lnk.parent_category_id == p1]
        p2_links = [lnk for lnk in links if lnk.parent_category_id == p2]
        # Within p1: sort by sort_index ascending
        assert [lnk.sort_index for lnk in p1_links] == [0, 2]
        # Groups must not interleave — whichever parent sorts first comes entirely before the other
        first_group, second_group = (p1_links, p2_links) if str(p1) < str(p2) else (p2_links, p1_links)
        assert links.index(first_group[-1]) < links.index(second_group[0])

    def test_tie_breaker_by_category_id(self, tmp_json_path: Path) -> None:
        """When sort_index and parent_category_id are equal, order by category_id."""
        repo = JsonRepository(tmp_json_path)
        parent = uuid4()
        # Use fixed UUIDs so we know which one is lexicographically first
        c_high = uuid4()
        c_low = uuid4()
        low_str, high_str = sorted([str(c_low), str(c_high)])
        c_first = c_low if str(c_low) == low_str else c_high
        c_second = c_high if str(c_low) == low_str else c_low

        repo.save_category_parent_link(
            CategoryParentLink(category_id=c_second, parent_category_id=parent, sort_index=1)
        )
        repo.save_category_parent_link(
            CategoryParentLink(category_id=c_first, parent_category_id=parent, sort_index=1)
        )

        links = repo.list_category_parent_links()
        assert links[0].category_id == c_first
        assert links[1].category_id == c_second

    def test_empty_returns_empty_list(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_category_parent_links() == []

    def test_negative_sort_index_sorts_first(self, tmp_json_path: Path) -> None:
        """Negative sort_index values sort before non-negative."""
        repo = JsonRepository(tmp_json_path)
        parent = uuid4()
        c_a = uuid4()
        c_b = uuid4()
        repo.save_category_parent_link(CategoryParentLink(category_id=c_a, parent_category_id=parent, sort_index=5))
        repo.save_category_parent_link(CategoryParentLink(category_id=c_b, parent_category_id=parent, sort_index=-1))

        links = repo.list_category_parent_links()
        assert links[0].sort_index == -1
        assert links[1].sort_index == 5


class TestListItemParentLinksOrdering:
    """list_item_parent_links() groups by category_id then sort_index."""

    def test_grouped_by_category_then_sort_index(self, tmp_json_path: Path) -> None:
        """Links spanning two categories are grouped by category, ordered by sort_index within group."""
        repo = JsonRepository(tmp_json_path)
        cat1 = uuid4()
        cat2 = uuid4()
        i_a = uuid4()
        i_b = uuid4()
        i_c = uuid4()
        # Insert in mixed order
        repo.save_item_parent_link(ItemParentLink(item_id=i_c, category_id=cat2, sort_index=3))
        repo.save_item_parent_link(ItemParentLink(item_id=i_b, category_id=cat1, sort_index=10))
        repo.save_item_parent_link(ItemParentLink(item_id=i_a, category_id=cat1, sort_index=1))

        links = repo.list_item_parent_links()
        cat1_links = [lnk for lnk in links if lnk.category_id == cat1]
        cat2_links = [lnk for lnk in links if lnk.category_id == cat2]
        assert [lnk.sort_index for lnk in cat1_links] == [1, 10]
        first_group, second_group = (cat1_links, cat2_links) if str(cat1) < str(cat2) else (cat2_links, cat1_links)
        assert links.index(first_group[-1]) < links.index(second_group[0])

    def test_empty_returns_empty_list(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_item_parent_links() == []

    def test_tie_breaker_by_item_id(self, tmp_json_path: Path) -> None:
        """When sort_index and category_id are equal, order by item_id."""
        repo = JsonRepository(tmp_json_path)
        cat = uuid4()
        i_high = uuid4()
        i_low = uuid4()
        low_str, high_str = sorted([str(i_low), str(i_high)])
        i_first = i_low if str(i_low) == low_str else i_high
        i_second = i_high if str(i_low) == low_str else i_low

        repo.save_item_parent_link(ItemParentLink(item_id=i_second, category_id=cat, sort_index=0))
        repo.save_item_parent_link(ItemParentLink(item_id=i_first, category_id=cat, sort_index=0))

        links = repo.list_item_parent_links()
        assert links[0].item_id == i_first
        assert links[1].item_id == i_second


class TestListItemRelationLinksOrdering:
    """list_item_relation_links() orders by sort_index then source/target IDs."""

    def test_ordered_by_sort_index(self, tmp_json_path: Path) -> None:
        """Relations for an item are returned ascending by sort_index."""
        repo = JsonRepository(tmp_json_path)
        src = uuid4()
        t1, t2, t3 = uuid4(), uuid4(), uuid4()
        # Insert in reverse order
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

    def test_ordering_preserved_with_relation_type_filter(self, tmp_json_path: Path) -> None:
        """sort_index ordering is preserved when relation_type filter is applied."""
        repo = JsonRepository(tmp_json_path)
        src = uuid4()
        t1, t2 = uuid4(), uuid4()
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t1, relation_type="ref", sort_index=5)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=t2, relation_type="ref", sort_index=1)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=uuid4(), relation_type="other", sort_index=0)
        )

        links = repo.list_item_relation_links(src, relation_type="ref")
        assert [lnk.sort_index for lnk in links] == [1, 5]

    def test_ordering_preserved_with_direction_incoming(self, tmp_json_path: Path) -> None:
        """sort_index ordering is preserved for incoming direction."""
        repo = JsonRepository(tmp_json_path)
        tgt = uuid4()
        s1, s2 = uuid4(), uuid4()
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=s1, target_item_id=tgt, relation_type="ref", sort_index=9)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=s2, target_item_id=tgt, relation_type="ref", sort_index=2)
        )

        links = repo.list_item_relation_links(tgt, direction="incoming")
        assert [lnk.sort_index for lnk in links] == [2, 9]

    def test_empty_returns_empty_list(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_item_relation_links(uuid4()) == []

    def test_negative_sort_index_sorts_first(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        src = uuid4()
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=uuid4(), relation_type="ref", sort_index=5)
        )
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=src, target_item_id=uuid4(), relation_type="ref", sort_index=-2)
        )

        links = repo.list_item_relation_links(src)
        assert links[0].sort_index == -2


# ---------------------------------------------------------------------------
# US2 — Category and item listing order
# ---------------------------------------------------------------------------


class TestListCategoriesOrdering:
    """list_categories() returns all categories ordered by name then category_id."""

    def test_ordered_by_name(self, tmp_json_path: Path) -> None:
        """Categories are returned in alphabetical name order."""
        repo = JsonRepository(tmp_json_path)
        repo.save_category(Category(name="Zebra"))
        repo.save_category(Category(name="Alpha"))
        repo.save_category(Category(name="Mango"))

        cats = repo.list_categories()
        assert [c.name for c in cats] == ["Alpha", "Mango", "Zebra"]

    def test_tie_breaker_by_category_id(self, tmp_json_path: Path) -> None:
        """Categories with the same name are further ordered by category_id."""
        repo = JsonRepository(tmp_json_path)
        c1 = Category(name="Same")
        c2 = Category(name="Same")
        repo.save_category(c2)
        repo.save_category(c1)

        cats = repo.list_categories()
        ids = [str(c.category_id) for c in cats]
        assert ids == sorted(ids)

    def test_empty_returns_empty_list(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_categories() == []

    def test_case_sensitive_ordering(self, tmp_json_path: Path) -> None:
        """Ordering follows default Python string comparison (uppercase before lowercase)."""
        repo = JsonRepository(tmp_json_path)
        repo.save_category(Category(name="banana"))
        repo.save_category(Category(name="Apple"))

        cats = repo.list_categories()
        # "Apple" < "banana" in Python str comparison
        assert cats[0].name == "Apple"
        assert cats[1].name == "banana"


class TestListItemsOrdering:
    """list_items() returns all items ordered by name then item_id."""

    def test_ordered_by_name(self, tmp_json_path: Path) -> None:
        """Items are returned in alphabetical name order."""
        repo = JsonRepository(tmp_json_path)
        repo.save_item(Item(name="Zeta"))
        repo.save_item(Item(name="Alpha"))
        repo.save_item(Item(name="Mu"))

        items = repo.list_items()
        assert [i.name for i in items] == ["Alpha", "Mu", "Zeta"]

    def test_tie_breaker_by_item_id(self, tmp_json_path: Path) -> None:
        """Items with the same name are further ordered by item_id."""
        repo = JsonRepository(tmp_json_path)
        i1 = Item(name="Same")
        i2 = Item(name="Same")
        repo.save_item(i2)
        repo.save_item(i1)

        items = repo.list_items()
        ids = [str(i.item_id) for i in items]
        assert ids == sorted(ids)

    def test_empty_returns_empty_list(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_items() == []


# ---------------------------------------------------------------------------
# US3 — External-ID list ordering
# ---------------------------------------------------------------------------


class TestListItemsByExternalIdOrdering:
    """list_items_by_external_id() returns matches ordered by name then item_id."""

    def test_ordered_by_name(self, tmp_json_path: Path) -> None:
        """Multiple items sharing an external_id are returned in name order."""
        repo = JsonRepository(tmp_json_path)
        ext = "shared-ext"
        repo.save_item(Item(name="Zeta", external_id=ext))
        repo.save_item(Item(name="Alpha", external_id=ext))
        repo.save_item(Item(name="Mu", external_id=ext))

        items = repo.list_items_by_external_id(ext)
        assert [i.name for i in items] == ["Alpha", "Mu", "Zeta"]

    def test_single_result_returned(self, tmp_json_path: Path) -> None:
        """Single match is returned correctly (no sorting regression)."""
        repo = JsonRepository(tmp_json_path)
        item = Item(name="Solo", external_id="solo-ext")
        repo.save_item(item)

        result = repo.list_items_by_external_id("solo-ext")
        assert len(result) == 1
        assert result[0].item_id == item.item_id

    def test_no_match_returns_empty(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_items_by_external_id("nonexistent") == []


class TestListCategoriesByExternalIdOrdering:
    """list_categories_by_external_id() returns matches ordered by name then category_id."""

    def test_ordered_by_name(self, tmp_json_path: Path) -> None:
        """Multiple categories sharing an external_id are returned in name order."""
        repo = JsonRepository(tmp_json_path)
        ext = "shared-cat-ext"
        repo.save_category(Category(name="Omega", external_id=ext))
        repo.save_category(Category(name="Beta", external_id=ext))
        repo.save_category(Category(name="Gamma", external_id=ext))

        cats = repo.list_categories_by_external_id(ext)
        assert [c.name for c in cats] == ["Beta", "Gamma", "Omega"]

    def test_single_result_returned(self, tmp_json_path: Path) -> None:
        """Single match is returned correctly."""
        repo = JsonRepository(tmp_json_path)
        cat = Category(name="Solo", external_id="solo-cat-ext")
        repo.save_category(cat)

        result = repo.list_categories_by_external_id("solo-cat-ext")
        assert len(result) == 1
        assert result[0].category_id == cat.category_id

    def test_no_match_returns_empty(self, tmp_json_path: Path) -> None:
        repo = JsonRepository(tmp_json_path)
        assert repo.list_categories_by_external_id("nonexistent") == []
