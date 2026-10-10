"""The implicit root is not a row in the container, and not a location either.

One rule, applied without exception: **the root's identifier answers not-found wherever a member
takes a category**, whether it hands a category back, filters by one, or places or moves something
under one. The root is a storage mechanism, not a domain entity — the link target that makes
``roots()`` computable — and the top level is reached through ``roots()`` and ``None`` in ``move``
and ``reorder`` alone.

The root remains a genuine stored ``Category`` throughout. This is a visibility rule at the service
boundary, not a data change — asserted directly in the last class, because a change that quietly
deleted the row would otherwise satisfy every assertion above it.
"""

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.constants import ROOT_CATEGORY_NAME
from taxomesh.domain.models import ItemParentLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError


def _give_the_root_an_external_id(service: TaxomeshService, external_id: str) -> None:
    """Stamp an external id onto the stored root row, so the lookups have something to refuse.

    Written through the repository rather than through ``categories.update``, which answers
    not-found for the root as every other member of the container does. Below the service
    boundary is the only place the row can be given a value the lookups would otherwise match.
    """
    root = service.repository.find_category(service._root_id)
    assert root is not None
    service.repository.save_category(root.model_copy(update={"external_id": external_id}))
    service._cache.clear()


def _stored_links(service: TaxomeshService) -> tuple[set[tuple[UUID, UUID, int]], set[tuple[UUID, UUID, int]]]:
    """Every stored parent link and placement, as ``(child, parent, sort_index)``."""
    repository = service.repository
    return (
        {(lnk.category_id, lnk.parent_category_id, lnk.sort_index) for lnk in repository.list_category_parent_links()},
        {(lnk.item_id, lnk.category_id, lnk.sort_index) for lnk in repository.list_item_parent_links()},
    )


class TestTheRootIsNotARow:
    """Every member that hands a category back to a caller treats the root as absent."""

    def test_subscript_raises(self, service: TaxomeshService) -> None:
        """The root is not an exception to the law — it is simply not in the container."""
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories[service._root_id]

    def test_get_returns_none(self, service: TaxomeshService) -> None:
        assert service.categories.get(service._root_id) is None

    def test_get_returns_the_supplied_default(self, service: TaxomeshService) -> None:
        sentinel = object()

        assert service.categories.get(service._root_id, sentinel) is sentinel

    def test_membership_is_false(self, service: TaxomeshService) -> None:
        """``in`` answers the question subscript answers, so it must agree with it."""
        assert service._root_id not in service.categories

    def test_len_counts_only_the_categories_the_caller_created(self, service: TaxomeshService) -> None:
        """The count agrees with membership: what ``in`` denies, ``len`` does not count."""
        service.categories.create("Alpha")
        service.categories.create("Beta")

        assert len(service.categories) == 2

    def test_get_many_omits_it(self, service: TaxomeshService) -> None:
        """An absent key is simply not in the result — the root is an absent key."""
        created = service.categories.create("Alpha")

        found = service.categories.get_many([created.category_id, service._root_id])

        assert created.category_id in found
        assert service._root_id not in found

    def test_get_by_slug_returns_none(self, service: TaxomeshService) -> None:
        """The root is created with an empty slug, so the empty slug must answer ``None``."""
        assert service.categories.get_by_slug("") is None

    def test_get_by_external_id_returns_none(self, service: TaxomeshService) -> None:
        _give_the_root_an_external_id(service, "ext-root")

        assert service.categories.get_by_external_id("ext-root") is None

    def test_get_many_by_external_id_omits_it(self, service: TaxomeshService) -> None:
        _give_the_root_an_external_id(service, "ext-root")

        assert dict(service.categories.get_many_by_external_id(["ext-root"])) == {}

    def test_list_excludes_it(self, service: TaxomeshService) -> None:
        service.categories.create("Alpha")

        for rows in (
            service.categories.list(),
            service.categories.list(enabled=None),
            service.categories.roots(enabled=None),
        ):
            assert service._root_id not in {row.category_id for row in rows}
            assert ROOT_CATEGORY_NAME not in {row.name for row in rows}

    def test_listing_the_categories_of_an_item_excludes_it(self, service: TaxomeshService) -> None:
        """The placement listing resolves ids straight from the links, so it needs its own rule.

        No member places an item in the root, and loading a store deletes such a placement, so it
        is written here through the repository port, as a direct write below the service would.
        """
        item = service.items.create("Thing")
        holder = service.categories.create("Holder")
        service.items.place_in(item.item_id, holder.category_id)
        service.repository.save_item_parent_link(ItemParentLink(item_id=item.item_id, category_id=service._root_id))
        service._cache.clear()

        rows = service.categories.list(item=item.item_id, enabled=None)

        assert [row.name for row in rows] == ["Holder"]

    def test_search_never_returns_it(self, service: TaxomeshService) -> None:
        """Searching the root's own reserved name finds nothing."""
        service.categories.create("Alpha")

        assert service.categories.search(ROOT_CATEGORY_NAME, enabled=None) == ()

    def test_the_graph_excludes_it(self, service: TaxomeshService) -> None:
        service.categories.create("Alpha")

        assert ROOT_CATEGORY_NAME not in {node.category.name for node in service.graph().roots}


class TestTheRootIsNotALocation:
    """Every member that takes a category as a parent, a filter or a placement answers not-found.

    The top level is reached through ``roots()`` and ``None`` in ``move`` and ``reorder`` alone.
    Each refused write is asserted with the links it would have changed, because the root is a
    stored row: a guard that went missing would let the write succeed.
    """

    @pytest.mark.parametrize(
        "read",
        [
            pytest.param(lambda s, root: s.categories.list(parent=root), id="categories.list"),
            pytest.param(lambda s, root: s.categories.search("", parent=root), id="categories.search-blank"),
            pytest.param(lambda s, root: s.categories.search("Alpha", parent=root), id="categories.search"),
            pytest.param(lambda s, root: s.items.list(category=root), id="items.list"),
            pytest.param(lambda s, root: s.items.list(category=root, recursive=True), id="items.list-recursive"),
            pytest.param(lambda s, root: s.items.search("Thing", category=root), id="items.search"),
            pytest.param(
                lambda s, root: s.items.search("Thing", category=root, recursive=True), id="items.search-recursive"
            ),
        ],
    )
    def test_a_read_filtered_by_it_raises(
        self, service: TaxomeshService, read: Callable[[TaxomeshService, UUID], object]
    ) -> None:
        service.categories.create("Alpha")
        service.items.create("Thing")

        with pytest.raises(TaxomeshCategoryNotFoundError):
            read(service, service._root_id)

    @pytest.mark.parametrize(
        "write",
        [
            pytest.param(lambda s, root, c, _o, _i: s.categories.add_parent(c, root), id="categories.add_parent"),
            pytest.param(
                lambda s, root, c, _o, _i: s.categories.remove_parent(c, root), id="categories.remove_parent"
            ),
            pytest.param(
                lambda s, root, c, o, _i: s.categories.move(c, from_parent=root, to_parent=o),
                id="categories.move-from",
            ),
            pytest.param(
                lambda s, root, c, _o, _i: s.categories.move(c, from_parent=None, to_parent=root),
                id="categories.move-to",
            ),
            pytest.param(lambda s, root, c, _o, _i: s.categories.reorder(root, [c]), id="categories.reorder"),
            pytest.param(lambda s, root, _c, _o, i: s.items.place_in(i, root), id="items.place_in"),
            pytest.param(lambda s, root, _c, _o, i: s.items.remove_from(i, root), id="items.remove_from"),
            pytest.param(
                lambda s, root, c, _o, i: s.items.move(i, from_category=root, to_category=c),
                id="items.move-from",
            ),
            pytest.param(
                lambda s, root, c, _o, i: s.items.move(i, from_category=c, to_category=root),
                id="items.move-to",
            ),
            pytest.param(lambda s, root, _c, _o, i: s.items.reorder(root, [i]), id="items.reorder"),
        ],
    )
    def test_a_write_naming_it_raises_and_changes_nothing(
        self,
        service: TaxomeshService,
        write: Callable[[TaxomeshService, UUID, UUID, UUID, UUID], object],
    ) -> None:
        alpha = service.categories.create("Alpha")
        beta = service.categories.create("Beta")
        item = service.items.create("Thing")
        service.items.place_in(item.item_id, alpha.category_id)
        before = _stored_links(service)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            write(service, service._root_id, alpha.category_id, beta.category_id, item.item_id)

        assert _stored_links(service) == before

    def test_an_unknown_category_is_refused_as_an_address_too(self, service: TaxomeshService) -> None:
        """The rule for the root is the rule for any identifier the container does not hold."""
        missing = uuid4()

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.categories.list(parent=missing)
        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.place_in(service.items.create("Thing").item_id, missing)


class TestTheRootIsStillStored:
    """This is a visibility rule at the service boundary, not a data change."""

    def test_the_row_is_still_in_storage(self, service: TaxomeshService) -> None:
        """Reached through the repository, which is below the boundary the rule applies at."""
        root = service.repository.find_category(service._root_id)

        assert root is not None
        assert root.name == ROOT_CATEGORY_NAME

    def test_creating_a_category_still_links_it_to_the_root(self, service: TaxomeshService) -> None:
        """The link the root exists for is unchanged — it is what makes ``roots()`` computable."""
        created = service.categories.create("Alpha")

        links = service.repository.list_category_parent_links()

        assert any(
            link.category_id == created.category_id and link.parent_category_id == service._root_id for link in links
        )
