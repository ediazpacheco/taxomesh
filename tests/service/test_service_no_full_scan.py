"""Spy-repository tests for 054: the four hot read paths must not issue full-table scans."""

import logging
from collections.abc import Collection
from typing import Literal
from uuid import UUID, uuid4

import pytest

from taxomesh.application.service import TaxomeshService
from taxomesh.domain.models import Category, CategoryParentLink, Item, ItemParentLink, ItemRelationLink
from taxomesh.exceptions import TaxomeshCategoryNotFoundError, TaxomeshItemNotFoundError
from tests.service.conftest import InMemoryRepository

SERVICE_LOGGER = "taxomesh.application.service"


class RecordingRepository(InMemoryRepository):
    """InMemoryRepository that records calls to the read methods under scrutiny."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_items(self, *, enabled: bool | None = True) -> list[Item]:
        self.calls.append(("list_items", {"enabled": enabled}))
        return super().list_items(enabled=enabled)

    def get_items_by_ids(
        self,
        item_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> dict[UUID, Item]:
        self.calls.append(("get_items_by_ids", {"item_ids": set(item_ids), "enabled": enabled}))
        return super().get_items_by_ids(item_ids, enabled=enabled)

    def list_item_parent_links(
        self,
        *,
        item_id: UUID | None = None,
        category_ids: Collection[UUID] | None = None,
    ) -> list[ItemParentLink]:
        recorded_categories = set(category_ids) if category_ids is not None else None
        self.calls.append(("list_item_parent_links", {"item_id": item_id, "category_ids": recorded_categories}))
        return super().list_item_parent_links(item_id=item_id, category_ids=category_ids)

    def get_categories_by_ids(
        self,
        category_ids: Collection[UUID],
        *,
        enabled: bool | None = None,
    ) -> dict[UUID, Category]:
        self.calls.append(("get_categories_by_ids", {"category_ids": set(category_ids), "enabled": enabled}))
        return super().get_categories_by_ids(category_ids, enabled=enabled)

    def list_category_parent_links(
        self,
        *,
        parent_category_ids: Collection[UUID] | None = None,
    ) -> list[CategoryParentLink]:
        recorded = set(parent_category_ids) if parent_category_ids is not None else None
        self.calls.append(("list_category_parent_links", {"parent_category_ids": recorded}))
        return super().list_category_parent_links(parent_category_ids=parent_category_ids)

    def get_item(self, item_id: UUID) -> Item | None:
        self.calls.append(("get_item", {"item_id": item_id}))
        return super().get_item(item_id)

    def get_category(self, category_id: UUID) -> Category | None:
        self.calls.append(("get_category", {"category_id": category_id}))
        return super().get_category(category_id)

    def list_item_relation_links_for_items(
        self,
        item_ids: Collection[UUID],
        *,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        relation_types: Collection[str] | None = None,
    ) -> list[ItemRelationLink]:
        self.calls.append(("list_item_relation_links_for_items", {"item_ids": set(item_ids), "direction": direction}))
        return super().list_item_relation_links_for_items(item_ids, direction=direction, relation_types=relation_types)

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
# Site 1 — list_related_items_for_sources (US1)
# ---------------------------------------------------------------------------


def test_related_items_no_full_scan(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    source = spy_service.create_item("Source")
    target_b = spy_service.create_item("Target B")
    target_c = spy_service.create_item("Target C")
    unrelated = spy_service.create_item("Unrelated")
    spy_service.relate_items(source.item_id, target_b.item_id, "covers")
    spy_service.relate_items(source.item_id, target_c.item_id, "performed_by")
    spy.calls.clear()

    result = spy_service.list_related_items_for_sources([source.item_id])

    assert "list_items" not in spy.names()
    bulk_calls = spy.kwargs_of("get_items_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is True
    assert bulk_calls[0]["item_ids"] == {source.item_id, target_b.item_id, target_c.item_id}
    assert unrelated.item_id not in bulk_calls[0]["item_ids"]  # type: ignore[operator]
    assert result == {
        source.item_id: {"covers": [target_b], "performed_by": [target_c]},
    }


def test_related_items_empty_input_no_repo_access(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    spy.calls.clear()
    assert spy_service.list_related_items_for_sources([]) == {}
    assert spy.calls == []


def test_related_items_disabled_target_skipped_with_warning(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R1 parity pin: a DISABLED target is treated as dangling (the item map is enabled-only)."""
    source = spy_service.create_item("Source")
    target = spy_service.create_item("Target")
    spy_service.relate_items(source.item_id, target.item_id, "covers")
    spy_service.update_item(target.item_id, enabled=False)

    with caplog.at_level(logging.WARNING, logger=SERVICE_LOGGER):
        result = spy_service.list_related_items_for_sources([source.item_id])

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    msg = warning_records[0].getMessage()
    assert "Source" in msg
    assert f"<orphaned item {target.item_id}>" in msg


def test_related_items_disabled_target_raises_when_skip_disabled(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
) -> None:
    """R1 parity pin: skip_on_error=False raises with the exact historical message."""
    source = spy_service.create_item("Source")
    target = spy_service.create_item("Target")
    spy_service.relate_items(source.item_id, target.item_id, "covers")
    spy_service.update_item(target.item_id, enabled=False)

    with pytest.raises(TaxomeshItemNotFoundError) as excinfo:
        spy_service.list_related_items_for_sources([source.item_id], skip_on_error=False)
    assert str(excinfo.value) == f"Item {target.item_id!r} referenced by relation not found"


# ---------------------------------------------------------------------------
# Site 1b — direction-aware batched traversal: incoming / both anti-N+1 (056)
# ---------------------------------------------------------------------------


def _link_query_calls(spy: RecordingRepository) -> list[dict[str, object]]:
    """Recorded calls to the unified batched link query."""
    return spy.kwargs_of("list_item_relation_links_for_items")


def test_related_items_incoming_two_calls_no_full_scan(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """direction="incoming": exactly one link query (direction=incoming) + one bulk lookup; no full scan."""
    tgt = spy_service.create_item("Target")
    src_b = spy_service.create_item("Source B")
    src_c = spy_service.create_item("Source C")
    unrelated = spy_service.create_item("Unrelated")
    spy_service.relate_items(src_b.item_id, tgt.item_id, "covers")
    spy_service.relate_items(src_c.item_id, tgt.item_id, "performed_by")
    spy.calls.clear()

    result = spy_service.list_related_items_for_sources([tgt.item_id], direction="incoming")

    assert "list_items" not in spy.names()
    link_calls = _link_query_calls(spy)
    assert len(link_calls) == 1
    assert link_calls[0]["direction"] == "incoming"
    bulk_calls = spy.kwargs_of("get_items_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is True
    assert bulk_calls[0]["item_ids"] == {tgt.item_id, src_b.item_id, src_c.item_id}
    assert unrelated.item_id not in bulk_calls[0]["item_ids"]  # type: ignore[operator]
    assert result == {tgt.item_id: {"covers": [src_b], "performed_by": [src_c]}}


def test_related_items_incoming_call_count_constant_in_input_size(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """Repository call count does not grow with the number of queried ids (anti-N+1)."""
    targets = [spy_service.create_item(f"T{n}") for n in range(5)]
    for t in targets:
        s = spy_service.create_item(f"S-for-{t.name}")
        spy_service.relate_items(s.item_id, t.item_id, "covers")
    spy.calls.clear()

    spy_service.list_related_items_for_sources([t.item_id for t in targets], direction="incoming")

    assert len(_link_query_calls(spy)) == 1
    assert len(spy.kwargs_of("get_items_by_ids")) == 1


def test_related_items_both_two_calls(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """direction="both": a single combined link query + one bulk lookup = two calls."""
    mid = spy_service.create_item("Mid")
    out_tgt = spy_service.create_item("OutTarget")
    in_src = spy_service.create_item("InSource")
    spy_service.relate_items(mid.item_id, out_tgt.item_id, "covers")
    spy_service.relate_items(in_src.item_id, mid.item_id, "covers")
    spy.calls.clear()

    result = spy_service.list_related_items_for_sources([mid.item_id], direction="both")

    assert "list_items" not in spy.names()
    link_calls = _link_query_calls(spy)
    assert len(link_calls) == 1
    assert link_calls[0]["direction"] == "both"
    assert len(spy.kwargs_of("get_items_by_ids")) == 1
    assert [i.item_id for i in result[mid.item_id]["covers"]] == [out_tgt.item_id, in_src.item_id]


def test_related_items_both_call_count_constant_in_input_size(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """The two-call bound for "both" stays constant as the number of queried ids grows."""
    mids = [spy_service.create_item(f"M{n}") for n in range(5)]
    for m in mids:
        out_t = spy_service.create_item(f"out-{m.name}")
        in_s = spy_service.create_item(f"in-{m.name}")
        spy_service.relate_items(m.item_id, out_t.item_id, "covers")
        spy_service.relate_items(in_s.item_id, m.item_id, "covers")
    spy.calls.clear()

    spy_service.list_related_items_for_sources([m.item_id for m in mids], direction="both")

    assert len(_link_query_calls(spy)) == 1
    assert len(spy.kwargs_of("get_items_by_ids")) == 1


# ---------------------------------------------------------------------------
# Site 2 — list_categories_by_item (US2)
# ---------------------------------------------------------------------------


def test_categories_by_item_uses_item_filter(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    cat_a = spy_service.create_category("Cat A")
    cat_b = spy_service.create_category("Cat B")
    item = spy_service.create_item("Item")
    other = spy_service.create_item("Other")
    spy_service.place_item_in_category(item.item_id, cat_b.category_id, sort_index=0)
    spy_service.place_item_in_category(item.item_id, cat_a.category_id, sort_index=1)
    spy_service.place_item_in_category(other.item_id, cat_a.category_id, sort_index=0)
    spy.calls.clear()

    result = spy_service.list_categories_by_item(item.item_id)

    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["item_id"] == item.item_id
    assert [c.category_id for c in result] == [cat_b.category_id, cat_a.category_id]  # sort_index order


def test_categories_by_item_unknown_item_raises_before_link_query(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
) -> None:
    spy.calls.clear()
    with pytest.raises(TaxomeshItemNotFoundError):
        spy_service.list_categories_by_item(uuid4())
    assert "list_item_parent_links" not in spy.names()


# ---------------------------------------------------------------------------
# Site 3 — _load_item_candidates recursive path (US3)
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

    items = svc._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert "list_items" not in spy.names()
    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["category_ids"] == {_uuid(1), _uuid(2)}
    bulk_calls = spy.kwargs_of("get_items_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["enabled"] is True
    # Dedup: item 12 (in both categories) appears exactly once; item 14 (outside) excluded.
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12), _uuid(13)]


def test_recursive_candidates_dangling_item_silently_skipped(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(99), category_id=_uuid(2), sort_index=2))

    items = svc._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert _uuid(99) not in {item.item_id for item in items}
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12), _uuid(13)]


def test_recursive_candidates_disabled_item_excluded(spy: RecordingRepository) -> None:
    """R1 parity pin: the recursive item map has always been enabled-only."""
    svc = _seed_tree(spy)
    spy.save_item(Item(item_id=_uuid(13), name="item-13", enabled=False))

    items = svc._load_item_candidates(category_id=_uuid(1), recursive=True)

    assert [item.item_id for item in items] == [_uuid(11), _uuid(12)]


def test_recursive_candidates_unknown_category_raises(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc._load_item_candidates(category_id=uuid4(), recursive=True)
    assert "list_item_parent_links" not in spy.names()


def test_search_items_recursive_public_path_no_full_scan(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()

    results = svc.search_items("item", category_id=_uuid(1), recursive=True, fuzzy=False)

    assert "list_items" not in spy.names()
    assert {item.item_id for item in results} <= {_uuid(11), _uuid(12), _uuid(13)}


# ---------------------------------------------------------------------------
# Site 4 — list_items(category_id=...) non-recursive path (US3)
# ---------------------------------------------------------------------------


def test_list_items_in_category_uses_category_filter(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()

    items = svc.list_items(category_id=_uuid(1))

    link_calls = spy.kwargs_of("list_item_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["category_ids"] == {_uuid(1)}
    # sort_index order within the category; child-category items excluded.
    assert [item.item_id for item in items] == [_uuid(11), _uuid(12)]


def test_list_items_in_category_dangling_link_still_raises(spy: RecordingRepository) -> None:
    """R2 parity pin: the non-recursive path resolves items via get_item and must keep raising."""
    svc = _seed_tree(spy)
    spy.save_item_parent_link(ItemParentLink(item_id=_uuid(99), category_id=_uuid(1), sort_index=9))

    with pytest.raises(TaxomeshItemNotFoundError):
        svc.list_items(category_id=_uuid(1))


def test_list_items_in_category_unknown_category_raises(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.calls.clear()
    with pytest.raises(TaxomeshCategoryNotFoundError):
        svc.list_items(category_id=uuid4())
    assert "list_item_parent_links" not in spy.names()


def test_list_items_in_category_enabled_filter_respected(spy: RecordingRepository) -> None:
    svc = _seed_tree(spy)
    spy.save_item(Item(item_id=_uuid(12), name="item-12", enabled=False))

    items = svc.list_items(category_id=_uuid(1), enabled=True)

    assert [item.item_id for item in items] == [_uuid(11)]


def test_related_items_disabled_source_renders_unknown_in_warning(
    spy: RecordingRepository,
    spy_service: TaxomeshService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R1 parity pin: a DISABLED source is absent from the (enabled-only) map → unknown-source repr."""
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
        result = spy_service.list_related_items_for_sources([source.item_id])

    assert result == {}
    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    assert f"<unknown source item {source.item_id}>" in warning_records[0].getMessage()


# ---------------------------------------------------------------------------
# Site 5 — the three placement read paths (spec 060, finding F1)
# ---------------------------------------------------------------------------
#
# These assert the *shape* of the calls the service makes: one batch resolve,
# never one resolve per returned row. The gate runs on the in-memory backend
# only, and that is sufficient — the service layer has no backend-conditional
# branching, so the sequence of port calls is identical whichever adapter sits
# underneath (FR-020). Per-backend evidence is the query-count module under
# tests/contrib/django/ and the parity assertions under tests/service/.


def test_list_items_by_category_resolves_in_one_batch(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """FR-020: zero single-row item reads, one batch call carrying every id."""
    category = spy_service.create_category("Jazz")
    placed = [spy_service.create_item(f"Album {i}") for i in range(4)]
    for index, item in enumerate(placed):
        spy_service.place_item_in_category(item.item_id, category.category_id, sort_index=index)
    other = spy_service.create_item("Elsewhere")
    spy.reset()

    result = spy_service.list_items(category_id=category.category_id)

    assert spy.count_of("get_item") == 0, "an item was resolved one row at a time — finding F1 has returned"
    assert spy.count_of("list_items") == 0, "the whole item table was scanned"
    bulk_calls = spy.kwargs_of("get_items_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["item_ids"] == {item.item_id for item in placed}
    assert other.item_id not in bulk_calls[0]["item_ids"]  # type: ignore[operator]
    # Unfiltered by design: a disabled endpoint must stay distinguishable from a
    # missing one, because an absent key raises (FR-011, FR-012).
    assert bulk_calls[0]["enabled"] is None
    assert result == placed


def test_list_items_by_category_checks_existence_exactly_once(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """FR-013: the existence check survives the rewrite, and costs exactly one read."""
    category = spy_service.create_category("Rock")
    item = spy_service.create_item("Album")
    spy_service.place_item_in_category(item.item_id, category.category_id)
    spy.reset()

    spy_service.list_items(category_id=category.category_id)

    assert spy.count_of("get_category") == 1


def test_list_items_by_category_skips_the_batch_when_empty(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """FR-016: no links means no batch resolve at all."""
    category = spy_service.create_category("Empty")
    spy.reset()

    assert spy_service.list_items(category_id=category.category_id) == []
    assert spy.count_of("get_items_by_ids") == 0


def test_list_categories_by_parent_resolves_in_one_batch(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """FR-020: one batch resolve, and the link read is pushed down to this parent only."""
    parent = spy_service.create_category("Parent")
    children = [spy_service.create_category(f"Child {i}") for i in range(4)]
    for index, child in enumerate(children):
        spy_service.add_category_parent(child.category_id, parent.category_id, sort_index=index)
    elsewhere = spy_service.create_category("Elsewhere")
    spy_service.add_category_parent(elsewhere.category_id, spy_service.create_category("Other").category_id)
    spy.reset()

    result = spy_service.list_categories(parent_id=parent.category_id)

    bulk_calls = spy.kwargs_of("get_categories_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["category_ids"] == {child.category_id for child in children}
    assert bulk_calls[0]["enabled"] is None
    # SC-003: the whole link table must not be read to answer one parent.
    link_calls = spy.kwargs_of("list_category_parent_links")
    assert len(link_calls) == 1
    assert link_calls[0]["parent_category_ids"] == {parent.category_id}
    assert result == children


def test_list_categories_by_parent_checks_existence_exactly_once(
    spy: RecordingRepository, spy_service: TaxomeshService
) -> None:
    """FR-020/R4: EXACTLY one single-row category read — the existence check — never zero.

    A blanket "zero" assertion is wrong for this path: the check and the
    resolution concern the same entity type. Asserting zero here would fail on a
    correct implementation.
    """
    parent = spy_service.create_category("Parent")
    child = spy_service.create_category("Child")
    spy_service.add_category_parent(child.category_id, parent.category_id)
    spy.reset()

    spy_service.list_categories(parent_id=parent.category_id)

    assert spy.count_of("get_category") == 1


def test_list_categories_by_item_resolves_in_one_batch(spy: RecordingRepository, spy_service: TaxomeshService) -> None:
    """FR-020: zero single-row CATEGORY reads here — the existence check reads an item."""
    item = spy_service.create_item("Placed")
    categories = [spy_service.create_category(f"Cat {i}") for i in range(4)]
    for index, category in enumerate(categories):
        spy_service.place_item_in_category(item.item_id, category.category_id, sort_index=index)
    spy.reset()

    result = spy_service.list_categories_by_item(item.item_id)

    assert spy.count_of("get_category") == 0, "a category was resolved one row at a time"
    assert spy.count_of("get_item") == 1, "the existence check must remain, and cost exactly one read"
    bulk_calls = spy.kwargs_of("get_categories_by_ids")
    assert len(bulk_calls) == 1
    assert bulk_calls[0]["category_ids"] == {category.category_id for category in categories}
    assert bulk_calls[0]["enabled"] is None
    assert result == categories
