"""Persistence tests for ItemRelationLink in DjangoRepository (US5)."""

import pytest

django = pytest.importorskip("django", reason="Django is not installed")

from django.db import connection  # noqa: E402

from taxomesh.adapters.repositories.django_repository import DjangoRepository  # noqa: E402
from taxomesh.application.service import TaxomeshService  # noqa: E402
from taxomesh.contrib.django.models import ItemRelationLinkModel  # noqa: E402
from taxomesh.domain.models import Item, ItemRelationLink  # noqa: E402

pytestmark = pytest.mark.django_db


def make_repo() -> DjangoRepository:
    return DjangoRepository()


def make_service() -> TaxomeshService:
    return TaxomeshService(repository=make_repo())


class TestDjangoRelationTableExists:
    """Migration creates the item_relation_link table."""

    def test_item_relation_link_table_exists(self) -> None:
        table_names = connection.introspection.table_names()
        assert "taxomesh_item_relation_link" in table_names


class TestDjangoRelationPersistence:
    """Relations are saved and retrieved correctly via DjangoRepository."""

    def test_save_and_retrieve_relation(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=3, metadata={"x": 1})

        links = svc.list_item_relations(src.item_id)
        assert len(links) == 1
        lnk = links[0]
        assert lnk.source_item_id == src.item_id
        assert lnk.target_item_id == tgt.item_id
        assert lnk.relation_type == "covers"
        assert lnk.sort_index == 3
        assert lnk.metadata == {"x": 1}

    def test_upsert_updates_sort_and_metadata(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=1)
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=9, metadata={"upd": True})

        links = svc.list_item_relations(src.item_id)
        assert len(links) == 1
        assert links[0].sort_index == 9
        assert links[0].metadata == {"upd": True}

    def test_unique_constraint_enforced(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        # Second call with same triple should upsert, not create a duplicate
        svc.relate_items(src.item_id, tgt.item_id, "covers", sort_index=5)
        count = ItemRelationLinkModel.objects.filter(
            source_item_id=src.item_id,
            target_item_id=tgt.item_id,
            relation_type="covers",
        ).count()
        assert count == 1

    def test_incoming_direction_filter(self) -> None:
        svc = make_service()
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        c = svc.create_item(name="C")
        svc.relate_items(a.item_id, b.item_id, "covers")
        svc.relate_items(c.item_id, b.item_id, "covers")

        links = svc.list_item_relations(b.item_id, direction="incoming")
        assert len(links) == 2
        sources = {lnk.source_item_id for lnk in links}
        assert sources == {a.item_id, c.item_id}

    def test_both_direction_filter(self) -> None:
        svc = make_service()
        author = svc.create_item(name="Author")
        peer = svc.create_item(name="Peer")
        work = svc.create_item(name="Work")
        svc.relate_items(author.item_id, peer.item_id, "worked_with")  # outgoing
        svc.relate_items(work.item_id, author.item_id, "lyrics_by")  # incoming

        both = svc.list_item_relations(author.item_id, direction="both")
        triples = {(lnk.source_item_id, lnk.target_item_id, lnk.relation_type) for lnk in both}
        assert triples == {
            (author.item_id, peer.item_id, "worked_with"),
            (work.item_id, author.item_id, "lyrics_by"),
        }
        # The original bug: outgoing alone drops the incoming credit.
        assert svc.list_item_relations(author.item_id, direction="outgoing") == [
            lnk for lnk in both if lnk.source_item_id == author.item_id
        ]

    def test_remove_relation(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        svc.remove_item_relation(src.item_id, tgt.item_id, "covers")

        assert svc.list_item_relations(src.item_id) == []

    def test_list_related_items_returns_item_objects(self) -> None:
        svc = make_service()
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        svc.relate_items(a.item_id, b.item_id, "covers")

        items = svc.list_related_items(a.item_id)
        assert len(items) == 1
        assert isinstance(items[0], Item)
        assert items[0].item_id == b.item_id


class TestDjangoRelationCascadeDelete:
    """Django on_delete=CASCADE removes relations when an item is deleted."""

    def test_deleting_source_item_cascades(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        svc.delete_item(src.item_id)

        links = svc.list_item_relations(tgt.item_id, direction="incoming")
        assert links == []

    def test_deleting_target_item_cascades(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")
        svc.delete_item(tgt.item_id)

        assert svc.list_item_relations(src.item_id) == []

    def test_returned_types_are_item_relation_link(self) -> None:
        svc = make_service()
        src = svc.create_item(name="A")
        tgt = svc.create_item(name="B")
        svc.relate_items(src.item_id, tgt.item_id, "covers")

        links = svc.list_item_relations(src.item_id)
        assert all(isinstance(lnk, ItemRelationLink) for lnk in links)


@pytest.mark.django_db
class TestDjangoBatchRelationLookup:
    """Tests for DjangoRepository.list_item_relation_links_for_items."""

    def test_returns_links_for_multiple_sources(self) -> None:
        svc = make_service()
        a = svc.create_item(name="A")
        b = svc.create_item(name="B")
        c = svc.create_item(name="C")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(a.item_id, t1.item_id, "x")
        svc.relate_items(b.item_id, t2.item_id, "y")

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([a.item_id, b.item_id])
        assert len(links) == 2
        source_ids = {lnk.source_item_id for lnk in links}
        assert source_ids == {a.item_id, b.item_id}
        assert all(lnk.source_item_id != c.item_id for lnk in links)

    def test_empty_source_ids_returns_empty(self) -> None:
        repo = make_repo()
        assert repo.list_item_relation_links_for_items([]) == []

    def test_filters_by_relation_types(self) -> None:
        svc = make_service()
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([src.item_id], relation_types=["music_by"])
        assert len(links) == 1
        assert links[0].relation_type == "music_by"

    def test_none_filter_returns_all(self) -> None:
        svc = make_service()
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([src.item_id], relation_types=None)
        assert len(links) == 2

    def test_empty_filter_returns_all(self) -> None:
        svc = make_service()
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "music_by")
        svc.relate_items(src.item_id, t2.item_id, "lyrics_by")

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([src.item_id], relation_types=[])
        assert len(links) == 2

    def test_ordering(self) -> None:
        svc = make_service()
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "covers", sort_index=5)
        svc.relate_items(src.item_id, t2.item_id, "covers", sort_index=1)

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([src.item_id])
        assert links[0].sort_index == 1
        assert links[1].sort_index == 5

    def test_uses_single_db_query(self) -> None:
        svc = make_service()
        src = svc.create_item(name="src")
        t1 = svc.create_item(name="T1")
        t2 = svc.create_item(name="T2")
        svc.relate_items(src.item_id, t1.item_id, "covers")
        svc.relate_items(src.item_id, t2.item_id, "samples")

        repo = make_repo()
        from django.test.utils import CaptureQueriesContext  # noqa: PLC0415

        with CaptureQueriesContext(connection) as ctx:
            links = repo.list_item_relation_links_for_items([src.item_id])
        assert len(ctx.captured_queries) == 1
        assert len(links) == 2

    def test_incoming_returns_links_by_target(self) -> None:
        svc = make_service()
        s1 = svc.create_item(name="S1")
        s2 = svc.create_item(name="S2")
        tgt = svc.create_item(name="tgt")
        other = svc.create_item(name="other")
        svc.relate_items(s1.item_id, tgt.item_id, "covers")
        svc.relate_items(s2.item_id, tgt.item_id, "covers")
        svc.relate_items(s1.item_id, other.item_id, "covers")

        repo = make_repo()
        links = repo.list_item_relation_links_for_items([tgt.item_id], direction="incoming")
        assert {lnk.source_item_id for lnk in links} == {s1.item_id, s2.item_id}
        assert all(lnk.target_item_id == tgt.item_id for lnk in links)

    def test_both_uses_single_or_query(self) -> None:
        svc = make_service()
        mid = svc.create_item(name="mid")
        out_tgt = svc.create_item(name="out")
        in_src = svc.create_item(name="in")
        svc.relate_items(mid.item_id, out_tgt.item_id, "covers")  # outgoing for mid
        svc.relate_items(in_src.item_id, mid.item_id, "covers")  # incoming for mid

        repo = make_repo()
        from django.test.utils import CaptureQueriesContext  # noqa: PLC0415

        with CaptureQueriesContext(connection) as ctx:
            links = repo.list_item_relation_links_for_items([mid.item_id], direction="both")
        # A single combined source-OR-target query, not two.
        assert len(ctx.captured_queries) == 1
        triples = {(lnk.source_item_id, lnk.target_item_id) for lnk in links}
        assert triples == {(mid.item_id, out_tgt.item_id), (in_src.item_id, mid.item_id)}
