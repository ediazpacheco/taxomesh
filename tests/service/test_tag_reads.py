"""Tags are read back: the port's tag-link read, an item's tags and a tag's items.

``tags.list(item=…)`` and ``items.list(tag=…)`` order by name, then identifier, since a tag
link carries no sort index. ``items.list`` composes the tag filter with ``category``: the
category listing, in its own order, keeps only the items carrying the tag.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from taxomesh.adapters.repositories.json_repository import JsonRepository
from taxomesh.adapters.repositories.yaml_repository import YamlRepository
from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Item, ItemTagLink, Tag
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError, TaxomeshTagNotFoundError
from tests.service.conftest import InMemoryRepository


@dataclass(frozen=True)
class Tagged:
    """Three items and three tags, linked in an order that is neither name nor id order."""

    percanta: Item
    mina: Item
    garufa: Item
    tango: Tag
    lunfardo: Tag
    milonga: Tag


def _tagged(service: TaxomeshService) -> Tagged:
    """Store the rows and tag them: every item carries ``tango``, and only Percanta the others."""
    percanta = service.items.create("Percanta")
    mina = service.items.create("Mina")
    garufa = service.items.create("Garufa")
    tango = service.tags.create("tango")
    lunfardo = service.tags.create("lunfardo")
    milonga = service.tags.create("milonga")
    for tag in (tango, milonga, lunfardo):
        service.items.tag(percanta.item_id, tag.tag_id)
    service.items.tag(mina.item_id, tango.tag_id)
    service.items.tag(garufa.item_id, tango.tag_id)
    return Tagged(percanta, mina, garufa, tango, lunfardo, milonga)


def _pairs(links: Sequence[ItemTagLink]) -> list[tuple[UUID, UUID]]:
    """Return each link as its ``(item_id, tag_id)`` pair, in the order read."""
    return [(link.item_id, link.tag_id) for link in links]


class TestThePortReadsTagLinks:
    def test_every_link_in_item_then_tag_order(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        expected = sorted(
            [(t.percanta.item_id, tag.tag_id) for tag in (t.tango, t.lunfardo, t.milonga)]
            + [(item.item_id, t.tango.tag_id) for item in (t.mina, t.garufa)]
        )

        assert _pairs(service.repository.list_item_tag_links()) == expected

    def test_filtered_by_item(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        expected = sorted((t.percanta.item_id, tag.tag_id) for tag in (t.tango, t.lunfardo, t.milonga))

        assert _pairs(service.repository.list_item_tag_links(item_ids=[t.percanta.item_id])) == expected

    def test_filtered_by_tag(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        expected = sorted((item.item_id, t.tango.tag_id) for item in (t.percanta, t.mina, t.garufa))

        assert _pairs(service.repository.list_item_tag_links(tag_ids=[t.tango.tag_id])) == expected

    def test_both_filters_hold_together(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        links = service.repository.list_item_tag_links(
            item_ids=[t.percanta.item_id, t.mina.item_id], tag_ids=[t.tango.tag_id, t.milonga.tag_id]
        )
        expected = sorted(
            [
                (t.percanta.item_id, t.tango.tag_id),
                (t.percanta.item_id, t.milonga.tag_id),
                (t.mina.item_id, t.tango.tag_id),
            ]
        )

        assert _pairs(links) == expected

    def test_an_empty_filter_matches_nothing(self, service: TaxomeshService) -> None:
        _tagged(service)

        assert list(service.repository.list_item_tag_links(item_ids=[])) == []
        assert list(service.repository.list_item_tag_links(tag_ids=[])) == []


class TestTagsListByItem:
    def test_an_items_tags_in_name_order(self, service: TaxomeshService) -> None:
        t = _tagged(service)

        assert service.tags.list(item=t.percanta.item_id) == (t.lunfardo, t.milonga, t.tango)

    def test_tags_sharing_a_name_are_ordered_by_id(self, service: TaxomeshService) -> None:
        item = service.items.create("Percanta")
        twins = [service.tags.create("tango") for _ in range(3)]
        for tag in twins:
            service.items.tag(item.item_id, tag.tag_id)

        assert service.tags.list(item=item.item_id) == tuple(sorted(twins, key=lambda tag: str(tag.tag_id)))

    def test_an_untagged_item_has_no_tags(self, service: TaxomeshService) -> None:
        _tagged(service)
        bare = service.items.create("Bare")

        assert service.tags.list(item=bare.item_id) == ()

    def test_the_unfiltered_listing_keeps_every_tag(self, service: TaxomeshService) -> None:
        t = _tagged(service)

        assert {tag.name for tag in service.tags.list()} == {t.tango.name, t.lunfardo.name, t.milonga.name}

    def test_tagging_and_untagging_show_through_a_warm_cache(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        assert service.tags.list(item=t.mina.item_id) == (t.tango,)

        service.items.tag(t.mina.item_id, t.lunfardo.tag_id)
        assert service.tags.list(item=t.mina.item_id) == (t.lunfardo, t.tango)

        service.items.untag(t.mina.item_id, t.tango.tag_id)
        assert service.tags.list(item=t.mina.item_id) == (t.lunfardo,)

    def test_an_unknown_item_raises(self, service: TaxomeshService) -> None:
        _tagged(service)
        unknown = uuid4()

        with pytest.raises(TaxomeshItemNotFoundError, match=str(unknown)):
            service.tags.list(item=unknown)


class TestItemsListByTag:
    def test_a_tags_items_in_name_order(self, service: TaxomeshService) -> None:
        t = _tagged(service)

        assert service.items.list(tag=t.tango.tag_id) == (t.garufa, t.mina, t.percanta)

    def test_a_tag_on_no_item_lists_nothing(self, service: TaxomeshService) -> None:
        _tagged(service)
        unused = service.tags.create("unused")

        assert service.items.list(tag=unused.tag_id) == ()

    def test_the_enabled_filter_applies(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        mina = service.items.update(t.mina.item_id, enabled=False)

        assert service.items.list(tag=t.tango.tag_id) == (t.garufa, t.percanta)
        assert service.items.list(tag=t.tango.tag_id, enabled=False) == (mina,)
        assert service.items.list(tag=t.tango.tag_id, enabled=None) == (t.garufa, mina, t.percanta)

    def test_untagging_shows_through_a_warm_cache(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        assert service.items.list(tag=t.lunfardo.tag_id) == (t.percanta,)

        service.items.untag(t.percanta.item_id, t.lunfardo.tag_id)
        assert service.items.list(tag=t.lunfardo.tag_id) == ()

    def test_an_unknown_tag_raises(self, service: TaxomeshService) -> None:
        _tagged(service)
        unknown = uuid4()

        with pytest.raises(TaxomeshTagNotFoundError, match=str(unknown)):
            service.items.list(tag=unknown)

    def test_recursive_without_a_category_is_ignored(self, service: TaxomeshService) -> None:
        t = _tagged(service)

        assert service.items.list(tag=t.tango.tag_id, recursive=True) == service.items.list(tag=t.tango.tag_id)


class TestTheTagFilterComposesWithACategory:
    def test_the_category_listing_keeps_its_order_and_only_the_tagged_items(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        records = service.categories.create("Records")
        for index, item in enumerate((t.percanta, t.mina, t.garufa)):
            service.items.place_in(item.item_id, records.category_id, sort_index=index)

        tagged = service.items.list(category=records.category_id, tag=t.tango.tag_id)
        lunfardo = service.items.list(category=records.category_id, tag=t.lunfardo.tag_id)

        assert tagged == (t.percanta, t.mina, t.garufa)
        assert lunfardo == (t.percanta,)

    def test_a_recursive_listing_keeps_its_order_and_only_the_tagged_items(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        records = service.categories.create("Records")
        singles = service.categories.create("Singles")
        service.categories.add_parent(singles.category_id, records.category_id)
        service.items.place_in(t.garufa.item_id, records.category_id, sort_index=0)
        service.items.place_in(t.percanta.item_id, singles.category_id, sort_index=0)
        service.items.place_in(t.mina.item_id, singles.category_id, sort_index=1)
        untagged = service.items.create("Untagged")
        service.items.place_in(untagged.item_id, singles.category_id, sort_index=2)

        found = service.items.list(category=records.category_id, recursive=True, tag=t.tango.tag_id)

        assert found == (t.garufa, t.percanta, t.mina)

    def test_a_tag_on_nothing_in_the_category_lists_nothing(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        records = service.categories.create("Records")
        service.items.place_in(t.mina.item_id, records.category_id)

        assert service.items.list(category=records.category_id, tag=t.lunfardo.tag_id) == ()

    def test_the_enabled_filter_applies_to_the_composition(self, service: TaxomeshService) -> None:
        t = _tagged(service)
        records = service.categories.create("Records")
        service.items.place_in(t.percanta.item_id, records.category_id, sort_index=0)
        service.items.place_in(t.mina.item_id, records.category_id, sort_index=1)
        mina = service.items.update(t.mina.item_id, enabled=False)

        assert service.items.list(category=records.category_id, tag=t.tango.tag_id) == (t.percanta,)
        assert service.items.list(category=records.category_id, tag=t.tango.tag_id, enabled=False) == (mina,)

    def test_an_unknown_category_raises_before_the_tag_is_checked(self, service: TaxomeshService) -> None:
        _tagged(service)

        with pytest.raises(TaxomeshCategoryNotFoundError):
            service.items.list(category=uuid4(), tag=uuid4())

    def test_an_unknown_tag_raises_beside_a_stored_category(self, service: TaxomeshService) -> None:
        _tagged(service)
        records = service.categories.create("Records")

        with pytest.raises(TaxomeshTagNotFoundError):
            service.items.list(category=records.category_id, tag=uuid4())


@pytest.fixture(params=["in_memory", "json", "yaml"])
def unchecked_service(request: pytest.FixtureRequest, tmp_path: Path) -> TaxomeshService:
    """A service over a backend that stores a link without checking its ends, unlike Django."""
    if request.param == "json":
        return TaxomeshService(repository=JsonRepository(tmp_path / "tags.json"))
    if request.param == "yaml":
        return TaxomeshService(repository=YamlRepository(tmp_path / "tags.yaml"))
    return TaxomeshService(repository=InMemoryRepository())


class TestALinkToAMissingRowRaises:
    """A link naming a row that is not stored raises that row's error, as a dangling placement does."""

    def test_an_items_link_to_a_missing_tag(self, unchecked_service: TaxomeshService) -> None:
        item = unchecked_service.items.create("Percanta")
        missing = uuid4()
        unchecked_service.repository.add_item_tag_link(item.item_id, missing)

        with pytest.raises(TaxomeshTagNotFoundError, match=str(missing)):
            unchecked_service.tags.list(item=item.item_id)

    def test_a_tags_link_to_a_missing_item(self, unchecked_service: TaxomeshService) -> None:
        tag = unchecked_service.tags.create("tango")
        missing = uuid4()
        unchecked_service.repository.add_item_tag_link(missing, tag.tag_id)

        with pytest.raises(TaxomeshItemNotFoundError, match=str(missing)):
            unchecked_service.items.list(tag=tag.tag_id)
