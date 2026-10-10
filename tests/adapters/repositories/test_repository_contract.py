"""The repository port's contract, asserted once for all four implementations.

Every test runs on the in-memory test double, ``JsonRepository``, ``YamlRepository`` and
``DjangoRepository``, and talks to the port directly, with no service in between. A link is always
saved between stored rows, since Django's foreign keys refuse any other.

What a single implementation adds, such as a file's format or a database's query count, is tested
beside that implementation: ``test_file_repositories.py`` for the two file stores, and
``tests/contrib/django/`` for Django.
"""

import re
from collections.abc import Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest

from taxomesh.domain.models import (
    Category,
    CategoryParentLink,
    Item,
    ItemParentLink,
    ItemRelationLink,
    Tag,
)
from taxomesh.exceptions import TaxomeshExternalIdConflictError
from taxomesh.ports.repository import TaxomeshRepositoryBase
from tests.service.conftest import BACKEND_PARAMS, _build_repository


@pytest.fixture(params=BACKEND_PARAMS)
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshRepositoryBase:
    """A fresh, empty repository of each implementation."""
    repository: TaxomeshRepositoryBase = _build_repository(request, tmp_path)
    return repository


def _uuid(n: int) -> UUID:
    """A fixed identifier whose string form sorts in the numeric order of ``n``."""
    return UUID(int=n)


def _category(n: int, *, name: str = "", enabled: bool = True, external_id: str | None = None) -> Category:
    return Category(category_id=_uuid(n), name=name or f"cat-{n:03d}", enabled=enabled, external_id=external_id)


def _item(n: int, *, name: str = "", enabled: bool = True, external_id: str | None = None) -> Item:
    return Item(item_id=_uuid(n), name=name or f"item-{n:03d}", enabled=enabled, external_id=external_id)


def _store_categories(repo: TaxomeshRepositoryBase, *numbers: int) -> None:
    for n in numbers:
        repo.save_category(_category(n))


def _store_items(repo: TaxomeshRepositoryBase, *numbers: int) -> None:
    for n in numbers:
        repo.save_item(_item(n))


# ---------------------------------------------------------------------------
# Rows: save, find, list, delete
# ---------------------------------------------------------------------------


class TestCategories:
    """``save_category``, ``find_category``, ``list_categories`` and ``delete_category``."""

    def test_a_saved_category_is_found(self, repo: TaxomeshRepositoryBase) -> None:
        stored = repo.save_category(
            Category(category_id=_uuid(1), name="Books", description="All books", slug="books")
        )
        assert repo.find_category(_uuid(1)) == stored
        assert (stored.name, stored.description, stored.slug) == ("Books", "All books", "books")

    def test_find_answers_none_for_an_unknown_category(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.find_category(_uuid(1)) is None

    def test_saving_again_replaces_the_row(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1, name="Original"))
        repo.save_category(_category(1, name="Updated"))
        assert [c.name for c in repo.list_categories()] == ["Updated"]

    def test_list_holds_every_category(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        assert {c.category_id for c in repo.list_categories()} == {_uuid(1), _uuid(2)}

    def test_list_of_an_empty_store_is_empty(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_categories() == []

    def test_delete_answers_true_and_the_row_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1)
        assert repo.delete_category(_uuid(1)) is True
        assert repo.find_category(_uuid(1)) is None

    def test_delete_answers_false_for_an_unknown_category(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.delete_category(_uuid(1)) is False


class TestItems:
    """``save_item``, ``find_item``, ``list_items`` and ``delete_item``."""

    def test_a_saved_item_is_found(self, repo: TaxomeshRepositoryBase) -> None:
        stored = repo.save_item(Item(item_id=_uuid(1), name="Lion", external_id="lion", slug="lion"))
        assert repo.find_item(_uuid(1)) == stored
        assert (stored.name, stored.external_id, stored.slug) == ("Lion", "lion", "lion")

    def test_find_answers_none_for_an_unknown_item(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.find_item(_uuid(1)) is None

    def test_saving_again_replaces_the_row(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(_item(1, name="Original"))
        repo.save_item(_item(1, name="Updated"))
        assert [i.name for i in repo.list_items()] == ["Updated"]

    def test_list_holds_every_item(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2)
        assert {i.item_id for i in repo.list_items()} == {_uuid(1), _uuid(2)}

    def test_list_of_an_empty_store_is_empty(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_items() == []

    def test_delete_answers_true_and_the_row_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1)
        assert repo.delete_item(_uuid(1)) is True
        assert repo.find_item(_uuid(1)) is None

    def test_delete_answers_false_for_an_unknown_item(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.delete_item(_uuid(1)) is False


class TestTags:
    """``save_tag``, ``find_tag``, ``list_tags``, ``map_tags_by_id`` and ``delete_tag``."""

    def test_a_saved_tag_is_found(self, repo: TaxomeshRepositoryBase) -> None:
        tag = Tag(tag_id=_uuid(1), name="fiction")
        repo.save_tag(tag)
        assert repo.find_tag(_uuid(1)) == tag

    def test_find_answers_none_for_an_unknown_tag(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.find_tag(_uuid(1)) is None

    def test_list_holds_every_tag(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_tag(Tag(tag_id=_uuid(1), name="a"))
        repo.save_tag(Tag(tag_id=_uuid(2), name="b"))
        assert {t.tag_id for t in repo.list_tags()} == {_uuid(1), _uuid(2)}

    def test_list_of_an_empty_store_is_empty(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_tags() == []

    def test_delete_answers_true_and_the_row_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_tag(Tag(tag_id=_uuid(1), name="bye"))
        assert repo.delete_tag(_uuid(1)) is True
        assert repo.find_tag(_uuid(1)) is None

    def test_delete_answers_false_for_an_unknown_tag(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.delete_tag(_uuid(1)) is False

    def test_map_by_id_holds_the_found_subset(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_tag(Tag(tag_id=_uuid(1), name="a"))
        repo.save_tag(Tag(tag_id=_uuid(2), name="b"))
        found = repo.map_tags_by_id([_uuid(1), _uuid(99)])
        assert {key: tag.name for key, tag in found.items()} == {_uuid(1): "a"}
        assert not repo.map_tags_by_id([])


class TestListingOrder:
    """``list_categories`` and ``list_items`` order by name, then by identifier."""

    def test_categories_by_name(self, repo: TaxomeshRepositoryBase) -> None:
        for n, name in enumerate(("Zebra", "Alpha", "Mango"), start=1):
            repo.save_category(_category(n, name=name))
        assert [c.name for c in repo.list_categories()] == ["Alpha", "Mango", "Zebra"]

    def test_categories_with_one_name_by_identifier(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(2, name="Same"))
        repo.save_category(_category(1, name="Same"))
        assert [c.category_id for c in repo.list_categories()] == [_uuid(1), _uuid(2)]

    def test_capitals_sort_before_lower_case(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1, name="banana"))
        repo.save_category(_category(2, name="Apple"))
        assert [c.name for c in repo.list_categories()] == ["Apple", "banana"]

    def test_items_by_name(self, repo: TaxomeshRepositoryBase) -> None:
        for n, name in enumerate(("Zeta", "Alpha", "Mu"), start=1):
            repo.save_item(_item(n, name=name))
        assert [i.name for i in repo.list_items()] == ["Alpha", "Mu", "Zeta"]

    def test_items_with_one_name_by_identifier(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(_item(2, name="Same"))
        repo.save_item(_item(1, name="Same"))
        assert [i.item_id for i in repo.list_items()] == [_uuid(1), _uuid(2)]


class TestEnabledFilter:
    """``list_categories`` and ``list_items`` filter by ``enabled``, which defaults to ``True``."""

    @pytest.fixture
    def stored(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        repo.save_category(_category(1, enabled=True))
        repo.save_category(_category(2, enabled=False))
        repo.save_item(_item(1, enabled=True))
        repo.save_item(_item(2, enabled=False))
        return repo

    @pytest.mark.parametrize(
        ("enabled", "expected"),
        [(True, {1}), (False, {2}), (None, {1, 2})],
        ids=["true", "false", "none"],
    )
    def test_categories(self, stored: TaxomeshRepositoryBase, enabled: bool | None, expected: set[int]) -> None:
        assert {c.category_id for c in stored.list_categories(enabled=enabled)} == {_uuid(n) for n in expected}

    @pytest.mark.parametrize(
        ("enabled", "expected"),
        [(True, {1}), (False, {2}), (None, {1, 2})],
        ids=["true", "false", "none"],
    )
    def test_items(self, stored: TaxomeshRepositoryBase, enabled: bool | None, expected: set[int]) -> None:
        assert {i.item_id for i in stored.list_items(enabled=enabled)} == {_uuid(n) for n in expected}

    def test_the_default_keeps_the_enabled_rows(self, stored: TaxomeshRepositoryBase) -> None:
        assert [c.category_id for c in stored.list_categories()] == [_uuid(1)]
        assert [i.item_id for i in stored.list_items()] == [_uuid(1)]


# ---------------------------------------------------------------------------
# Lookups by slug and by external id
# ---------------------------------------------------------------------------


class TestSlugLookups:
    """``find_category_by_slug`` and ``find_item_by_slug``."""

    def test_a_category_is_found_by_its_slug(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(Category(category_id=_uuid(1), name="Books", slug="books"))
        found = repo.find_category_by_slug("books")
        assert found is not None
        assert found.category_id == _uuid(1)

    def test_an_item_is_found_by_its_slug(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(Item(item_id=_uuid(1), name="Item", slug="my-item"))
        found = repo.find_item_by_slug("my-item")
        assert found is not None
        assert found.item_id == _uuid(1)

    def test_an_unknown_slug_finds_nothing(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.find_category_by_slug("nonexistent") is None
        assert repo.find_item_by_slug("nonexistent") is None


class TestExternalIds:
    """``find_*_by_external_id``, and an external id held by one row only."""

    def test_a_category_is_found_by_its_external_id(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1, external_id="solo"))
        found = repo.find_category_by_external_id("solo")
        assert found is not None
        assert found.category_id == _uuid(1)

    def test_an_item_is_found_by_its_external_id(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(_item(1, external_id="solo"))
        found = repo.find_item_by_external_id("solo")
        assert found is not None
        assert found.item_id == _uuid(1)

    def test_an_unknown_external_id_finds_nothing(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.find_category_by_external_id("nonexistent") is None
        assert repo.find_item_by_external_id("nonexistent") is None

    def test_a_missing_external_id_is_stored_as_none(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1))
        repo.save_item(_item(1))
        stored_category = repo.find_category(_uuid(1))
        stored_item = repo.find_item(_uuid(1))
        assert stored_category is not None
        assert stored_item is not None
        assert (stored_category.external_id, stored_item.external_id) == (None, None)

    def test_a_second_category_with_the_external_id_is_refused(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1, external_id="taken"))
        message = "External id 'taken' is already used by another category"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            repo.save_category(_category(2, external_id="taken"))

    def test_a_second_item_with_the_external_id_is_refused(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(_item(1, external_id="taken"))
        message = "External id 'taken' is already used by another item"
        with pytest.raises(TaxomeshExternalIdConflictError, match=re.escape(message)):
            repo.save_item(_item(2, external_id="taken"))

    def test_saving_the_holder_again_keeps_its_external_id(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_category(_category(1, name="Original", external_id="kept"))
        repo.save_item(_item(1, name="Original", external_id="kept"))
        repo.save_category(_category(1, name="Updated", external_id="kept"))
        repo.save_item(_item(1, name="Updated", external_id="kept"))
        stored_category = repo.find_category(_uuid(1))
        stored_item = repo.find_item(_uuid(1))
        assert stored_category is not None
        assert stored_item is not None
        assert (stored_category.name, stored_item.name) == ("Updated", "Updated")

    def test_rows_without_an_external_id_never_conflict(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        _store_items(repo, 1, 2)
        assert len(repo.list_categories()) == 2
        assert len(repo.list_items()) == 2


class TestBulkExternalIdLookups:
    """``map_categories_by_external_id`` and ``map_items_by_external_id``, keyed by external id."""

    @pytest.fixture
    def stored(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        repo.save_category(_category(1, external_id="a"))
        repo.save_category(_category(2, external_id="b", enabled=False))
        repo.save_item(_item(1, external_id="a"))
        repo.save_item(_item(2, external_id="b", enabled=False))
        return repo

    def test_every_found_row_is_keyed_by_its_external_id(self, stored: TaxomeshRepositoryBase) -> None:
        categories = stored.map_categories_by_external_id(["a", "b"])
        items = stored.map_items_by_external_id(["a", "b"])
        assert {key: c.category_id for key, c in categories.items()} == {"a": _uuid(1), "b": _uuid(2)}
        assert {key: i.item_id for key, i in items.items()} == {"a": _uuid(1), "b": _uuid(2)}

    def test_an_unknown_external_id_is_absent(self, stored: TaxomeshRepositoryBase) -> None:
        assert set(stored.map_categories_by_external_id(["a", "missing"])) == {"a"}
        assert set(stored.map_items_by_external_id(["a", "missing"])) == {"a"}
        assert stored.map_items_by_external_id(["missing", "also-missing"]) == {}

    def test_a_repeated_external_id_gives_one_key(self, stored: TaxomeshRepositoryBase) -> None:
        assert set(stored.map_categories_by_external_id(["a", "a"])) == {"a"}
        assert set(stored.map_items_by_external_id(["a", "a"])) == {"a"}

    def test_values_are_matched_exactly_so_blanks_find_nothing(self, stored: TaxomeshRepositoryBase) -> None:
        assert set(stored.map_categories_by_external_id(["a", "", "   "])) == {"a"}
        assert set(stored.map_items_by_external_id(["a", "", "   "])) == {"a"}

    def test_no_external_id_gives_an_empty_map(self, stored: TaxomeshRepositoryBase) -> None:
        assert stored.map_categories_by_external_id([]) == {}
        assert stored.map_items_by_external_id([]) == {}

    @pytest.mark.parametrize(
        ("enabled", "expected"),
        [(True, {"a"}), (False, {"b"}), (None, {"a", "b"})],
        ids=["true", "false", "none"],
    )
    def test_the_enabled_filter(
        self, stored: TaxomeshRepositoryBase, enabled: bool | None, expected: set[str]
    ) -> None:
        assert set(stored.map_categories_by_external_id(["a", "b"], enabled=enabled)) == expected
        assert set(stored.map_items_by_external_id(["a", "b"], enabled=enabled)) == expected


class TestMapItemsById:
    """``map_items_by_id``: the found subset, keyed by identifier."""

    def test_the_found_subset(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2, 3)
        result = repo.map_items_by_id([_uuid(1), _uuid(3), _uuid(99)])
        assert {key: item.name for key, item in result.items()} == {_uuid(1): "item-001", _uuid(3): "item-003"}

    def test_nothing_found_gives_an_empty_map(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1)
        assert repo.map_items_by_id([_uuid(98), _uuid(99)]) == {}
        assert repo.map_items_by_id([]) == {}

    def test_each_value_is_the_stored_row(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 7)
        assert repo.map_items_by_id([_uuid(7)])[_uuid(7)] == repo.find_item(_uuid(7))

    @pytest.mark.parametrize(
        ("enabled", "expected"),
        [(True, {1}), (False, {2}), (None, {1, 2})],
        ids=["true", "false", "none"],
    )
    def test_the_enabled_filter(self, repo: TaxomeshRepositoryBase, enabled: bool | None, expected: set[int]) -> None:
        repo.save_item(_item(1, enabled=True))
        repo.save_item(_item(2, enabled=False))
        assert set(repo.map_items_by_id([_uuid(1), _uuid(2)], enabled=enabled)) == {_uuid(n) for n in expected}

    def test_the_filter_defaults_to_every_row(self, repo: TaxomeshRepositoryBase) -> None:
        repo.save_item(_item(1, enabled=True))
        repo.save_item(_item(2, enabled=False))
        assert set(repo.map_items_by_id([_uuid(1), _uuid(2)])) == {_uuid(1), _uuid(2)}


class TestMapCategoriesById:
    """``map_categories_by_id``: the found subset, keyed by identifier, every row by default."""

    def test_the_found_subset(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        repo.save_category(_category(3, enabled=False))
        found = repo.map_categories_by_id([_uuid(1), _uuid(3), _uuid(99)])
        assert {key: category.name for key, category in found.items()} == {_uuid(1): "cat-001", _uuid(3): "cat-003"}
        assert not repo.map_categories_by_id([])


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


class TestItemTagLinks:
    """``add_item_tag_link`` and ``delete_item_tag_link``."""

    @pytest.fixture
    def stored(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        _store_items(repo, 1)
        repo.save_tag(Tag(tag_id=_uuid(2), name="tag"))
        return repo

    def test_a_link_joins_the_item_and_the_tag(self, stored: TaxomeshRepositoryBase) -> None:
        stored.add_item_tag_link(_uuid(1), _uuid(2))
        assert [(lnk.item_id, lnk.tag_id) for lnk in stored.list_item_tag_links()] == [(_uuid(1), _uuid(2))]

    def test_adding_a_link_twice_stores_it_once(self, stored: TaxomeshRepositoryBase) -> None:
        stored.add_item_tag_link(_uuid(1), _uuid(2))
        stored.add_item_tag_link(_uuid(1), _uuid(2))
        assert len(stored.list_item_tag_links()) == 1

    def test_delete_answers_true_and_the_link_is_gone(self, stored: TaxomeshRepositoryBase) -> None:
        stored.add_item_tag_link(_uuid(1), _uuid(2))
        assert stored.delete_item_tag_link(_uuid(1), _uuid(2)) is True
        assert stored.list_item_tag_links() == []

    def test_delete_answers_false_for_an_unknown_link(self, stored: TaxomeshRepositoryBase) -> None:
        assert stored.delete_item_tag_link(_uuid(1), _uuid(2)) is False


class TestCategoryParentLinks:
    """``save_category_parent_link``, ``delete_category_parent_link`` and ``list_category_parent_links``.

    The listing filters by either end of the link, or both.
    """

    def test_a_saved_link_is_listed(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        repo.save_category_parent_link(
            CategoryParentLink(category_id=_uuid(1), parent_category_id=_uuid(2), sort_index=1)
        )
        links = repo.list_category_parent_links()
        assert [(lnk.category_id, lnk.parent_category_id, lnk.sort_index) for lnk in links] == [
            (_uuid(1), _uuid(2), 1)
        ]

    def test_saving_the_pair_again_replaces_its_sort_index(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        for sort_index in (0, 42):
            repo.save_category_parent_link(
                CategoryParentLink(category_id=_uuid(1), parent_category_id=_uuid(2), sort_index=sort_index)
            )
        assert [lnk.sort_index for lnk in repo.list_category_parent_links()] == [42]

    def test_an_empty_store_lists_none(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_category_parent_links() == []

    def test_delete_answers_true_once_and_the_link_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2, 3)
        for parent in (2, 3):
            repo.save_category_parent_link(CategoryParentLink(category_id=_uuid(1), parent_category_id=_uuid(parent)))
        assert repo.delete_category_parent_link(_uuid(1), _uuid(2)) is True
        assert repo.delete_category_parent_link(_uuid(1), _uuid(2)) is False
        assert [lnk.parent_category_id for lnk in repo.list_category_parent_links()] == [_uuid(3)]

    def test_links_group_by_parent_then_sort_index(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2, 11, 12, 13)
        for child, parent, sort_index in ((13, 2, 5), (12, 1, 2), (11, 1, 0)):
            repo.save_category_parent_link(
                CategoryParentLink(category_id=_uuid(child), parent_category_id=_uuid(parent), sort_index=sort_index)
            )
        links = repo.list_category_parent_links()
        assert [(lnk.category_id, lnk.parent_category_id) for lnk in links] == [
            (_uuid(11), _uuid(1)),
            (_uuid(12), _uuid(1)),
            (_uuid(13), _uuid(2)),
        ]

    def test_a_sort_index_tie_orders_by_category(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 11, 12)
        for child in (12, 11):
            repo.save_category_parent_link(
                CategoryParentLink(category_id=_uuid(child), parent_category_id=_uuid(1), sort_index=1)
            )
        assert [lnk.category_id for lnk in repo.list_category_parent_links()] == [_uuid(11), _uuid(12)]

    def test_a_negative_sort_index_comes_first(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 11, 12)
        repo.save_category_parent_link(
            CategoryParentLink(category_id=_uuid(11), parent_category_id=_uuid(1), sort_index=5)
        )
        repo.save_category_parent_link(
            CategoryParentLink(category_id=_uuid(12), parent_category_id=_uuid(1), sort_index=-1)
        )
        assert [lnk.sort_index for lnk in repo.list_category_parent_links()] == [-1, 5]

    @pytest.fixture
    def parented(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        """Three parents and four links: 11 under 1 and 2, 12 under 1, 13 under 3."""
        _store_categories(repo, 1, 2, 3, 11, 12, 13)
        for child, parent in ((11, 1), (11, 2), (12, 1), (13, 3)):
            repo.save_category_parent_link(
                CategoryParentLink(category_id=_uuid(child), parent_category_id=_uuid(parent))
            )
        return repo

    @staticmethod
    def _pairs(links: Sequence[CategoryParentLink]) -> list[tuple[UUID, UUID]]:
        return [(lnk.category_id, lnk.parent_category_id) for lnk in links]

    def test_the_category_filter(self, parented: TaxomeshRepositoryBase) -> None:
        assert self._pairs(parented.list_category_parent_links(category_ids=[_uuid(11), _uuid(13)])) == [
            (_uuid(11), _uuid(1)),
            (_uuid(11), _uuid(2)),
            (_uuid(13), _uuid(3)),
        ]

    def test_the_parent_filter(self, parented: TaxomeshRepositoryBase) -> None:
        assert self._pairs(parented.list_category_parent_links(parent_category_ids=[_uuid(1)])) == [
            (_uuid(11), _uuid(1)),
            (_uuid(12), _uuid(1)),
        ]
        assert parented.list_category_parent_links(parent_category_ids=[_uuid(99)]) == []

    def test_an_empty_filter_matches_nothing(self, parented: TaxomeshRepositoryBase) -> None:
        assert parented.list_category_parent_links(category_ids=[]) == []
        assert parented.list_category_parent_links(parent_category_ids=set()) == []

    def test_both_filters_hold_together(self, parented: TaxomeshRepositoryBase) -> None:
        assert self._pairs(
            parented.list_category_parent_links(category_ids=[_uuid(11)], parent_category_ids=[_uuid(2), _uuid(3)])
        ) == [(_uuid(11), _uuid(2))]


class TestItemParentLinks:
    """``save_item_parent_link``, ``delete_item_parent_link`` and ``list_item_parent_links``, with both filters."""

    def test_a_saved_link_is_listed(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1)
        _store_items(repo, 11)
        repo.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(1), sort_index=0))
        links = repo.list_item_parent_links()
        assert [(lnk.item_id, lnk.category_id) for lnk in links] == [(_uuid(11), _uuid(1))]

    def test_saving_the_pair_again_replaces_its_sort_index(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1)
        _store_items(repo, 11)
        for sort_index in (1, 99):
            repo.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(1), sort_index=sort_index))
        assert [lnk.sort_index for lnk in repo.list_item_parent_links()] == [99]

    def test_an_empty_store_lists_none(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_item_parent_links() == []

    def test_delete_answers_true_once_and_the_link_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        _store_categories(repo, 1, 2)
        _store_items(repo, 11)
        for category in (1, 2):
            repo.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(category)))
        assert repo.delete_item_parent_link(_uuid(11), _uuid(1)) is True
        assert repo.delete_item_parent_link(_uuid(11), _uuid(1)) is False
        assert [lnk.category_id for lnk in repo.list_item_parent_links()] == [_uuid(2)]

    @pytest.fixture
    def placed(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        """Two categories, four items and five links, one pair tied on its sort index.

        Saved out of order; listed by category, then sort index, then item:
        (11, 1, 0), (12, 1, 0), (13, 1, 1), (11, 2, 0), (14, 2, 5).
        """
        _store_categories(repo, 1, 2)
        _store_items(repo, 11, 12, 13, 14)
        for item, category, sort_index in ((14, 2, 5), (12, 1, 0), (13, 1, 1), (11, 2, 0), (11, 1, 0)):
            repo.save_item_parent_link(
                ItemParentLink(item_id=_uuid(item), category_id=_uuid(category), sort_index=sort_index)
            )
        return repo

    @staticmethod
    def _triples(links: Sequence[ItemParentLink]) -> list[tuple[UUID, UUID, int]]:
        return [(lnk.item_id, lnk.category_id, lnk.sort_index) for lnk in links]

    def test_every_link_by_category_then_sort_index_then_item(self, placed: TaxomeshRepositoryBase) -> None:
        assert self._triples(placed.list_item_parent_links()) == [
            (_uuid(11), _uuid(1), 0),
            (_uuid(12), _uuid(1), 0),
            (_uuid(13), _uuid(1), 1),
            (_uuid(11), _uuid(2), 0),
            (_uuid(14), _uuid(2), 5),
        ]

    def test_the_item_filter(self, placed: TaxomeshRepositoryBase) -> None:
        assert self._triples(placed.list_item_parent_links(item_ids=[_uuid(11), _uuid(14)])) == [
            (_uuid(11), _uuid(1), 0),
            (_uuid(11), _uuid(2), 0),
            (_uuid(14), _uuid(2), 5),
        ]
        assert placed.list_item_parent_links(item_ids=[_uuid(99)]) == []

    def test_the_category_filter_keeps_the_order(self, placed: TaxomeshRepositoryBase) -> None:
        assert self._triples(placed.list_item_parent_links(category_ids=[_uuid(2)])) == [
            (_uuid(11), _uuid(2), 0),
            (_uuid(14), _uuid(2), 5),
        ]
        assert placed.list_item_parent_links(category_ids={_uuid(1), _uuid(2)}) == placed.list_item_parent_links()

    def test_an_empty_filter_matches_nothing(self, placed: TaxomeshRepositoryBase) -> None:
        assert placed.list_item_parent_links(category_ids=[]) == []
        assert placed.list_item_parent_links(category_ids=set()) == []
        assert placed.list_item_parent_links(item_ids=[]) == []

    def test_both_filters_hold_together(self, placed: TaxomeshRepositoryBase) -> None:
        assert self._triples(placed.list_item_parent_links(item_ids=[_uuid(11)], category_ids=[_uuid(2)])) == [
            (_uuid(11), _uuid(2), 0)
        ]
        assert placed.list_item_parent_links(item_ids=[_uuid(14)], category_ids=[_uuid(1)]) == []


class TestItemRelationLinks:
    """``save_item_relation_link``, ``delete_item_relation_link`` and ``list_item_relation_links``."""

    def test_every_field_is_stored(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2)
        link = ItemRelationLink(
            source_item_id=_uuid(1), target_item_id=_uuid(2), relation_type="covers", sort_index=7, metadata={"k": "v"}
        )
        repo.save_item_relation_link(link)
        assert list(repo.list_item_relation_links(_uuid(1))) == [link]

    def test_saving_the_triple_again_replaces_its_sort_index_and_metadata(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2)
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=_uuid(1), target_item_id=_uuid(2), relation_type="covers", sort_index=1)
        )
        repo.save_item_relation_link(
            ItemRelationLink(
                source_item_id=_uuid(1),
                target_item_id=_uuid(2),
                relation_type="covers",
                sort_index=9,
                metadata={"updated": True},
            )
        )
        links = repo.list_item_relation_links(_uuid(1))
        assert [(lnk.sort_index, lnk.metadata) for lnk in links] == [(9, {"updated": True})]

    def test_delete_answers_true_and_the_link_is_gone(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2)
        repo.save_item_relation_link(
            ItemRelationLink(source_item_id=_uuid(1), target_item_id=_uuid(2), relation_type="covers")
        )
        assert repo.delete_item_relation_link(_uuid(1), _uuid(2), "covers") is True
        assert repo.list_item_relation_links(_uuid(1)) == []

    def test_delete_answers_false_for_an_unknown_link(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2)
        assert repo.delete_item_relation_link(_uuid(1), _uuid(2), "covers") is False

    def test_an_item_without_links_lists_none(self, repo: TaxomeshRepositoryBase) -> None:
        assert repo.list_item_relation_links(_uuid(1)) == []

    def test_a_negative_sort_index_comes_first(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2, 3)
        for target, sort_index in ((2, 5), (3, -2)):
            repo.save_item_relation_link(
                ItemRelationLink(
                    source_item_id=_uuid(1), target_item_id=_uuid(target), relation_type="ref", sort_index=sort_index
                )
            )
        assert [lnk.sort_index for lnk in repo.list_item_relation_links(_uuid(1))] == [-2, 5]

    def test_the_relation_type_filter_keeps_the_order(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2, 3, 4)
        for target, relation_type, sort_index in ((2, "ref", 5), (3, "ref", 1), (4, "other", 0)):
            repo.save_item_relation_link(
                ItemRelationLink(
                    source_item_id=_uuid(1),
                    target_item_id=_uuid(target),
                    relation_type=relation_type,
                    sort_index=sort_index,
                )
            )
        links = repo.list_item_relation_links(_uuid(1), relation_types=["ref"])
        assert [lnk.sort_index for lnk in links] == [1, 5]


# The relation-link reads, over one dataset. ``relation_type`` and ``sort_index`` disagree on
# purpose: "alpha" sorts before "beta" while carrying the higher sort index, which separates the
# batch orderings (relation type first) from the single-item one (sort index first).
_ITEM_A = UUID("aaaaaaaa-0000-4000-8000-000000000001")
_ITEM_B = UUID("bbbbbbbb-0000-4000-8000-000000000002")
_ITEM_C = UUID("cccccccc-0000-4000-8000-000000000003")
_ITEM_D = UUID("dddddddd-0000-4000-8000-000000000004")
_LINK_A_C = ItemRelationLink(source_item_id=_ITEM_A, target_item_id=_ITEM_C, relation_type="beta", sort_index=1)
_LINK_A_D = ItemRelationLink(source_item_id=_ITEM_A, target_item_id=_ITEM_D, relation_type="alpha", sort_index=2)
_LINK_B_C = ItemRelationLink(source_item_id=_ITEM_B, target_item_id=_ITEM_C, relation_type="alpha", sort_index=0)


def _key(link: ItemRelationLink) -> tuple[UUID, UUID, str]:
    return (link.source_item_id, link.target_item_id, link.relation_type)


def _keys(links: Sequence[ItemRelationLink]) -> list[tuple[UUID, UUID, str]]:
    return [_key(link) for link in links]


class TestRelationReadOrders:
    """The two relation reads order differently, so neither can stand in for the other.

    ============================== ============ =================================================
    member                         direction    ordering
    ============================== ============ =================================================
    ``list_item_relation_links``   any          ``(sort_index, source, target)``
    ``..._batch``                  outgoing     ``(source, relation_type, sort_index, target)``
    ``..._batch``                  incoming     ``(target, relation_type, sort_index, source)``
    ``..._batch``                  both         ``(sort_index, source, target)``
    ============================== ============ =================================================

    The batch orders group by the queried end first, which a read of one item has no use for. Only
    ``both`` coincides with the single-item read.
    """

    @pytest.fixture
    def related(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        for index, item_id in enumerate((_ITEM_A, _ITEM_B, _ITEM_C, _ITEM_D)):
            repo.save_item(Item(item_id=item_id, name=f"Item {index}"))
        for link in (_LINK_A_C, _LINK_A_D, _LINK_B_C):
            repo.save_item_relation_link(link)
        return repo

    def test_one_item_one_link_set_two_orders(self, related: TaxomeshRepositoryBase) -> None:
        single = related.list_item_relation_links(_ITEM_A, direction="outgoing")
        batch = related.list_item_relation_links_batch([_ITEM_A], direction="outgoing")
        assert set(_keys(single)) == set(_keys(batch))
        assert _keys(single) == [_key(_LINK_A_C), _key(_LINK_A_D)]
        assert _keys(batch) == [_key(_LINK_A_D), _key(_LINK_A_C)]

    @pytest.mark.parametrize(
        ("item", "direction", "expected"),
        [
            (_ITEM_A, "outgoing", [_LINK_A_C, _LINK_A_D]),
            (_ITEM_C, "incoming", [_LINK_B_C, _LINK_A_C]),
            (_ITEM_C, "both", [_LINK_B_C, _LINK_A_C]),
        ],
        ids=["outgoing", "incoming", "both"],
    )
    def test_the_single_item_read_orders_by_sort_index(
        self,
        related: TaxomeshRepositoryBase,
        item: UUID,
        direction: Literal["outgoing", "incoming", "both"],
        expected: list[ItemRelationLink],
    ) -> None:
        assert _keys(related.list_item_relation_links(item, direction=direction)) == _keys(expected)

    def test_the_outgoing_batch_orders_by_source_then_relation_type(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_ITEM_A, _ITEM_B], direction="outgoing")
        assert _keys(links) == _keys([_LINK_A_D, _LINK_A_C, _LINK_B_C])

    def test_the_incoming_batch_orders_by_target_then_relation_type(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_ITEM_C, _ITEM_D], direction="incoming")
        assert _keys(links) == _keys([_LINK_B_C, _LINK_A_C, _LINK_A_D])

    def test_the_both_batch_orders_as_the_single_item_read(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_ITEM_A, _ITEM_B, _ITEM_C, _ITEM_D], direction="both")
        assert _keys(links) == _keys([_LINK_B_C, _LINK_A_C, _LINK_A_D])

    def test_a_link_with_both_ends_queried_appears_once(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_ITEM_A, _ITEM_C], direction="both")
        assert len(links) == len(set(_keys(links)))

    def test_the_single_item_read_under_both_joins_each_direction(self, related: TaxomeshRepositoryBase) -> None:
        both = related.list_item_relation_links(_ITEM_C, direction="both")
        assert set(_keys(both)) == set(_keys(related.list_item_relation_links(_ITEM_C, direction="incoming")))
        both_a = related.list_item_relation_links(_ITEM_A, direction="both")
        assert set(_keys(both_a)) == {_key(_LINK_A_C), _key(_LINK_A_D)}


class TestRelationBatchRead:
    """``list_item_relation_links_batch``: the links of many items in one read."""

    @pytest.fixture
    def related(self, repo: TaxomeshRepositoryBase) -> TaxomeshRepositoryBase:
        """Items 1 and 2 relate out to 11 and 12; 21 and 22 relate in to 1."""
        _store_items(repo, 1, 2, 3, 11, 12, 21, 22)
        for source, target, relation_type in ((1, 11, "music_by"), (1, 12, "lyrics_by"), (2, 11, "music_by")):
            repo.save_item_relation_link(
                ItemRelationLink(
                    source_item_id=_uuid(source), target_item_id=_uuid(target), relation_type=relation_type
                )
            )
        for source, relation_type in ((21, "music_by"), (22, "lyrics_by")):
            repo.save_item_relation_link(
                ItemRelationLink(source_item_id=_uuid(source), target_item_id=_uuid(1), relation_type=relation_type)
            )
        return repo

    def test_the_outgoing_links_of_every_item_given(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_uuid(1), _uuid(2), _uuid(3)])
        assert {lnk.source_item_id for lnk in links} == {_uuid(1), _uuid(2)}
        assert len(links) == 3

    def test_the_incoming_links_of_every_item_given(self, related: TaxomeshRepositoryBase) -> None:
        links = related.list_item_relation_links_batch([_uuid(1), _uuid(11)], direction="incoming")
        assert {(lnk.source_item_id, lnk.target_item_id) for lnk in links} == {
            (_uuid(21), _uuid(1)),
            (_uuid(22), _uuid(1)),
            (_uuid(1), _uuid(11)),
            (_uuid(2), _uuid(11)),
        }

    @pytest.mark.parametrize("direction", ["outgoing", "incoming", "both"])
    def test_no_item_gives_no_link(
        self, related: TaxomeshRepositoryBase, direction: Literal["outgoing", "incoming", "both"]
    ) -> None:
        assert related.list_item_relation_links_batch([], direction=direction) == []

    @pytest.mark.parametrize("direction", ["outgoing", "incoming"])
    def test_the_relation_type_filter(
        self, related: TaxomeshRepositoryBase, direction: Literal["outgoing", "incoming"]
    ) -> None:
        links = related.list_item_relation_links_batch([_uuid(1)], direction=direction, relation_types=["music_by"])
        assert [lnk.relation_type for lnk in links] == ["music_by"]

    @pytest.mark.parametrize("relation_types", [None, []], ids=["none", "empty"])
    def test_no_relation_type_filter_keeps_every_type(
        self, related: TaxomeshRepositoryBase, relation_types: list[str] | None
    ) -> None:
        links = related.list_item_relation_links_batch([_uuid(1)], relation_types=relation_types)
        assert {lnk.relation_type for lnk in links} == {"music_by", "lyrics_by"}

    def test_a_sort_index_tie_orders_by_the_other_end(self, repo: TaxomeshRepositoryBase) -> None:
        _store_items(repo, 1, 2, 11, 12)
        for source, target in ((1, 12), (1, 11), (2, 11)):
            repo.save_item_relation_link(
                ItemRelationLink(source_item_id=_uuid(source), target_item_id=_uuid(target), relation_type="covers")
            )
        outgoing = repo.list_item_relation_links_batch([_uuid(1)])
        incoming = repo.list_item_relation_links_batch([_uuid(11)], direction="incoming")
        assert [lnk.target_item_id for lnk in outgoing] == [_uuid(11), _uuid(12)]
        assert [lnk.source_item_id for lnk in incoming] == [_uuid(1), _uuid(2)]


# ---------------------------------------------------------------------------
# The atomic boundary
# ---------------------------------------------------------------------------


class TestAtomic:
    """``atomic()`` is a context manager yielding ``None``, and a write inside it persists.

    Whether a failure inside it rolls back differs by backend: ``test_atomic_operations.py``
    asserts each.
    """

    def test_it_is_a_context_manager(self, repo: TaxomeshRepositoryBase) -> None:
        assert isinstance(repo.atomic(), AbstractContextManager)

    def test_the_block_yields_none(self, repo: TaxomeshRepositoryBase) -> None:
        with repo.atomic() as value:
            assert value is None

    def test_a_write_inside_it_persists(self, repo: TaxomeshRepositoryBase) -> None:
        with repo.atomic():
            stored = repo.save_category(_category(1))
        assert repo.find_category(_uuid(1)) == stored
