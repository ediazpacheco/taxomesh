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
