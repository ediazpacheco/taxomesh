"""Spy-repository tests for 054: the four hot read paths must not issue full-table scans."""

import logging
from collections.abc import Collection, Mapping
from typing import Literal
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError
from tests.service.conftest import InMemoryRepository

SERVICE_LOGGER = "taxomesh.application.collections.items"


class RecordingRepository(InMemoryRepository):
    """InMemoryRepository that records calls to the read methods under scrutiny."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        self.calls.append(("list_items", {"enabled": enabled}))
        return super().list_items(enabled=enabled)

    def map_items_by_id(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Item]:
        self.calls.append(("map_items_by_id", {"item_ids": set(item_ids), "enabled": enabled}))
        return super().map_items_by_id(item_ids, enabled=enabled)

    def list_item_parent_links(
        self,
        *,
        item_ids: Collection[UUID] | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        recorded_items = set(item_ids) if item_ids is not None else None
        recorded_categories = set(category_ids) if category_ids is not None else None
        self.calls.append(
            ("list_item_parent_links", {"item_ids": recorded_items, "category_ids": recorded_categories})
        )
        return super().list_item_parent_links(item_ids=item_ids, category_ids=category_ids)

    def map_categories_by_id(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> Mapping[UUID, Category]:
        self.calls.append(("map_categories_by_id", {"category_ids": set(category_ids), "enabled": enabled}))
        return super().map_categories_by_id(category_ids, enabled=enabled)

    def list_category_parent_links(
        self,
        *,
        category_ids: Collection[UUID] | None = None,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        recorded_children = set(category_ids) if category_ids is not None else None
        recorded = set(parent_category_ids) if parent_category_ids is not None else None
        self.calls.append(
            ("list_category_parent_links", {"category_ids": recorded_children, "parent_category_ids": recorded})
        )
        return super().list_category_parent_links(category_ids=category_ids, parent_category_ids=parent_category_ids)

    def find_item(self, item_id: UUID) -> Item | None:
        self.calls.append(("find_item", {"item_id": item_id}))
        return super().find_item(item_id)

    def find_category(self, category_id: UUID) -> Category | None:
        self.calls.append(("find_category", {"category_id": category_id}))
        return super().find_category(category_id)

    def list_item_relation_links_batch(
        self,
        item_ids: Collection[UUID],
        *,
        relation_types: Collection[str] | None = None,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
    ) -> list[ItemRelationLink]:
        self.calls.append(("list_item_relation_links_batch", {"item_ids": set(item_ids), "direction": direction}))
        return super().list_item_relation_links_batch(item_ids, relation_types=relation_types, direction=direction)

    def names(self) -> list[str]:
        """Return the recorded method names in call order."""
        return [name for name, _ in self.calls]

    def count_of(self, name: str) -> int:
        """Return how many times *name* was called."""
        return sum(1 for called, _ in self.calls if called == name)

    def reset(self) -> None:
        """Discard recorded calls, so a measurement excludes fixture setup."""
        self.calls.clear()

    def kwargs_of(self, name: str) -> list[dict[str, object]]:
        """Return the recorded kwargs of every call to *name*."""
        return [kwargs for called, kwargs in self.calls if called == name]


@pytest.fixture
def spy() -> RecordingRepository:
    """Return a fresh recording repository."""
    return RecordingRepository()


@pytest.fixture
def spy_service(spy: RecordingRepository) -> TaxomeshService:
    """Return a TaxomeshService backed by the recording repository."""
    return TaxomeshService(repository=spy)


# ---------------------------------------------------------------------------
# Site 1 — items.get_many_related
# ---------------------------------------------------------------------------


def test_related_items_no_full_scan(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    source = spy_service.items.create("Source")
    target_b = spy_service.items.create("Target B")
    target_c = spy_service.items.create("Target C")
    spy_service.items.create("Unrelated")
    spy_service.items.relate(source.item_id, target_b.item_id, "covers")
    spy_service.items.relate(source.item_id, target_c.item_id, "performed_by")
    spy.calls.clear()

    result = spy_service.items.get_many_related([source.item_id])

    assert "list_items" not in spy.names()
    bulk_calls = spy.kwargs_of("map_items_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is None
    assert bulk_calls[0]["item_ids"] == {source.item_id, target_b.item_id, target_c.item_id}
    assert {item_id: dict(related.by_type) for item_id, related in result.items()} == {
        source.item_id: {"covers": (target_b,), "performed_by": (target_c,)},
    }


def test_related_items_empty_input_no_repo_access(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    spy.calls.clear()
    assert spy_service.items.get_many_related([]) == {}
    assert spy.calls == []


def test_related_items_disabled_target_filtered_without_a_warning(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A disabled target is filtered out, as a listing filters, and nothing is logged."""
    source = spy_service.items.create("Source")
    target = spy_service.items.create("Target")
    spy_service.items.relate(source.item_id, target.item_id, "covers")
    spy_service.items.update(target.item_id, enabled=False)

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = spy_service.items.get_many_related([source.item_id])

    assert result == {}
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


def test_related_items_disabled_target_returned_unfiltered(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
) -> None:
    """``enabled=None`` returns a disabled target: it is stored, so it is no error."""
    source = spy_service.items.create("Source")
    target = spy_service.items.create("Target")
    spy_service.items.relate(source.item_id, target.item_id, "covers")
    disabled = spy_service.items.update(target.item_id, enabled=False)

    result = spy_service.items.get_many_related([source.item_id], enabled=None)

    assert result[source.item_id].of_type("covers") == (disabled,)


# ---------------------------------------------------------------------------
# Site 1b — direction-aware batched traversal: incoming / both anti-N+1 (056)
# ---------------------------------------------------------------------------


def _link_query_calls(spy: RecordingRepository) -> list[dict[str, object]]:
    """Recorded calls to the unified batched link query."""
    return spy.kwargs_of("list_item_relation_links_batch")


def test_related_items_incoming_two_calls_no_full_scan(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """direction="incoming": exactly one link query (direction=incoming) + one bulk lookup; no full scan."""
    tgt = spy_service.items.create("Target")
    src_b = spy_service.items.create("Source B")
    src_c = spy_service.items.create("Source C")
    spy_service.items.create("Unrelated")
    spy_service.items.relate(src_b.item_id, tgt.item_id, "covers")
    spy_service.items.relate(src_c.item_id, tgt.item_id, "performed_by")
    spy.calls.clear()

    result = spy_service.items.get_many_related([tgt.item_id], direction="incoming")

    assert "list_items" not in spy.names()
    link_calls = _link_query_calls(spy)
    assert len(link_calls) == 1
    assert link_calls[0]["direction"] == "incoming"
    bulk_calls = spy.kwargs_of("map_items_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is None
    assert bulk_calls[0]["item_ids"] == {tgt.item_id, src_b.item_id, src_c.item_id}
    assert {item_id: dict(related.by_type) for item_id, related in result.items()} == {
        tgt.item_id: {"covers": (src_b,), "performed_by": (src_c,)}
    }


def test_related_items_incoming_call_count_constant_in_input_size(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """Repository call count does not grow with the number of queried ids (anti-N+1)."""
    targets = [spy_service.items.create(f"T{n}") for n in range(5)]
    for t in targets:
        s = spy_service.items.create(f"S-for-{t.name}")
        spy_service.items.relate(s.item_id, t.item_id, "covers")
    spy.calls.clear()

    spy_service.items.get_many_related([t.item_id for t in targets], direction="incoming")

    assert len(_link_query_calls(spy)) == 1
    assert len(spy.kwargs_of("map_items_by_id")) == 1


def test_related_items_both_two_calls(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """direction="both": a single combined link query + one bulk lookup = two calls."""
    mid = spy_service.items.create("Mid")
    out_tgt = spy_service.items.create("OutTarget")
    in_src = spy_service.items.create("InSource")
    spy_service.items.relate(mid.item_id, out_tgt.item_id, "covers")
    spy_service.items.relate(in_src.item_id, mid.item_id, "covers")
    spy.calls.clear()

    result = spy_service.items.get_many_related([mid.item_id], direction="both")

    assert "list_items" not in spy.names()
    link_calls = _link_query_calls(spy)
    assert len(link_calls) == 1
    assert link_calls[0]["direction"] == "both"
    assert len(spy.kwargs_of("map_items_by_id")) == 1
    assert [i.item_id for i in result[mid.item_id].of_type("covers")] == [out_tgt.item_id, in_src.item_id]


def test_related_items_both_call_count_constant_in_input_size(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """The two-call bound for "both" stays constant as the number of queried ids grows."""
    mids = [spy_service.items.create(f"M{n}") for n in range(5)]
    for m in mids:
        out_t = spy_service.items.create(f"out-{m.name}")
        in_s = spy_service.items.create(f"in-{m.name}")
        spy_service.items.relate(m.item_id, out_t.item_id, "covers")
        spy_service.items.relate(in_s.item_id, m.item_id, "covers")
    spy.calls.clear()

    spy_service.items.get_many_related([m.item_id for m in mids], direction="both")

    assert len(_link_query_calls(spy)) == 1
    assert len(spy.kwargs_of("map_items_by_id")) == 1


# ---------------------------------------------------------------------------
# Site 2 — categories.list(item=…)
# ---------------------------------------------------------------------------


def test_categories_by_item_uses_item_filter(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    cat_a = spy_service.categories.create("Cat A")
    cat_b = spy_service.categories.create("Cat B")
    item = spy_service.items.create("Item")
    other = spy_service.items.create("Other")
    spy_service.items.place_in(item.item_id, cat_b.category_id, sort_index=0)
    spy_service.items.place_in(item.item_id, cat_a.category_id, sort_index=1)
    spy_service.items.place_in(other.item_id, cat_a.category_id, sort_index=0)
    spy.calls.clear()

    result = spy_service.categories.list(item=item.item_id)

    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["item_ids"] == {item.item_id}
    assert [c.category_id for c in result] == [cat_b.category_id, cat_a.category_id]  # sort_index order


def test_categories_by_item_unknown_item_raises_before_link_query(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
) -> None:
    spy.calls.clear()
    with pytest.raises(TaxomeshItemNotFoundError):
        spy_service.categories.list(item=uuid4())
    assert "list_item_parent_links" not in spy.names()


# ---------------------------------------------------------------------------
# Site 3 — _load_item_candidates recursive path
# ---------------------------------------------------------------------------


def _uuid(n: int) -> UUID:
    """Deterministic UUID whose string form sorts in numeric order of n."""
    return UUID(int=n)


def _seed_tree(spy: RecordingRepository) -> TaxomeshService:
    """Parent category (1) with child (2); items 11/12 in parent, 12/13 in child, 14 outside.

    Item 12 is placed in BOTH categories (dedup case); the service is created
    after seeding so no memoized state predates the data.
    """
    spy.save_category(Category(category_id=_uuid(1), name="parent"))
    spy.save_category(Category(category_id=_uuid(2), name="child"))
    spy.save_category(Category(category_id=_uuid(3), name="outside"))
    for n in (11, 12, 13, 14):
        spy.save_item(Item(item_id=_uuid(n), name=f"item-{n}"))
    spy._category_parent_links.append(CategoryParentLink(category_id=_uuid(2), parent_category_id=_uuid(1)))
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(11), category_id=_uuid(1), sort_index=0))
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(12), category_id=_uuid(1), sort_index=1))
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(12), category_id=_uuid(2), sort_index=0))
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(13), category_id=_uuid(2), sort_index=1))
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(14), category_id=_uuid(3), sort_index=0))
    return TaxomeshService(repository=spy)


def test_recursive_candidates_no_full_scan(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()

    items = svc.items._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert "list_items" not in spy.names()
    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["category_ids"] == {_uuid(1), _uuid(2)}
    bulk_calls = spy.kwargs_of("map_items_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is True
    # Dedup: item 12 (in both categories) appears exactly once; item 14 (outside) excluded.
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12), _uuid(13)]


def test_recursive_candidates_dangling_item_silently_skipped(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(99), category_id=_uuid(2), sort_index=2))

    items = svc.items._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert _uuid(99) not in {item.item_id for item in items}
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12), _uuid(13)]


def test_recursive_candidates_disabled_item_excluded(spy: RecordingRepository) -> None:
    """Parity pin: the recursive item map has always been enabled-only."""
    svc = _seed_tree(spy)
    spy.save_item(Item(item_id=_uuid(13), name="item-13", enabled=False))

    items = svc.items._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert [item.item_id for item in items] == [_uuid(11), _uuid(12)]


def test_recursive_candidates_unknown_category_raises(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.items._load_item_candidates(category_id=uuid4(), recursive=True)
    assert "list_item_parent_links" not in spy.names()


def test_items_search_recursive_public_path_no_full_scan(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()

    results = svc.items.search("item", category=_uuid(1), recursive=True, fuzzy=False)

    assert "list_items" not in spy.names()
    assert {item.item_id for item in results} <= {_uuid(11), _uuid(12), _uuid(13)}


# ---------------------------------------------------------------------------
# Site 4 — list_items(category_id=...) non-recursive path
# ---------------------------------------------------------------------------


def test_items_list_in_category_uses_category_filter(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()

    items = svc.items.list(category=_uuid(1))

    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["category_ids"] == {_uuid(1)}
    # sort_index order within the category; child-category items excluded.
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12)]


def test_items_list_in_category_dangling_link_raises(spy: RecordingRepository) -> None:
    """A placement naming an absent item makes the non-recursive listing raise the item's not-found."""
    svc = _seed_tree(spy)
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(99), category_id=_uuid(1), sort_index=9))

    with pytest.raises(TaxomeshItemNotFoundError):
        svc.items.list(category=_uuid(1))


def test_items_list_in_category_unknown_category_raises(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.items.list(category=uuid4())
    assert "list_item_parent_links" not in spy.names()


def test_items_list_in_category_enabled_filter_respected(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.save_item(Item(item_id=_uuid(12), name="item-12", enabled=False))

    items = svc.items.list(category=_uuid(1), enabled=True)

    assert [item.item_id for item in items] == [_uuid(11)]


def test_related_items_disabled_source_is_named_in_the_warning(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A disabled queried item is stored, so the warning for its absent target names it."""
    source = Item(name="Disabled Source", enabled=False)
    spy.save_item(source)
    missing_target_id = uuid4()
    spy._item_relation_links.append(
        ItemRelationLink(
            source_item_id=source.item_id,
            target_item_id=missing_target_id,
            relation_type="covers",
        )
    )

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = spy_service.items.get_many_related([source.item_id])

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    message = warning_records[0].getMessage()
    assert "Disabled Source" in message
    assert f"target item {missing_target_id} is absent" in message


# ---------------------------------------------------------------------------
# Site 5 — the three placement read paths
# ---------------------------------------------------------------------------
#
# These assert the *shape* of the calls the service makes: one batch resolve,
# never one resolve per returned row. The gate runs on the in-memory backend
# only, and that is sufficient — the service layer has no backend-conditional
# branching, so the sequence of port calls is identical whichever repository sits
# underneath. Per-backend evidence is the query-count module under
# tests/contrib/django/ and the parity assertions under tests/service/.


def test_items_list_by_category_resolves_in_one_batch(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """Zero single-row item reads, one batch call carrying every id."""
    category = spy_service.categories.create("Jazz")
    placed = [spy_service.items.create(f"Album {i}") for i in range(4)]
    for index, item in enumerate(placed):
        spy_service.items.place_in(item.item_id, category.category_id, sort_index=index)
    spy_service.items.create("Elsewhere")
    spy.reset()

    result = spy_service.items.list(category=category.category_id)

    assert spy.count_of("find_item") == 0, "an item was resolved one row at a time"
    assert spy.count_of("list_items") == 0, "the whole item table was scanned"
    bulk_calls = spy.kwargs_of("map_items_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["item_ids"] == {item.item_id for item in placed}
    # Unfiltered by design: a disabled endpoint must stay distinguishable from one
    # that is not stored, because an absent key raises.
    assert bulk_calls[0]["enabled"] is None
    assert result == tuple(placed)


def test_items_list_by_category_checks_existence_exactly_once(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """Listing a category checks that it exists, and that check costs exactly one read."""
    category = spy_service.categories.create("Rock")
    item = spy_service.items.create("Album")
    spy_service.items.place_in(item.item_id, category.category_id)
    spy.reset()

    spy_service.items.list(category=category.category_id)

    assert spy.count_of("find_category") == 1


def test_items_list_by_category_skips_the_batch_when_empty(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """No links means no batch resolve at all."""
    category = spy_service.categories.create("Empty")
    spy.reset()

    assert spy_service.items.list(category=category.category_id) == ()
    assert spy.count_of("map_items_by_id") == 0


def test_categories_list_by_parent_resolves_in_one_batch(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """One batch resolve, and the link read is pushed down to this parent only."""
    parent = spy_service.categories.create("Parent")
    children = [spy_service.categories.create(f"Child {i}") for i in range(4)]
    for index, child in enumerate(children):
        spy_service.categories.add_parent(child.category_id, parent.category_id, sort_index=index)
    elsewhere = spy_service.categories.create("Elsewhere")
    spy_service.categories.add_parent(elsewhere.category_id, spy_service.categories.create("Other").category_id)
    spy.reset()

    result = spy_service.categories.list(parent=parent.category_id)

    bulk_calls = spy.kwargs_of("map_categories_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["category_ids"] == {child.category_id for child in children}
    assert bulk_calls[0]["enabled"] is None
    # The whole link table must not be read to answer one parent.
    link_calls = spy.kwargs_of("list_category_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["parent_category_ids"] == {parent.category_id}
    assert result == tuple(children)


def test_categories_list_by_parent_checks_existence_exactly_once(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """EXACTLY one single-row category read — the existence check — never zero.

    A blanket "zero" assertion is wrong for this path: the check and the
    resolution concern the same entity type. Asserting zero here would fail on a
    correct implementation.
    """
    parent = spy_service.categories.create("Parent")
    child = spy_service.categories.create("Child")
    spy_service.categories.add_parent(child.category_id, parent.category_id)
    spy.reset()

    spy_service.categories.list(parent=parent.category_id)

    assert spy.count_of("find_category") == 1


def test_categories_list_by_item_resolves_in_one_batch(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """Zero single-row CATEGORY reads here — the existence check reads an item."""
    item = spy_service.items.create("Placed")
    categories = [spy_service.categories.create(f"Cat {i}") for i in range(4)]
    for index, category in enumerate(categories):
        spy_service.items.place_in(item.item_id, category.category_id, sort_index=index)
    spy.reset()

    result = spy_service.categories.list(item=item.item_id)

    assert spy.count_of("find_category") == 0, "a category was resolved one row at a time"
    assert spy.count_of("find_item") == 1, "the existence check must remain, and cost exactly one read"
    bulk_calls = spy.kwargs_of("map_categories_by_id")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["category_ids"] == {category.category_id for category in categories}
    assert bulk_calls[0]["enabled"] is None
    assert result == tuple(categories)
